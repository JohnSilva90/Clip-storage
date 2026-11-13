"""Senhas criptografadas e login por cookie (JWT)."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from .config import CHAVE_SECRETA, DIAS_SESSAO
from .database import obter_banco
from .models import Usuario

NOME_COOKIE = "cs_sessao"


def gerar_hash(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def conferir_senha(senha: str, hash_salvo: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), hash_salvo.encode())
    except ValueError:
        return False


def criar_token(usuario_id: int, dias: int = DIAS_SESSAO) -> str:
    dados = {"sub": str(usuario_id), "exp": datetime.now(timezone.utc) + timedelta(days=dias)}
    return jwt.encode(dados, CHAVE_SECRETA, algorithm="HS256")


def usuario_logado(cs_sessao: str | None = Cookie(default=None), banco: Session = Depends(obter_banco)) -> Usuario:
    """Dependência das rotas protegidas: devolve o usuário do cookie ou erro 401."""
    if not cs_sessao:
        raise HTTPException(401, "Faça login para continuar.")
    try:
        dados = jwt.decode(cs_sessao, CHAVE_SECRETA, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Sessão expirada. Entre novamente.")
    usuario = banco.get(Usuario, int(dados["sub"]))
    if not usuario:
        raise HTTPException(401, "Conta não encontrada.")
    return usuario
