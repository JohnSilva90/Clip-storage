"""Conversa com a API do Mercado Pago: Checkout Pro pela API de Orders (pacotes) e Assinaturas (planos)."""
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request

from .config import MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, URL_PUBLICA

log = logging.getLogger("clipstorage.mercadopago")
API = "https://api.mercadopago.com"


class ErroPagamento(Exception):
    pass


def _cabecalhos(chave_unica: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    if chave_unica:
        h["X-Idempotency-Key"] = chave_unica   # evita cobrança duplicada se o pedido for reenviado
    return h


def _req(metodo: str, caminho: str, corpo: dict | None = None, chave_unica: str | None = None) -> dict:
    """Chamada HTTP usando só a biblioteca padrão do Python (sem dependências extras)."""
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(API + caminho, data=dados, method=metodo, headers=_cabecalhos(chave_unica))
    try:
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            return json.loads(resposta.read().decode() or "{}")
    except urllib.error.HTTPError as erro:
        log.error("Mercado Pago %s %s -> %s %s", metodo, caminho, erro.code, erro.read()[:500])
        raise ErroPagamento("O Mercado Pago recusou a operação. Tente de novo em instantes.")
    except (urllib.error.URLError, TimeoutError) as erro:
        raise ErroPagamento(f"Sem conexão com o Mercado Pago: {erro}")


def _url_aviso() -> str | None:
    # O Mercado Pago só consegue avisar um endereço público (não funciona com localhost)
    return None if "localhost" in URL_PUBLICA or "127.0.0.1" in URL_PUBLICA else f"{URL_PUBLICA}/api/pagamentos/webhook"


def _local() -> bool:
    return "localhost" in URL_PUBLICA or "127.0.0.1" in URL_PUBLICA


def criar_checkout(referencia: str, titulo: str, valor: float, email: str) -> tuple[str, str]:
    """Pagamento único (pacote de créditos) pela API de Orders do Checkout Pro.
    Devolve (id da order, link do checkout com Pix, cartão e boleto)."""
    total = f"{valor:.2f}"
    volta = f"{URL_PUBLICA}/assinatura.html?pedido={referencia}"
    corpo = {
        "type": "online",
        "processing_mode": "manual",
        "total_amount": total,
        "external_reference": referencia,
        "description": titulo,
        "payer": {"email": email},
        "items": [{"title": titulo, "unit_price": total, "quantity": 1}],
        "config": {
            "statement_descriptor": "CLIPSTORAGE",
            "online": {"success_url": volta, "failure_url": volta, "pending_url": volta},
        },
    }
    if not _local():
        corpo["config"]["online"]["auto_return"] = "approved"
    try:
        dados = _req("POST", "/v1/orders", corpo, chave_unica=referencia)
    except ErroPagamento:
        if not _local():
            raise
        # No PC o Mercado Pago pode recusar endereços "localhost": tenta sem a volta automática
        corpo["config"].pop("online")
        dados = _req("POST", "/v1/orders", corpo, chave_unica=referencia + "-b")
    return str(dados["id"]), dados["checkout_url"]


def buscar_order(order_id: str) -> dict:
    return _req("GET", f"/v1/orders/{order_id}")


def criar_assinatura(referencia: str, titulo: str, valor: float, email: str) -> tuple[str, str]:
    """Assinatura mensal no cartão. Devolve (id da assinatura, link para o cliente autorizar)."""
    corpo = {
        "reason": titulo,
        "external_reference": referencia,
        "payer_email": email,
        "auto_recurring": {"frequency": 1, "frequency_type": "months", "transaction_amount": round(valor, 2), "currency_id": "BRL"},
        "back_url": f"{URL_PUBLICA}/assinatura.html?pedido={referencia}",
        "status": "pending",
    }
    if _url_aviso():
        corpo["notification_url"] = _url_aviso()
    dados = _req("POST", "/preapproval", corpo, chave_unica=referencia)
    return str(dados["id"]), dados["init_point"]


def buscar_pagamento(pagamento_id: str) -> dict:
    return _req("GET", f"/v1/payments/{pagamento_id}")


def pagamentos_da_referencia(referencia: str) -> list[dict]:
    return _req("GET", f"/v1/payments/search?external_reference={referencia}&sort=date_created&criteria=desc").get("results", [])


def buscar_assinatura(assinatura_id: str) -> dict:
    return _req("GET", f"/preapproval/{assinatura_id}")


def buscar_cobranca_assinatura(cobranca_id: str) -> dict:
    return _req("GET", f"/authorized_payments/{cobranca_id}")


def cancelar_assinatura(assinatura_id: str) -> dict:
    return _req("PUT", f"/preapproval/{assinatura_id}", {"status": "cancelled"})


def conta() -> dict:
    """Dados da conta dona do token (usado pelo verificar_mercadopago.py)."""
    return _req("GET", "/users/me")


def url_aviso() -> str | None:
    return _url_aviso()


def assinatura_valida(cabecalho_assinatura: str | None, id_requisicao: str | None, id_dado: str | None) -> bool:
    """Confere se o aviso (webhook) veio mesmo do Mercado Pago, pela assinatura HMAC."""
    if not MP_WEBHOOK_SECRET:
        # Sem segredo só é aceito rodando no PC (http). No site de verdade (https) o segredo é obrigatório.
        if URL_PUBLICA.startswith("https://"):
            log.error("MP_WEBHOOK_SECRET não configurado: aviso recusado por segurança.")
            return False
        return True
    if not cabecalho_assinatura:
        return False
    partes = dict(p.split("=", 1) for p in cabecalho_assinatura.split(",") if "=" in p)
    ts, v1 = partes.get("ts", "").strip(), partes.get("v1", "").strip()
    modelo = ""
    if id_dado:
        modelo += f"id:{str(id_dado).lower()};"
    if id_requisicao:
        modelo += f"request-id:{id_requisicao};"
    modelo += f"ts:{ts};"
    esperado = hmac.new(MP_WEBHOOK_SECRET.encode(), modelo.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)
