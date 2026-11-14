"""Tudo que usa o FFmpeg: duração, áudio, volume, corte e miniatura."""
import json
import re
import subprocess
from pathlib import Path

TAMANHOS = {
    # formato: (largura, altura) da exportação final em 1080p
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}


class ErroVideo(Exception):
    pass


def _rodar(comando: list[str]) -> subprocess.CompletedProcess:
    resultado = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if resultado.returncode != 0:
        raise ErroVideo(resultado.stderr[-800:])
    return resultado


def duracao(arquivo: Path) -> float:
    """Duração do vídeo em segundos."""
    r = _rodar(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(arquivo)])
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except (KeyError, ValueError):
        raise ErroVideo("Não consegui ler a duração do vídeo.")


def tem_audio(arquivo: Path) -> bool:
    r = _rodar(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(arquivo)])
    return bool(r.stdout.strip())


def extrair_audio(arquivo: Path, inicio: float, fim: float, saida: Path) -> Path:
    """Áudio em WAV mono 16 kHz, o formato que o Whisper prefere."""
    _rodar(["ffmpeg", "-y", "-v", "error", "-ss", f"{inicio:.2f}", "-t", f"{fim - inicio:.2f}", "-i", str(arquivo),
            "-vn", "-ac", "1", "-ar", "16000", str(saida)])
    return saida


def volume_por_segundo(arquivo: Path, inicio: float, fim: float) -> list[float]:
    """Volume (RMS em dB) de cada segundo do trecho. Serve para achar momentos de empolgação."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{inicio:.2f}", "-t", f"{fim - inicio:.2f}", "-i", str(arquivo), "-vn",
         "-af", "aresample=8000,asetnsamples=8000,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
         "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    valores = []
    for m in re.finditer(r"RMS_level=(-?[\d.]+|-inf)", r.stdout):
        v = m.group(1)
        valores.append(-90.0 if v == "-inf" else max(-90.0, float(v)))
    return valores


def _caminho_ffmpeg(caminho: Path) -> str:
    """O filtro de legenda do FFmpeg precisa de barras e dois-pontos escapados (importante no Windows)."""
    return str(caminho.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def renderizar(arquivo: Path, inicio: float, fim: float, saida: Path, formato: str = "9:16",
               escala: float = 1.0, legenda_ass: Path | None = None, rapido: bool = False,
               layout: dict | None = None) -> Path:
    """Corta o trecho, monta o enquadramento e (opcionalmente) grava a legenda no vídeo."""
    from .enquadramento import filtro
    largura, altura = TAMANHOS.get(formato, TAMANHOS["9:16"])
    largura, altura = int(largura * escala) // 2 * 2, int(altura * escala) // 2 * 2
    if formato == "16:9":
        grafo = (f"[0:v]scale={largura}:{altura}:force_original_aspect_ratio=decrease,"
                 f"pad={largura}:{altura}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[v]")
    elif formato == "1:1":
        tipo = (layout or {}).get("tipo")
        grafo = filtro(layout if tipo in ("rosto", "desfocado") else {"tipo": "centro"}, largura, altura)
    else:
        grafo = filtro(layout or {"tipo": "centro"}, largura, altura)
    if legenda_ass:
        grafo += f";[v]subtitles='{_caminho_ffmpeg(legenda_ass)}'[saida]"
    else:
        grafo += ";[v]null[saida]"
    comando = ["ffmpeg", "-y", "-v", "error", "-ss", f"{inicio:.3f}", "-t", f"{fim - inicio:.3f}", "-i", str(arquivo),
               "-filter_complex", grafo, "-map", "[saida]", "-map", "0:a?",
               "-c:v", "libx264", "-preset", "ultrafast" if rapido else "veryfast",
               "-crf", "28" if rapido else "21", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(saida)]
    _rodar(comando)
    return saida


def recortar_fonte(arquivo: Path, inicio: float, fim: float, saida: Path) -> Path:
    """Guarda só um pedaço do vídeo original (com folga) em boa qualidade.
    Assim o original pode ser apagado e o disco do servidor não enche."""
    _rodar(["ffmpeg", "-y", "-v", "error", "-ss", f"{inicio:.3f}", "-t", f"{fim - inicio:.3f}", "-i", str(arquivo),
            "-map", "0:v:0", "-map", "0:a?", "-vf", "scale=-2:'min(ih,1080)'",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", str(saida)])
    return saida


def miniatura(video: Path, saida: Path) -> Path:
    total = duracao(video)
    _rodar(["ffmpeg", "-y", "-v", "error", "-ss", f"{total / 3:.2f}", "-i", str(video), "-frames:v", "1",
            "-vf", "scale=360:-2", "-q:v", "4", str(saida)])
    return saida
