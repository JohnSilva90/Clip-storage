"""Compras de créditos e assinaturas.

Regra de ouro: os créditos e o plano só são liberados quando o Mercado Pago
CONFIRMA o pagamento (pelo webhook ou pela verificação na volta do checkout).
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

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
    if pedido.status in ("aprovado", "estornado"):
        return   # já liberado (ou devolvido): nunca dá crédito duas vezes
    pedido.status, pedido.mp_id, pedido.aprovado_em = "aprovado", mp_id or pedido.mp_id, datetime.now(timezone.utc)
    pedido.usuario.creditos += pedido.quantidade
    banco.add(MovimentoCredito(usuario=pedido.usuario, quantidade=pedido.quantidade,
                               descricao=f"Pacote de {pedido.quantidade} créditos"))
    banco.commit()
    log.info("Pedido %s aprovado: +%s créditos para o usuário %s", pedido.referencia, pedido.quantidade, pedido.usuario_id)


def _utc(dt: datetime | None) -> datetime | None:
    """O SQLite devolve datas sem fuso: trata como UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def ativar_plano(banco: Session, pedido: Pedido, assinatura_id: str | None = None):
    usuario = pedido.usuario
    # Aviso atrasado de uma assinatura antiga (o cliente já trocou de plano): ignora
    if pedido.status == "aprovado" and assinatura_id and usuario.assinatura_mp_id not in (None, assinatura_id):
        return
    if pedido.status != "aprovado":
        pedido.status, pedido.aprovado_em = "aprovado", _agora()
    if assinatura_id:
        antiga = usuario.assinatura_mp_id
        # Troca de plano: só cancela a assinatura antiga DEPOIS que a nova foi paga
        if antiga and antiga != assinatura_id and antiga != "simulado" and not PAGAMENTO_SIMULADO:
            try:
                mp.cancelar_assinatura(antiga)
            except mp.ErroPagamento as erro:
                log.error("Não consegui cancelar a assinatura antiga %s: %s", antiga, erro)
        pedido.mp_id = assinatura_id
        usuario.assinatura_mp_id = assinatura_id
    usuario.plano_ate = None
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
    usuario.plano, usuario.assinatura_mp_id, usuario.plano_ate = "explorador", None, None
    banco.add(MovimentoCredito(usuario=usuario, quantidade=0, descricao="Assinatura encerrada: plano Explorador"))
    banco.commit()


def fim_do_periodo_pago(banco: Session, usuario: Usuario) -> datetime:
    """Até quando o cliente já pagou: próxima cobrança no Mercado Pago, ou 30 dias após o último pagamento."""
    agora = _agora()
    if usuario.assinatura_mp_id and usuario.assinatura_mp_id != "simulado" and not PAGAMENTO_SIMULADO:
        try:
            proxima = mp.buscar_assinatura(usuario.assinatura_mp_id).get("next_payment_date")
            if proxima:
                data = _utc(datetime.fromisoformat(proxima.replace("Z", "+00:00")))
                if data > agora:
                    return min(data, agora + timedelta(days=31))
        except (mp.ErroPagamento, ValueError) as erro:
            log.warning("Sem data da próxima cobrança de %s: %s", usuario.assinatura_mp_id, erro)
    ultimo = banco.scalar(select(MovimentoCredito.criado_em).where(
        MovimentoCredito.usuario_id == usuario.id,
        MovimentoCredito.descricao.like("Plano % ativado") | MovimentoCredito.descricao.like("Renovação mensal%"),
    ).order_by(MovimentoCredito.criado_em.desc()))
    return max(agora, _utc(ultimo) + timedelta(days=30)) if ultimo else agora


def encerrar_no_fim_do_periodo(banco: Session, usuario: Usuario):
    """Cancelou: o plano continua até o fim do mês já pago e depois volta ao grátis."""
    ate = fim_do_periodo_pago(banco, usuario)
    if ate <= _agora() + timedelta(minutes=1):
        return voltar_ao_gratis(banco, usuario)
    usuario.plano_ate, usuario.assinatura_mp_id = ate, None
    banco.add(MovimentoCredito(usuario=usuario, quantidade=0,
                               descricao=f"Assinatura cancelada: plano {PLANOS[usuario.plano]['nome']} vale até {ate.astimezone(timezone(timedelta(hours=-3))):%d/%m/%Y}"))
    banco.commit()


