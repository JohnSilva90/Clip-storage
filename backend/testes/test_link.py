"""Testes da importação por link (o yt-dlp é "fingido": não acessa a internet)."""
import os
import shutil
import subprocess
import tempfile
import time


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.processamento import download  # noqa: E402

VIDEO = os.path.join(tempfile.mkdtemp(), "fonte.mp4")


@pytest.fixture(scope="module", autouse=True)
def video_de_teste():
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24", "-f", "lavfi",
                    "-i", "sine=frequency=300", "-t", "40", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", VIDEO], check=True)


@pytest.fixture(autouse=True)
def yt_falso(monkeypatch):
    def info(url):
        if "privado" in url:
            raise download.ErroLink("Esse vídeo é privado.")
        return {"url": url, "titulo": "Minha live de teste", "duracao": 3600.0, "miniatura": None, "canal": "Canal"}

    def baixar(url, inicio, fim, pasta, nome, ao_progredir=None):
        if ao_progredir:
            ao_progredir(0.5)
        destino = pasta / f"{nome}.mp4"
        shutil.copy(VIDEO, destino)
        return destino

    monkeypatch.setattr(download, "informacoes", info)
    monkeypatch.setattr(download, "baixar_trecho", baixar)


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        c.post("/api/auth/cadastro", json={"nome": "Link", "email": f"l{os.urandom(3).hex()}@t.com", "senha": "Senha@123"})
        yield c


def test_info_do_link(cliente):
    r = cliente.post("/api/projetos/link/info", json={"url": "https://www.youtube.com/watch?v=abc"})
    assert r.status_code == 200 and r.json()["duracao"] == 3600


def test_link_privado(cliente):
    r = cliente.post("/api/projetos/link/info", json={"url": "https://www.youtube.com/watch?v=privado"})
    assert r.status_code == 400 and "privado" in r.json()["detail"]


def test_plano_gratis_limita_trecho(cliente):
    r = cliente.post("/api/projetos/link", json={"url": "https://youtu.be/abc", "inicio_min": 0, "fim_min": 30})
    assert r.status_code == 403


def test_link_vira_cortes(cliente):
    r = cliente.post("/api/projetos/link", json={"url": "https://youtu.be/abc", "inicio_min": 10, "fim_min": 10.6,
                                                "duracao": "curto"})
    assert r.status_code == 200, r.text
    assert r.json()["saldo"] == 7
    pid = r.json()["id"]
    for _ in range(120):
        p = cliente.get(f"/api/projetos/{pid}").json()
        if p["status"] in ("pronto", "erro"):
            break
        time.sleep(0.5)
    assert p["status"] == "pronto", p
    assert p["lista_cortes"], "deveria ter cortes"
    assert cliente.get(p["lista_cortes"][0]["previa"]).status_code == 200


def test_bloqueia_endereco_interno():
    real = download.__dict__["_host_permitido"]
    with pytest.raises(download.ErroLink):
        real("http://127.0.0.1/video.mp4")
    with pytest.raises(download.ErroLink):
        real("https://exemplo.com/pagina.html")
