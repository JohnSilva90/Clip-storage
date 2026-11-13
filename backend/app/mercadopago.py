"""Conversa com a API do Mercado Pago (Checkout Pro para Pix/cartão e Assinaturas)."""
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


def criar_checkout(referencia: str, titulo: str, valor: float, email: str) -> str:
    """Pagamento único (pacote de créditos). Devolve o link do checkout (Pix, cartão, boleto)."""
    corpo = {
        "items": [{"title": titulo, "quantity": 1, "unit_price": round(valor, 2), "currency_id": "BRL"}],
        "payer": {"email": email},
        "external_reference": referencia,
        "back_urls": {s: f"{URL_PUBLICA}/assinatura.html?pedido={referencia}" for s in ("success", "failure", "pending")},
        "statement_descriptor": "CLIPSTORAGE",
    }
    if "localhost" not in URL_PUBLICA:
        corpo["auto_return"] = "approved"
    if _url_aviso():
        corpo["notification_url"] = _url_aviso()
    dados = _req("POST", "/checkout/preferences", corpo, chave_unica=referencia)
    return dados.get("init_point") or dados["sandbox_init_point"]


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


def assinatura_valida(cabecalho_assinatura: str | None, id_requisicao: str | None, id_dado: str | None) -> bool:
    """Confere se o aviso (webhook) veio mesmo do Mercado Pago, pela assinatura HMAC."""
    if not MP_WEBHOOK_SECRET:
        return True   # sem segredo configurado, aceita (só em testes!)
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