def estornar_creditos(banco: Session, pedido: Pedido):
    """Pagamento devolvido ou contestado depois de aprovado: tira os créditos que ainda sobram."""
    if pedido.status != "aprovado":
        return
    tirar = min(pedido.usuario.creditos, pedido.quantidade)
    pedido.usuario.creditos -= tirar
    pedido.status = "estornado"
    banco.add(MovimentoCredito(usuario=pedido.usuario, quantidade=-tirar,
                               descricao=f"Estorno do pacote de {pedido.quantidade} créditos"))
    banco.commit()
    log.warning("Pedido %s estornado: -%s créditos do usuário %s", pedido.referencia, tirar, pedido.usuario_id)


def _aplicar_pagamento(banco: Session, pedido: Pedido, pg: dict):
    status = pg.get("status")
    if status == "approved" and float(pg.get("transaction_amount", 0)) >= pedido.valor - 0.01:
        liberar_creditos(banco, pedido, str(pg.get("id")))
    elif status in ("refunded", "charged_back"):
        estornar_creditos(banco, pedido)
    elif status in ("rejected", "cancelled") and pedido.status == "pendente":
        pedido.status = "recusado"
        banco.commit()


def _aplicar_order(banco: Session, pedido: Pedido, order: dict):
    """Status da order (API de Orders): processed = pago."""
    status = order.get("status")
    pago = float(order.get("total_paid_amount") or 0)
    if status == "processed" and pago >= pedido.valor - 0.01:
        liberar_creditos(banco, pedido, str(order.get("id")))
    elif status in ("refunded", "charged_back"):
        estornar_creditos(banco, pedido)
    elif status in ("canceled", "cancelled", "failed") and pedido.status == "pendente":
        pedido.status = "recusado"
        banco.commit()
    elif status == "expired" and pedido.status == "pendente":
        pedido.status = "expirado"
        banco.commit()


def conferir_pedido(banco: Session, pedido: Pedido):
    """Pergunta ao Mercado Pago como está um pedido pendente."""
    if pedido.tipo == "creditos" and (pedido.mp_id or "").upper().startswith("ORD"):
        _aplicar_order(banco, pedido, mp.buscar_order(pedido.mp_id))
    elif pedido.tipo == "creditos":
        pagamentos = mp.pagamentos_da_referencia(pedido.referencia)
        aprovado = next((p for p in pagamentos if p.get("status") == "approved"), None)
        for pg in ([aprovado] if aprovado else pagamentos[:1]):
            _aplicar_pagamento(banco, pedido, pg)
    elif pedido.mp_id:
        if mp.buscar_assinatura(pedido.mp_id).get("status") == "authorized":
            ativar_plano(banco, pedido, pedido.mp_id)


def rotina_de_pagamentos():
    """Roda de hora em hora: encerra planos cancelados que venceram e confere pedidos sem resposta
    (caso algum aviso do Mercado Pago tenha se perdido)."""
    agora = _agora()
    with SessaoBanco() as banco:
        for u in banco.scalars(select(Usuario).where(Usuario.plano_ate.is_not(None))):
            if _utc(u.plano_ate) <= agora:
                voltar_ao_gratis(banco, u)
        if PAGAMENTO_SIMULADO:
            return
        pendentes = banco.scalars(select(Pedido).where(Pedido.status == "pendente")).all()
        for pedido in pendentes:
            idade = agora - _utc(pedido.criado_em)
            if idade < timedelta(minutes=10):
                continue
            try:
                conferir_pedido(banco, pedido)
            except mp.ErroPagamento as erro:
                log.warning("Não consegui conferir o pedido %s: %s", pedido.referencia, erro)
                continue
            if pedido.status == "pendente" and idade > timedelta(days=3):
                pedido.status = "expirado"   # Pix e boleto não pagos vencem
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
        order_id, link = mp.criar_checkout(pedido.referencia, f"Clip Storage: {dados.quantidade} créditos", valor, usuario.email)
    except mp.ErroPagamento as erro:
        banco.rollback()
        raise HTTPException(502, str(erro))
    pedido.mp_id = order_id
    banco.commit()
    return {"checkout": link, "pedido": pedido.referencia}


