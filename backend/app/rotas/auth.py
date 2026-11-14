"""Cadastro, login, logout e dados da conta."""
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..contas import ilimitado, plano_de, saldo
from ..config import DIAS_SESSAO, PLANOS
from ..database import obter_banco
from ..models import MovimentoCredito, Usuario
from ..seguranca import NOME_COOKIE, conferir_senha, criar_token, gerar_hash, usuario_logado

rotas = APIRouter(prefix="/api/auth", tags=["Contas"])
EMAIL_OK = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


class Cadastro(BaseModel):
    nome: str = Field(min_length=2, max_length=80)
    email: str
    senha: str = Field(min_length=8, max_length=128)


class Login(BaseModel):
    email: str
    senha: str
    lembrar: bool = True


def dados_usuario(u: Usuario) -> dict:
    plano = plano_de(u)
    return {"id": u.id, "nome": u.nome, "email": u.email, "plano": u.plano, "plano_nome": plano["nome"],
            "creditos": saldo(u), "ilimitado": ilimitado(u), "creditos_plano": plano["creditos"], "max_min": plano["max_min"],
            "marca_dagua": plano["marca_dagua"], "assinante": bool(u.assinatura_mp_id),
            "plano_ate": u.plano_ate.isoformat() if u.plano_ate else None}


def abrir_sessao(resposta: Response, usuario: Usuario, lembrar: bool = True):
    dias = DIAS_SESSAO if lembrar else 1
    resposta.set_cookie(NOME_COOKIE, criar_token(usuario.id, dias), httponly=True, samesite="lax",
                        max_age=dias * 86400 if lembrar else None)


@rotas.post("/cadastro")
def cadastrar(dados: Cadastro, resposta: Response, banco: Session = Depends(obter_banco)):
    email = dados.email.strip().lower()
    if not EMAIL_OK.match(email):
        raise HTTPException(400, "E-mail inválido.")
    if banco.scalar(select(Usuario).where(Usuario.email == email)):
        raise HTTPException(409, "Já existe uma conta com esse e-mail.")
    usuario = Usuario(nome=dados.nome.strip(), email=email, senha_hash=gerar_hash(dados.senha),
                      plano="explorador", creditos=PLANOS["explorador"]["creditos"])
    usuario.movimentos.append(MovimentoCredito(quantidade=usuario.creditos, descricao="Créditos de boas-vindas"))
    banco.add(usuario)
    banco.commit()
    abrir_sessao(resposta, usuario)
    return dados_usuario(usuario)


@rotas.post("/login")
def entrar(dados: Login, resposta: Response, banco: Session = Depends(obter_banco)):
    usuario = banco.scalar(select(Usuario).where(Usuario.email == dados.email.strip().lower()))
    if not usuario or not conferir_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(401, "E-mail ou senha incorretos.")
    abrir_sessao(resposta, usuario, dados.lembrar)
    return dados_usuario(usuario)


@rotas.post("/sair")
def sair(resposta: Response):
    resposta.delete_cookie(NOME_COOKIE)
    return {"ok": True}


@rotas.get("/eu")
def eu(usuario: Usuario = Depends(usuario_logado)):
    return dados_usuario(usuario)
