"""Transcrição do áudio com o faster-whisper (roda no próprio computador, grátis).

Se o faster-whisper não estiver instalado, o Clip Storage continua funcionando,
só que sem legendas e escolhendo os trechos pelo volume da voz.
"""
import logging
from pathlib import Path

from ..config import WHISPER_DISPOSITIVO, WHISPER_MODELO

log = logging.getLogger("clipstorage.transcricao")
_modelo = None


def disponivel() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _carregar():
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        tipo = "float16" if WHISPER_DISPOSITIVO == "cuda" else "int8"
        log.info("Carregando o modelo Whisper '%s' (%s)...", WHISPER_MODELO, WHISPER_DISPOSITIVO)
        _modelo = WhisperModel(WHISPER_MODELO, device=WHISPER_DISPOSITIVO, compute_type=tipo)
    return _modelo


def transcrever(audio_wav: Path, deslocamento: float, idioma: str = "pt", ao_progredir=None) -> list[dict] | None:
    """Devolve as palavras com o tempo de cada uma: [{"p": "olá", "i": 12.3, "f": 12.6}, ...].

    `deslocamento` soma o início do trecho, para os tempos ficarem no relógio do vídeo original.
    """
    if not disponivel():
        log.warning("faster-whisper não instalado: seguindo sem transcrição.")
        return None
    try:
        modelo = _carregar()
        segmentos, info = modelo.transcribe(str(audio_wav), language=idioma or None, word_timestamps=True, vad_filter=True)
        palavras = []
        for seg in segmentos:
            for w in seg.words or []:
                texto = w.word.strip()
                if texto:
                    palavras.append({"p": texto, "i": round(w.start + deslocamento, 2), "f": round(w.end + deslocamento, 2)})
            if ao_progredir and info.duration:
                ao_progredir(min(1.0, seg.end / info.duration))
        return palavras
    except Exception as erro:  # modelo não baixou, falta de memória etc.
        log.exception("Falha na transcrição: %s", erro)
        return None
