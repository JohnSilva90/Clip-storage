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


# ---------------- Sinais de "momento forte" ----------------
# Palavras que costumam aparecer em reações fortes (gameplay, live, podcast)
REACOES = {
    "caraca", "caramba", "nossa", "meu deus", "deus", "não acredito", "nao acredito", "que isso", "mano", "socorro",
    "kkkk", "kkk", "haha", "hahaha", "rindo", "incrível", "incrivel", "absurdo", "insano", "surreal", "olha isso",
    "olha", "corre", "cuidado", "atrás", "morri", "morreu", "matei", "explodiu", "explosão", "bomba", "tiro",
    "headshot", "clutch", "ganhamos", "ganhei", "vitória", "perdemos", "acabou", "chorando", "chorei", "choro",
    "emocionado", "emocionante", "obrigado", "obrigada", "te amo", "eu te amo", "parabéns", "gol", "porra",
    "caralho", "puta", "eita", "vixe", "uau", "wow", "omg", "não", "sim", "vai",
}
FORTES = {"meu deus", "não acredito", "nao acredito", "socorro", "morri", "explodiu", "clutch", "headshot",
          "chorando", "chorei", "te amo", "caralho", "porra", "insano", "absurdo", "ganhamos", "kkkk"}


def _normalizar(valores: list[float]) -> list[float]:
    if not valores:
        return []
    vmin, vmax = min(valores), max(valores)
    return [(v - vmin) / (vmax - vmin) if vmax > vmin else 0.0 for v in valores]


def sinais(volumes: list[float], inicio_trecho: float, palavras: list[dict] | None) -> dict:
    """Para cada segundo: volume, "susto" (subida brusca de volume) e palavras de reação."""
    total = len(volumes)
    vol = _normalizar(volumes)
    # Subida brusca: volume agora comparado com a média dos 6 segundos anteriores
    subida = []
    for i in range(total):
        antes = vol[max(0, i - 6):i] or [vol[i]]
        subida.append(max(0.0, vol[i] - sum(antes) / len(antes)))
    subida = _normalizar(subida)
    reacao = [0.0] * total
    fala = [0] * total
    texto = [w["p"].lower().strip(".,!?…\"'") for w in (palavras or [])]
    for k, w in enumerate(palavras or []):
        seg = int(w["i"] - inicio_trecho)
        if not 0 <= seg < total:
            continue
        fala[seg] += 1
        dupla = texto[k] + " " + texto[k + 1] if k + 1 < len(texto) else ""
        if dupla in FORTES or texto[k] in FORTES:
            reacao[seg] += 2
        elif dupla in REACOES or texto[k] in REACOES:
            reacao[seg] += 1
        if w["p"].endswith(("!", "?!")):
            reacao[seg] += 0.5
    return {"volume": vol, "subida": subida, "reacao": reacao, "fala": fala}


