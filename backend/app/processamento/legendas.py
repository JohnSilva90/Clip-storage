"""Gera o arquivo de legenda .ASS (animado, palavra por palavra) que o FFmpeg grava no vídeo."""
from pathlib import Path

from .video import TAMANHOS

PALAVRAS_POR_BLOCO = 3


def _cor_ass(hexa: str) -> str:
    """'#ffd84d' -> '&H004DD8FF' (o ASS usa azul-verde-vermelho)."""
    hexa = (hexa or "#ffd84d").lstrip("#")
    if len(hexa) != 6:
        hexa = "ffd84d"
    r, g, b = hexa[0:2], hexa[2:4], hexa[4:6]
    return f"&H00{b}{g}{r}".upper()


def _tempo(s: float) -> str:
    s = max(0.0, s)
    h, resto = divmod(s, 3600)
    m, seg = divmod(resto, 60)
    return f"{int(h)}:{int(m):02d}:{seg:05.2f}"


def palavras_do_corte(palavras: list[dict] | None, inicio: float, fim: float, texto_editado: str | None = None) -> list[dict]:
    """Palavras do corte com o tempo relativo ao começo do corte (0 = início)."""
    originais = [w for w in (palavras or []) if w["i"] >= inicio - 0.05 and w["f"] <= fim + 0.3]
    lista = [{"p": w["p"], "i": w["i"] - inicio, "f": w["f"] - inicio} for w in originais]
    if texto_editado and texto_editado.strip():
        novas = texto_editado.split()
        if lista:   # espalha o texto novo no mesmo intervalo de fala
            a, b = lista[0]["i"], lista[-1]["f"]
        else:
            a, b = 0.3, (fim - inicio) - 0.3
        passo = (b - a) / max(1, len(novas))
        lista = [{"p": p, "i": a + k * passo, "f": a + (k + 1) * passo} for k, p in enumerate(novas)]
    return lista


def gerar_ass(lista: list[dict], estilo: dict, saida: Path, marca_dagua: bool, duracao: float) -> Path:
    formato = estilo.get("formato", "9:16")
    largura, altura = TAMANHOS.get(formato, TAMANHOS["9:16"])
    tipo = estilo.get("legenda", "destaque")
    destaque = _cor_ass(estilo.get("cor", "#ffd84d"))
    posicao = estilo.get("posicao", "baixo")
    alinhamento = {"baixo": 2, "meio": 5, "cima": 8}.get(posicao, 2)
    margem_v = int(altura * (0.20 if posicao == "baixo" else 0.12))
    tamanho = int(largura * (0.075 if formato != "16:9" else 0.045))

    if tipo == "classica":
        borda, contorno, sombra, fundo = 3, 14, 0, "&H90000000"   # caixa preta atrás do texto
    elif tipo == "neon":
        borda, contorno, sombra, fundo = 1, 5, 0, "&H00000000"
    else:
        borda, contorno, sombra, fundo = 1, 7, 3, "&H80000000"
    cor_contorno = "&H00F65C8B" if tipo == "neon" else "&H00000000"

    linhas = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {largura}", f"PlayResY: {altura}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Legenda,Arial,{tamanho},&H00FFFFFF,&H00FFFFFF,{cor_contorno},{fundo},-1,0,0,0,100,100,0,0,{borda},{contorno},{sombra},{alinhamento},60,60,{margem_v},1",
        f"Style: Marca,Arial,{int(tamanho * 0.45)},&H60FFFFFF,&H00FFFFFF,&H80000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,9,40,40,40,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    efeito_neon = r"\blur4" if tipo == "neon" else ""

    # Blocos de 3 palavras; a palavra falada no momento fica colorida e maior.
    for k in range(0, len(lista), PALAVRAS_POR_BLOCO):
        bloco = lista[k:k + PALAVRAS_POR_BLOCO]
        for j, atual in enumerate(bloco):
            ini = atual["i"]
            fim = bloco[j + 1]["i"] if j + 1 < len(bloco) else atual["f"] + 0.15
            partes = []
            for w in bloco:
                texto = w["p"].upper().replace("{", "").replace("}", "")
                if w is atual:
                    partes.append(r"{\c" + destaque + r"&\fscx112\fscy112}" + texto + r"{\c&H00FFFFFF&\fscx100\fscy100}")
                else:
                    partes.append(texto)
            linhas.append(f"Dialogue: 0,{_tempo(ini)},{_tempo(fim)},Legenda,,0,0,0,,{{{efeito_neon}}}{' '.join(partes)}")

    if marca_dagua:
        linhas.append(f"Dialogue: 1,{_tempo(0)},{_tempo(duracao + 1)},Marca,,0,0,0,,CLIP STORAGE")

    saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return saida