@rotas.post("/assinatura")
def assinar(dados: Assinar, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    if dados.plano not in PRECOS_PLANOS:
        raise HTTPException(400, "Plano inválido.")
    if usuario.plano == dados.plano and not usuario.plano_ate:
        raise HTTPException(400, "Você já está nesse plano.")
    valor = PRECOS_PLANOS[dados.plano]
    pedido = _novo_pedido(banco, usuario, tipo="assinatura", plano=dados.plano, valor=valor)
    if PAGAMENTO_SIMULADO:
        ativar_plano(banco, pedido, "simulado")
        return {"simulado": True, "usuario": dados_usuario(usuario)}
    try:
        # Trocando de plano: a assinatura antiga só é cancelada quando a nova for paga (ver ativar_plano)
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
    if usuario.plano_ate:
        raise HTTPException(400, "A assinatura já está cancelada.")
    if PAGAMENTO_SIMULADO or usuario.assinatura_mp_id in (None, "simulado"):
        voltar_ao_gratis(banco, usuario)
        return dados_usuario(usuario)
    try:
        ate = fim_do_periodo_pago(banco, usuario)   # pega a data antes de cancelar no Mercado Pago
        mp.cancelar_assinatura(usuario.assinatura_mp_id)
    except mp.ErroPagamento as erro:
        raise HTTPException(502, str(erro))
    if ate <= _agora() + timedelta(minutes=1):
        voltar_ao_gratis(banco, usuario)
    else:
        usuario.plano_ate, usuario.assinatura_mp_id = ate, None
        banco.add(MovimentoCredito(usuario=usuario, quantidade=0,
                                   descricao=f"Assinatura cancelada: plano {PLANOS[usuario.plano]['nome']} vale até {ate.astimezone(timezone(timedelta(hours=-3))):%d/%m/%Y}"))
        banco.commit()
    return dados_usuario(usuario)


@rotas.get("/pedido/{referencia}")
def verificar(referencia: str, usuario: Usuario = Depends(usuario_logado), banco: Session = Depends(obter_banco)):
    """Chamado quando o cliente volta do checkout: confere no Mercado Pago se já pagou."""
    pedido = banco.scalar(select(Pedido).where(Pedido.referencia == referencia, Pedido.usuario_id == usuario.id))
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado.")
    if pedido.status == "pendente" and not PAGAMENTO_SIMULADO:
        try:
            conferir_pedido(banco, pedido)
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
        if tipo == "order":
            order = mp.buscar_order(id_dado)
            pedido = banco.scalar(select(Pedido).where(Pedido.referencia == order.get("external_reference")))
            if pedido and pedido.tipo == "creditos":
                _aplicar_order(banco, pedido, order)

        elif tipo == "payment":
            pg = mp.buscar_pagamento(id_dado)
            pedido = banco.scalar(select(Pedido).where(Pedido.referencia == pg.get("external_reference")))
            if pedido and pedido.tipo == "creditos":
                _aplicar_pagamento(banco, pedido, pg)

        elif tipo == "subscription_preapproval":
            assinatura = mp.buscar_assinatura(id_dado)
            pedido = banco.scalar(select(Pedido).where(Pedido.referencia == assinatura.get("external_reference")))
            if pedido:
                if assinatura.get("status") == "authorized":
                    ativar_plano(banco, pedido, id_dado)
                elif assinatura.get("status") in ("cancelled", "paused") and pedido.usuario.assinatura_mp_id == id_dado:
                    # Cancelada no app do Mercado Pago ou por falta de pagamento: vale até o fim do mês pago
                    encerrar_no_fim_do_periodo(banco, pedido.usuario)

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