# ---------------- Modo grátis ----------------
def por_volume(volumes: list[float], inicio_trecho: float, palavras: list[dict] | None,
               quantidade: int, faixa: tuple[int, int]) -> list[dict]:
    """Procura os trechos com mais energia: picos de volume (tiros, explosões, gritos),
    subidas bruscas (sustos, reações) e palavras de emoção (risada, choro, comemoração)."""
    total = len(volumes)
    if total == 0:
        return []
    alvo = min(total, (faixa[0] + faixa[1]) // 2)
    s = sinais(volumes, inicio_trecho, palavras)
    vol, subida, reacao, fala = s["volume"], s["subida"], s["reacao"], s["fala"]

    pontos = []
    for ini in range(0, max(1, total - alvo + 1)):
        janela = range(ini, ini + alvo)
        media = sum(vol[i] for i in janela) / alvo
        pico = max(vol[i] for i in janela)
        susto = max(subida[i] for i in janela)
        emocao = min(sum(reacao[i] for i in janela) / 4, 1.0)
        falando = min(sum(fala[i] for i in janela) / (alvo * 2.0), 1.0) if palavras else 0.5
        # o momento mais forte nos primeiros 40% do corte prende a atenção logo no começo (gancho)
        momento = max(janela, key=lambda i: vol[i] + subida[i] + reacao[i] / 2)
        gancho = 0.08 if momento - ini <= alvo * 0.4 else 0.0
        nota = media * 0.25 + pico * 0.2 + susto * 0.2 + emocao * 0.2 + falando * 0.07 + gancho
        pontos.append((nota, ini, momento))
    pontos.sort(reverse=True)

    escolhidos = []
    for nota, ini, momento in pontos:
        if len(escolhidos) >= quantidade:
            break
        if all(abs(ini - e[1]) >= alvo for e in escolhidos):
            escolhidos.append((nota, ini, momento))

    melhor = escolhidos[0][0] if escolhidos else 1
    cortes = []
    for nota, ini, momento in escolhidos:
        a, b = _ajustar_a_palavras(inicio_trecho + ini, inicio_trecho + ini + alvo, palavras)
        motivos = []
        if subida[momento] > 0.5:
            motivos.append("reação forte / susto")
        if vol[momento] > 0.8:
            motivos.append("pico de volume (grito, tiro ou explosão)")
        if sum(reacao[i] for i in range(ini, ini + alvo)) >= 2:
            motivos.append("palavras de emoção")
        motivo = ", ".join(motivos) or "trecho com mais energia"
        cortes.append({"inicio": a, "fim": b, "nota": int(60 + 38 * (nota / melhor if melhor else 0)),
                       "titulo": _titulo(palavras, a, b),
                       "motivo": f"Momento forte aos {mmss(inicio_trecho + momento)}: {motivo}."})
    return cortes


def com_claude(palavras: list[dict], quantidade: int, faixa: tuple[int, int],
               volumes: list[float] | None = None, inicio_trecho: float = 0) -> list[dict] | None:
    if not ANTHROPIC_API_KEY or not palavras:
        return None
    try:
        import anthropic
    except ImportError:
        log.warning("Pacote 'anthropic' não instalado.")
        return None
    pedido = f"""Você é editor de vídeos curtos virais para TikTok, Reels e Shorts, especialista em lives de games
(como GTA), podcasts e reacts. Abaixo está a transcrição de um vídeo, com o tempo em segundos no início de cada linha.
Marcas [ÁUDIO: ...] indicam gritos, tiros, explosões ou sustos que não aparecem no texto.

Escolha os {quantidade} melhores trechos para virar cortes. Priorize, nesta ordem de importância:
1. Ação e jogadas: explosões, tiroteios, perseguições, jogadas bonitas ou decisivas, clutch, fails engraçados.
2. Reações fortes: gritos, sustos, "não acredito", comemoração, raiva.
3. Emoção: choro, agradecimento, desabafo, momentos sentimentais.
4. Humor e polêmica: risadas, piadas, opiniões fortes, histórias curiosas.

Cada corte deve:
- ter entre {faixa[0]} e {faixa[1]} segundos;
- começar 3 a 8 segundos ANTES do momento forte (para dar contexto) e terminar logo depois da reação;
- fazer sentido sozinho, sem cortar frase no meio;
- não se sobrepor a outro corte.

Responda SOMENTE com JSON, neste formato:
[{{"inicio": 123.4, "fim": 165.0, "titulo": "título curto e chamativo", "nota": 0-100, "motivo": "por que vai engajar"}}]

TRANSCRIÇÃO:
{_texto_com_tempos(palavras, volumes, inicio_trecho)[:180000]}"""
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
    cortes = com_claude(palavras, quantidade, faixa, volumes, inicio_trecho)
    if cortes:
        return cortes, "claude"
    return por_volume(volumes, inicio_trecho, palavras, quantidade, faixa), "volume"
