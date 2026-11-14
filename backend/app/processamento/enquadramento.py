"""Enquadramento inteligente para o formato vertical (9:16).

Olha alguns quadros do trecho, procura rostos e escolhe o layout:
- "streamer":  rosto pequeno num canto (webcam por cima do jogo) -> câmera em cima, jogo embaixo
- "rosto":     rosto grande (podcast, vlog, react)               -> corte vertical seguindo o rosto
- "desfocado": sem rosto (gameplay puro)                         -> tela inteira com fundo desfocado
"""
import logging
from pathlib import Path

log = logging.getLogger("clipstorage.enquadramento")

LAYOUTS = ("auto", "streamer", "rosto", "desfocado", "centro")


def _detector():
    import cv2
    caminho = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    return cv2, cv2.CascadeClassifier(caminho)


def analisar(arquivo: Path, inicio: float, fim: float, amostras: int = 10) -> dict:
    """Devolve {"tipo": ..., "camera": [x, y, w, h] (frações), "rosto_x": fração}."""
    try:
        cv2, detector = _detector()
    except Exception as erro:  # OpenCV não instalado
        log.warning("OpenCV indisponível (%s): usando fundo desfocado.", erro)
        return {"tipo": "desfocado"}

    cap = cv2.VideoCapture(str(arquivo))
    largura = cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0
    altura = cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0
    if not largura or not altura:
        cap.release()
        return {"tipo": "desfocado"}
    if altura > largura:          # vídeo já vertical
        cap.release()
        return {"tipo": "centro"}

    rostos = []
    duracao = max(1.0, fim - inicio)
    for k in range(amostras):
        t = inicio + duracao * (k + 0.5) / amostras
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, quadro = cap.read()
        if not ok:
            continue
        cinza = cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
        achados = detector.detectMultiScale(cinza, scaleFactor=1.1, minNeighbors=6,
                                            minSize=(int(altura * 0.06), int(altura * 0.06)))
        if len(achados):
            x, y, w, h = max(achados, key=lambda r: r[2] * r[3])   # o maior rosto do quadro
            rostos.append((x / largura, y / altura, w / largura, h / altura))
    cap.release()

    # Precisa achar o rosto na maioria dos quadros, e sempre no mesmo lugar
    if len(rostos) < max(3, amostras * 0.5):
        return {"tipo": "desfocado"}
    rostos.sort(key=lambda r: r[0] + r[2] / 2)
    x, y, w, h = rostos[len(rostos) // 2]           # mediana (ignora detecções soltas)
    cx, cy = x + w / 2, y + h / 2
    estaveis = [r for r in rostos if abs((r[0] + r[2] / 2) - cx) < 0.08 and abs((r[1] + r[3] / 2) - cy) < 0.1]
    if len(estaveis) < len(rostos) * 0.6:
        return {"tipo": "desfocado"}

    if w >= 0.12:
        return {"tipo": "rosto", "rosto_x": round(float(cx), 4)}

    # Webcam: um retângulo 16:9 em volta do rosto (o rosto ocupa ~1/4 da largura da câmera)
    cam_w = min(0.5, w * 3.4)
    cam_h = cam_w * (largura / altura) * 9 / 16
    cam_x = min(max(0.0, cx - cam_w / 2), 1 - cam_w)
    cam_y = min(max(0.0, cy - cam_h * 0.45), 1 - cam_h)
    return {"tipo": "streamer", "camera": [round(float(v), 4) for v in (cam_x, cam_y, cam_w, cam_h)]}


def filtro(layout: dict | None, largura: int, altura: int) -> str:
    """Monta o filtro do FFmpeg (filter_complex) que termina na saída [v]."""
    tipo = (layout or {}).get("tipo", "desfocado")
    def par(e):  # dimensão sempre par (exigência do H.264), entre aspas por causa das vírgulas
        return f"'trunc(({e})/2)*2'"

    def num(e):
        return f"trunc(({e})/2)*2"

    if tipo == "streamer" and layout.get("camera"):
        x, y, w, h = layout["camera"]
        topo = int(altura * 0.32) // 2 * 2
        baixo = altura - topo
        prop = largura / baixo
        return (f"[0:v]split=2[c][j];"
                f"[c]crop={par(f'iw*{w}')}:{par(f'ih*{h}')}:iw*{x}:ih*{y},scale={largura}:{topo},setsar=1[cam];"
                f"[j]crop={par(f'min(iw,ih*{prop:.5f})')}:{par(f'min(ih,iw/{prop:.5f})')},scale={largura}:{baixo},setsar=1[jogo];"
                f"[cam][jogo]vstack=inputs=2[v]")

    if tipo == "rosto" and "rosto_x" in layout:
        fx = layout["rosto_x"]
        prop = largura / altura
        cw = num(f"min(iw,ih*{prop:.5f})")
        return (f"[0:v]crop='{cw}':{par(f'min(ih,iw/{prop:.5f})')}:"
                f"'min(max(0,iw*{fx}-({cw})/2),iw-({cw}))':0,scale={largura}:{altura},setsar=1[v]")

    if tipo == "desfocado":
        return (f"[0:v]split=2[f][p];"
                f"[f]scale={largura}:{altura}:force_original_aspect_ratio=increase,crop={largura}:{altura},boxblur=24:4,eq=brightness=-0.08[fundo];"
                f"[p]scale={largura}:-2,setsar=1[frente];"
                f"[fundo][frente]overlay=(W-w)/2:(H-h)/2,setsar=1[v]")

    # "centro": recorte simples do meio
    prop = largura / altura
    return (f"[0:v]crop={par(f'min(iw,ih*{prop:.5f})')}:{par(f'min(ih,iw/{prop:.5f})')},"
            f"scale={largura}:{altura},setsar=1[v]")
