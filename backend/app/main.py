"""Clip Storage — servidor principal.

Para rodar (dentro da pasta backend):
    uvicorn app.main:app --reload
Depois abra http://localhost:8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect, text

from .config import ANTHROPIC_API_KEY, PAGAMENTO_SIMULADO, PASTA_SITE
from .database import Base, motor
from .processamento import fila, transcricao
from .rotas import auth, conta, cortes, pagamentos, projetos

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s", datefmt="%H:%M:%S")

PAGINAS = {"index", "login", "cadastro", "recuperar-senha", "painel", "importar", "editor", "assinatura", "campeonatos",
           "termos", "privacidade"}


def atualizar_banco():
    """Cria as tabelas novas e adiciona colunas novas em bancos antigos (migração simples)."""
    Base.metadata.create_all(motor)
    insp = inspect(motor)
    with motor.begin() as conexao:
        for tabela in Base.metadata.sorted_tables:
            existentes = {c["name"] for c in insp.get_columns(tabela.name)}
            for coluna in tabela.columns:
                if coluna.name not in existentes:
                    tipo = coluna.type.compile(motor.dialect)
                    conexao.execute(text(f"ALTER TABLE {tabela.name} ADD COLUMN {coluna.name} {tipo}"))


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    atualizar_banco()                     # cria/atualiza as tabelas
    fila.iniciar()                        # liga o trabalhador que processa os vídeos
    yield
    fila.parar()


app = FastAPI(title="Clip Storage API", version="0.2.0", lifespan=ciclo_de_vida)
app.include_router(auth.rotas)
app.include_router(projetos.rotas)
app.include_router(cortes.rotas)
app.include_router(conta.rotas)
app.include_router(pagamentos.rotas)


@app.get("/api/saude", tags=["Sistema"])
def saude():
    """O site usa isto para saber se está conectado ao servidor."""
    return {"ok": True, "transcricao": transcricao.disponivel(), "ia_claude": bool(ANTHROPIC_API_KEY),
            "pagamento_simulado": PAGAMENTO_SIMULADO}


@app.middleware("http")
async def sem_cache_antigo(request, chamar):
    """Faz o navegador sempre conferir se o site mudou (evita ficar com JavaScript antigo)."""
    resposta = await chamar(request)
    if not request.url.path.startswith("/api/"):
        resposta.headers["Cache-Control"] = "no-cache"
    return resposta


# ---------- Site (só os arquivos públicos; a pasta backend nunca é exposta) ----------
app.mount("/assets", StaticFiles(directory=PASTA_SITE / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(PASTA_SITE / "index.html")


@app.get("/{pagina}.html", include_in_schema=False)
def pagina_html(pagina: str):
    if pagina not in PAGINAS:
        raise HTTPException(404)
    return FileResponse(PASTA_SITE / f"{pagina}.html")
