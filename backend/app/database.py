"""Conexão com o banco de dados (SQLite no desenvolvimento)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import URL_BANCO

argumentos = {"check_same_thread": False} if URL_BANCO.startswith("sqlite") else {}
motor = create_engine(URL_BANCO, connect_args=argumentos)
SessaoBanco = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def obter_banco():
    """Abre uma sessão do banco para cada requisição e fecha no final."""
    banco = SessaoBanco()
    try:
        yield banco
    finally:
        banco.close()
