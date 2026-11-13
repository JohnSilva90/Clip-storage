"""Escolha dos melhores trechos do vídeo.

Dois modos:
1. Com chave da Anthropic: o Claude lê a transcrição e escolhe os momentos.
2. Sem chave (grátis): procura os trechos com voz mais alta e mais fala por segundo.
"""
import json
import logging
import re

from ..config import ANTHROPIC_API_KEY, MODELO_CLAUDE

log = logging.getLogger("clipstorage.destaques")

DURACOES = {"curto": (15, 30), "medio": (30, 60), "longo": (60, 90)}


def mmss(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def quantos_cortes(minutos: float, pedido: str, maximo: int) -> int:
    if pedido and pedido.isdigit():
        return max(1, min(int(pedido), maximo))
    return max(1, min(maximo, round(minutos / 6) + 2))


def _ajustar_a_palavras(inicio: float, fim: float, palavras: list[dict] | None) -> tuple[float, float]:
    """Começa e termina o corte no limite de uma palavra, para não cortar ninguém no meio da fala."""
    if not palavras:
        return inicio, fim
    antes = [w for w in palavras if w["i"] <= inicio + 0.3]
    depois = [w for w in palavras if w["f"] >= fim - 0.3]
    novo_ini = antes[-1]["i"] if antes else inicio
    novo_fim = depois[0]["f"] if depois else fim
    return max(0.0, novo_ini - 0.15), novo_fim + 0.25


def _titulo(palavras: list[dict] | None, inicio: float, fim: float) -> str:
    if palavras:
        texto = " ".join(w["p"] for w in palavras if inicio <= w["i"] <= fim)
        texto = re.sub(r"\s+", " ", texto).strip()
        if texto:
            return (texto[:60].rsplit(" ", 1)[0] + "...") if len(texto) > 60 else texto
    return f"Momento em {mmss(inicio)}"


# ---------------- Modo grátis ----------------
def por_volume(volumes: list[float], inicio_trecho: float, palavras: list[dict] | None,
               quantidade: int, faixa: tuple[int, int]) -> list[dict]:
    """Janela deslizante: soma volume e quantidade de fala, e pega as melhores sem sobrepor."""
    total = len(volumes)
    if total == 0:
        return []
    alvo = min(total, (faixa[0] + faixa[1]) // 2)
    fala = [0] * total
    for w in palavras or []:
        seg = int(w["i"] - inicio_trecho)
        if 0 <= seg < total:
            fala[seg] += 1
    # deixa o volume entre 0 e 1
    vmin, vmax = min(volumes), max(volumes)
    norm = [(v - vmin) / (vmax - vmin) if vmax > vmin else 0.5 for v in volumes]

    pontos = []
    for ini in range(0, max(1, total - alvo + 1)):
        janela = norm[ini:ini + alvo]
        media = sum(janela) / len(janela)
        pico = max(janela)
        densidade = sum(fala[ini:ini + alvo]) / alvo if palavras else 0
        pontos.append((media * 0.6 + pico * 0.25 + min(densidade / 3, 1) * 0.15, ini))
    pontos.sort(reverse=True)

    escolhidos = []
    for nota, ini in pontos:
        if len(escolhidos) >= quantidade:
            break
        if all(abs(ini - e) >= alvo for _, e in escolhidos):
            escolhidos.append((nota, ini))

    melhor = escolhidos[0][0] if escolhidos else 1
    cortes = []
    for nota, ini in escolhidos:
        a, b = _ajustar_a_palavras(inicio_trecho + ini, inicio_trecho + ini + alvo, palavras)
        cortes.append({"inicio": a, "fim": b, "nota": int(60 + 38 * (nota / melhor if melhor else 0)),
                       "titulo": _titulo(palavras, a, b), "motivo": "Trecho com mais energia na voz."})
    return cortes


# ---------------- Modo Claude ----------------
def _texto_com_tempos(palavras: list[dict]) -> str:
    """Agrupa as palavras em linhas de ~12 segundos: '[12:30] texto...'."""
    linhas, atual, ini = [], [], None
    for w in palavras:
        if ini is None:
            ini = w["i"]
        atual.append(w["p"])
        if w["f"] - ini >= 12 or w["p"].endswith((".", "?", "!")):
            linhas.append(f"[{ini:.1f}] {' '.join(atual)}")
            atual, ini = [], None
    if atual:
        linhas.append(f"[{ini:.1f}] {' '.join(atual)}")
    return "\n".join(linhas)


def com_claude(palavras: list[dict], quantidade: int, faixa: tuple[int, int]) -> list[dict] | None:
    if not ANTHROPIC_API_KEY or not palavras:
        return None
    try:
        import anthropic
    except ImportError:
        log.warning("Pacote 'anthropic' não instalado.")
        return None
    pedido = f"""Você é editor de vídeos curtos virais para TikTok, Reels e Shorts.
Abaixo está a transcrição de um vídeo, com o tempo em segundos no início de cada linha.

Escolha os {quantidade} melhores trechos para virar cortes. Cada corte deve:
- ter entre {faixa[0]} e {faixa[1]} segundos;
- fazer sentido sozinho, com começo e fim claros (sem cortar frase no meio);
- prender a atenção nos primeiros 3 segundos (gancho forte, polêmica, humor, emoção, dica valiosa);
- não se sobrepor a outro corte.

Responda SOMENTE com JSON, neste formato:
[{{"inicio": 123.4, "fim": 165.0, "titulo": "título curto e chamativo", "nota": 0-100, "motivo": "por que vai engajar"}}]

TRANSCRIÇÃO:
{_texto_com_tempos(palavras)[:180000]}"""
    try:
        cliente = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resposta = cliente.messages.create(model=MODELO_CLAUDE, max_tokens=4000,
                                           messages=[{"role": "user", "content": pedido}])
        texto = "".join(b.text for b in resposta.content if getattr(b, "type", "") == "text")
        dados = json.loads(re.search(r"\[.*\]", texto, re.S).group(0))
    except Exception as erro:
        log.exception("Falha ao usar o Claude, voltando ao modo grátis: %s", erro)
        return None

    cortes = []
    for c in dados[:quantidade]:
        try:
            a, b = float(c["inicio"]), float(c["fim"])
        except (KeyError, TypeError, ValueError):
            continue
        if b - a < 5:
            continue
        a, b = _ajustar_a_palavras(a, b, palavras)
        cortes.append({"inicio": a, "fim": b, "nota": int(max(0, min(100, c.get("nota", 80)))),
                       "titulo": str(c.get("titulo") or _titulo(palavras, a, b))[:120],
                       "motivo": str(c.get("motivo", ""))[:400]})
    return cortes or None


def escolher(volumes, inicio_trecho, palavras, quantidade, duracao_pedida) -> tuple[list[dict], str]:
    faixa = DURACOES.get(duracao_pedida, DURACOES["medio"])
    cortes = com_claude(palavras, quantidade, faixa)
    if cortes:
        return cortes, "claude"
    return por_volume(volumes, inicio_trecho, palavras, quantidade, faixa), "volume"
