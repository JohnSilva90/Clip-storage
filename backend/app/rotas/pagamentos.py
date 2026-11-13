"""Compras de créditos e assinaturas.

Regra de ouro: os créditos e o plano só são liberados quando o Mercado Pago
CONFIRMA o pagamento (pelo webhook ou pela verificação na volta do checkout).
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import mercadopago as mp
from ..config import PACOTES_CREDITOS, PAGAMENTO_SIMULADO, PLANOS, PRECOS_PLANOS
from ..database import SessaoBanco, obter_banco
from ..models import MovimentoCredito, Pedido, Usuario
from ..seguranca import usuario_logado
from .auth import dados_usuario

log = logging.getLogger("clipstorage.pagamentos")
rotas = APIRouter(prefix="/api/pagamentos", tags=["Pagamentos"])


class CompraCreditos(BaseModel):
    quantidade: int


class Assinar(BaseModel):
    plano: str


def _novo_pedido(banco, usuario, **campos) -> Pedido:
    pedido = Pedido(usuario=usuario, referencia="cs_" + uuid.uuid4().hex[:24], **campos)
    banco.add(pedido)
    banco.flush()
    return pedido


# ---------- Liberação (usada pelo webhook, pela verificação e pela simulação) ----------
def liberar_creditos(banco: Session, pedido: Pedido, mp_id: str | None = None):
    if pedido.status == "aprovado":
        return   # já liberado: nunca dá crédito duas vezes
    pedido.status, pedido.mp_id, pedido.aprovado_em = "aprovado", mp_id or pedido.mp_id, datetime.now(timezone.utc)
    pedido.usuario.creditos += pedido.quantidade
    banco.add(MovimentoCredito(usuario=pedido.usuario, quantidade=pedido.quantidade,
                               descricao=f"Pacote de {pedido.quantidade} créditos"))
    banco.commit()
    log.info("Pedido %s aprovado: +%s créditos para o usuário %s", pedido.referencia, pedido.quantidade, pedido.usuario_id)


def ativar_plano(banco: Session, pedido: Pedido, assinatura_id: str | None = None):
    usuario = pedido.usuario
    if pedido.status != "aprovado":
        pedido.status, pedido.aprovado_em = "aprovado", datetime.now(timezone.utc)
    if assinatura_id:
        pedido.mp_id = assinatura_id
        usuario.assinatura_mp_id = assinatura_id
    if usuario.plano != pedido.plano:
        usuario.plano = pedido.plano
        renovar_creditos(banco, usuario, "Plano {} ativado")
    banco.commit()


def renovar_creditos(banco: Session, usuario: Usuario, descricao: str):
    """Começo de cada ciclo: os créditos do plano voltam ao total (os avulsos que sobrarem continuam)."""
    total = PLANOS[usuario.plano]["creditos"]
    ganho = max(0, total - usuario.creditos)
    usuario.creditos = max(usuario.creditos, total)
    banco.add(MovimentoCredito(usuario=usuario, quantidade=ganho, descricao=descricao.format(PLANOS[usuario.plano]["nome"])))


def voltar_ao_gratis(banco: Session, usuario: Usuario):
    usuario.plano, usuario.assinatura_mp_id = "explorador", None
    banco.add(MovimentoCredito(usuario=usuario, quantidade=0, descricao="Assinatura encerrada: plano Explorador"))
    banco.commit()


# ---------- Rotas ----------
@rotas.get("/config")
def configuracao():
    return {"simulado": PAGAMENTO_SIMULADO, "planos": PRECOS_PLANOS, "pacotes": PACOTES_CREDITOS}


@rotas.post("/creditos")
def comprar_creditos(dados: CompraCreditos, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    if dados.quantidade not in PACOTES_CREDITOS:
        raise HTTPException(400, "Pacote inválido.")
    valor = PACOTES_CREDITOS[dados.quantidade]
    pedido = _novo_pedido(banco, usuario, tipo="creditos", quantidade=dados.quantidade, valor=valor)
    if PAGAMENTO_SIMULADO:
        liberar_creditos(banco, pedido, "simulado")
        return {"simulado": True, "usuario": dados_usuario(usuario)}
    try:
        link = mp.criar_checkout(pedido.referencia, f"Clip Storage: {dados.quantidade} créditos", valor, usuario.email)
    except mp.ErroPagamento as erro:
        banco.rollback()
        raise HTTPException(502, str(erro))
    banco.commit()
    return {"checkout": link, "pedido": pedido.referencia}


@rotas.post("/assinatura")
def assinar(dados: Assinar, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    if dados.plano not in PRECOS_PLANOS:
        raise HTTPException(400, "Plano inválido.")
    if usuario.plano == dados.plano:
        raise HTTPException(400, "Você já está nesse plano.")
    valor = PRECOS_PLANOS[dados.plano]
    pedido = _novo_pedido(banco, usuario, tipo="assinatura", plano=dados.plano, valor=valor)
    if PAGAMENTO_SIMULADO:
        ativar_plano(banco, pedido, "simulado")
        return {"simulado": True, "usuario": dados_usuario(usuario)}
    try:
        # Trocando de plano: cancela a assinatura antiga antes de criar a nova
        if usuario.assinatura_mp_id and usuario.assinatura_mp_id != "simulado":
            mp.cancelar_assinatura(usuario.assinatura_mp_id)
        assinatura_id, link = mp.criar_assinatura(pedido.referencia, f"Clip Storage: plano {PLANOS[dados.plano]['nome']}",
                                                  valor, usuario.email)
    except mp.ErroPagamento as erro:
        banco.rollback()
        raise HTTPException(502, str(erro))
    pedido.mp_id = assinatura_id
    banco.commit()
    return {"checkout": link, "pedido": pedido.referencia}


@rotas.post("/cancelar")
def cancelar(usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    if usuario.plano == "explorador":
        raise HTTPException(400, "Você já está no plano grátis.")
    if usuario.assinatura_mp_id and usuario.assinatura_mp_id != "simulado" and not PAGAMENTO_SIMULADO:
        try:
            mp.cancelar_assinatura(usuario.assinatura_mp_id)
        except mp.ErroPagamento as erro:
            raise HTTPException(502, str(erro))
    voltar_ao_gratis(banco, usuario)
    return dados_usuario(usuario)


@rotas.get("/pedido/{referencia}")
def verificar(referencia: str, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    """Chamado quando o cliente volta do checkout: confere no Mercado Pago se já pagou."""
    pedido = banco.scalar(select(Pedido).where(Pedido.referencia == referencia, Pedido.usuario_id == usuario.id))
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado.")
    if pedido.status == "pendente" and not PAGAMENTO_SIMULADO:
        try:
            if pedido.tipo == "creditos":
                for pg in mp.pagamentos_da_referencia(referencia):
                    if pg.get("status") == "approved" and float(pg.get("transaction_amount", 0)) >= pedido.valor - 0.01:
                        liberar_creditos(banco, pedido, str(pg["id"]))
                        break
                    if pg.get("status") in ("rejected", "cancelled"):
                        pedido.status = "recusado"
                        banco.commit()
            elif pedido.mp_id:
                assinatura = mp.buscar_assinatura(pedido.mp_id)
                if assinatura.get("status") == "authorized":
                    ativar_plano(banco, pedido, pedido.mp_id)
        except mp.ErroPagamento as erro:
            log.warning("Não consegui verificar o pedido %s: %s", referencia, erro)
    return {"status": pedido.status, "tipo": pedido.tipo, "usuario": dados_usuario(usuario)}


@rotas.post("/webhook")
async def webhook(request: Request, x_signature: str | None = Header(default=None), x_request_id: str | None = Header(default=None)):
    """O Mercado Pago chama esta rota quando algo muda num pagamento ou assinatura."""
    try:
        corpo = await request.json()
    except Exception:
        corpo = {}
    tipo = corpo.get("type") or request.query_params.get("type") or request.query_params.get("topic")
    id_dado = str((corpo.get("data") or {}).get("id") or request.query_params.get("data.id") or request.query_params.get("id") or "")
    if not mp.assinatura_valida(x_signature, x_request_id, id_dado):
        log.warning("Webhook com assinatura inválida recusado.")
        raise HTTPException(401, "Assinatura inválida.")
    if not id_dado:
        return {"ok": True}

    banco = SessaoBanco()
    try:
        if tipo == "payment":
            pg = mp.buscar_pagamento(id_dado)
            pedido = banco.scalar(select(Pedido).where(Pedido.referencia == pg.get("external_reference")))
            if pedido and pedido.tipo == "creditos":
                if pg.get("status") == "approved" and float(pg.get("transaction_amount", 0)) >= pedido.valor - 0.01:
                    liberar_creditos(banco, pedido, id_dado)
                elif pg.get("status") in ("rejected", "cancelled", "refunded", "charged_back") and pedido.status == "pendente":
                    pedido.status = "recusado"
                    banco.commit()

        elif tipo == "subscription_preapproval":
            assinatura = mp.buscar_assinatura(id_dado)
            pedido = banco.scalar(select(Pedido).where(Pedido.referencia == assinatura.get("external_reference")))
            if pedido:
                if assinatura.get("status") == "authorized":
                    ativar_plano(banco, pedido, id_dado)
                elif assinatura.get("status") in ("cancelled", "paused") and pedido.usuario.assinatura_mp_id == id_dado:
                    voltar_ao_gratis(banco, pedido.usuario)

        elif tipo == "subscription_authorized_payment":
            # Cobrança mensal da assinatura: renova os créditos do ciclo
            cobranca = mp.buscar_cobranca_assinatura(id_dado)
            if cobranca.get("status") in ("processed", "approved") or (cobranca.get("payment") or {}).get("status") == "approved":
                usuario = banco.scalar(select(Usuario).where(Usuario.assinatura_mp_id == str(cobranca.get("preapproval_id"))))
                if usuario:
                    renovar_creditos(banco, usuario, "Renovação mensal do plano {}")
                    banco.commit()
    except mp.ErroPagamento as erro:
        log.error("Falha ao processar webhook %s/%s: %s", tipo, id_dado, erro)
        raise HTTPException(502, "Tente de novo")   # o Mercado Pago reenvia mais tarde
    finally:
        banco.close()
    return {"ok": True}
