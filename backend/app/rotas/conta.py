"""Histórico de créditos da conta. (Compras e assinaturas ficam em pagamentos.py)"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import obter_banco
from ..models import MovimentoCredito, Pedido, Usuario
from ..seguranca import usuario_logado

rotas = APIRouter(prefix="/api/conta", tags=["Conta"])


@rotas.get("/historico")
def historico(usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    movs = banco.scalars(select(MovimentoCredito).where(MovimentoCredito.usuario_id == usuario.id)
                         .order_by(MovimentoCredito.criado_em.desc()).limit(50))
    return [{"quantidade": m.quantidade, "descricao": m.descricao, "data": m.criado_em.isoformat()} for m in movs]


@rotas.get("/pedidos")
def pedidos(usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    lista = banco.scalars(select(Pedido).where(Pedido.usuario_id == usuario.id).order_by(Pedido.criado_em.desc()).limit(30))
    return [{"referencia": p.referencia, "tipo": p.tipo, "plano": p.plano, "quantidade": p.quantidade,
             "valor": p.valor, "status": p.status, "data": p.criado_em.isoformat()} for p in lista]
