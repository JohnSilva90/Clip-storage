"""Importação por link: YouTube, Twitch, Kick e links diretos de vídeo (usa o yt-dlp).

Importante: use apenas vídeos seus ou que você tem permissão para usar.
"""
import ipaddress
import logging
import socket
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger("clipstorage.download")

PLATAFORMAS = ("youtube.com", "youtu.be", "twitch.tv", "kick.com")
EXTENSOES_DIRETAS = (".mp4", ".mov", ".mkv", ".webm", ".m4v")


class ErroLink(Exception):
    pass


def _host_permitido(url: str) -> str:
    """Aceita só http/https e bloqueia endereços internos (proteção contra SSRF)."""
    partes = urlparse(url.strip())
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise ErroLink("Cole um link válido, começando com https://")
    host = partes.hostname.lower()
    eh_plataforma = any(host == p or host.endswith("." + p) for p in PLATAFORMAS)
    if not eh_plataforma and not partes.path.lower().endswith(EXTENSOES_DIRETAS):
        raise ErroLink("Use um link do YouTube, Twitch ou Kick, ou um link direto de vídeo (.mp4).")
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ErroLink("Esse endereço não é permitido.")
    except socket.gaierror:
        raise ErroLink("Não encontrei esse site. Confira o link.")
    return url.strip()


def _yt_dlp():
    try:
        import yt_dlp
        return yt_dlp
    except ImportError:
        raise ErroLink("O yt-dlp não está instalado no servidor.")


def _mensagem_amigavel(erro: Exception) -> str:
    texto = str(erro).lower()
    if "private" in texto:
        return "Esse vídeo é privado."
    if "sign in" in texto or "age" in texto:
        return "Esse vídeo pede login ou é restrito por idade. Baixe o arquivo e envie pela aba Arquivo."
    if "unavailable" in texto or "not available" in texto or "404" in texto:
        return "Vídeo indisponível. Confira o link."
    if "live" in texto:
        return "Essa live ainda não terminou. Tente quando o vídeo estiver salvo."
    return "Não consegui ler esse link. Confira se o vídeo é público."


def informacoes(url: str) -> dict:
    """Título, duração e miniatura, sem baixar o vídeo."""
    url = _host_permitido(url)
    yt_dlp = _yt_dlp()
    opcoes = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as erro:
        log.warning("Falha ao ler o link %s: %s", url, erro)
        raise ErroLink(_mensagem_amigavel(erro))
    if info.get("_type") == "playlist":
        raise ErroLink("Esse link é de uma playlist. Use o link de um vídeo só.")
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise ErroLink("Essa live ainda não terminou. Tente quando o vídeo estiver salvo.")
    duracao = float(info.get("duration") or 0)
    if duracao <= 0:
        raise ErroLink("Não consegui descobrir a duração desse vídeo.")
    return {"url": url, "titulo": (info.get("title") or "Vídeo importado")[:200], "duracao": duracao,
            "miniatura": info.get("thumbnail"), "canal": info.get("uploader") or info.get("channel")}


def baixar_trecho(url: str, inicio: float, fim: float, pasta: Path, nome_base: str, ao_progredir=None) -> Path:
    """Baixa só o trecho escolhido (economiza tempo e espaço), em até 1080p."""
    url = _host_permitido(url)
    yt_dlp = _yt_dlp()
    from yt_dlp.utils import download_range_func

    def gancho(d):
        if ao_progredir and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                ao_progredir(min(1.0, d.get("downloaded_bytes", 0) / total))

    opcoes = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(pasta / f"{nome_base}.%(ext)s"),
        "download_ranges": download_range_func(None, [(inicio, fim)]),
        "force_keyframes_at_cuts": True,
        "progress_hooks": [gancho],
    }
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as erro:
        log.warning("Falha ao baixar %s: %s", url, erro)
        raise ErroLink(_mensagem_amigavel(erro))
    arquivos = sorted(pasta.glob(f"{nome_base}.*"), key=lambda p: p.stat().st_size, reverse=True)
    arquivos = [a for a in arquivos if a.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")]
    if not arquivos:
        raise ErroLink("O download terminou, mas não encontrei o vídeo.")
    return arquivos[0]
