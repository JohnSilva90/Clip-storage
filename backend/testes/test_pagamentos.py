"""Testes dos pagamentos (rode com: python -m pytest testes)

O Mercado Pago é "fingido" aqui: nenhum dinheiro de verdade é usado.
"""
import hashlib
import hmac
import os
import tempfile


import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import mercadopago as mp  # noqa: E402
from app.main import app  # noqa: E402

FALSO = {"pagamentos": {}, "assinaturas": {}, "cobrancas": {}}


@pytest.fixture(autouse=True)
def mp_falso(monkeypatch):
    monkeypatch.setattr(mp, "criar_checkout", lambda ref, t, v, e: f"https://mp.test/checkout/{ref}")
    monkeypatch.setattr(mp, "criar_assinatura", lambda ref, t, v, e: (f"sub_{ref}", f"https://mp.test/assinar/{ref}"))
    monkeypatch.setattr(mp, "cancelar_assinatura", lambda i: {"status": "cancelled"})
    monkeypatch.setattr(mp, "buscar_pagamento", lambda i: FALSO["pagamentos"][i])
    monkeypatch.setattr(mp, "buscar_assinatura", lambda i: FALSO["assinaturas"][i])
    monkeypatch.setattr(mp, "buscar_cobranca_assinatura", lambda i: FALSO["cobrancas"][i])
    monkeypatch.setattr(mp, "pagamentos_da_referencia",
                        lambda ref: [p for p in FALSO["pagamentos"].values() if p["external_reference"] == ref])


def assinar_webhook(id_dado, req="req-1", ts="1700000000"):
    v1 = hmac.new(b"segredo-teste", f"id:{id_dado};request-id:{req};ts:{ts};".encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": req}


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        c.post("/api/auth/cadastro", json={"nome": "Teste", "email": f"t{os.urandom(3).hex()}@t.com", "senha": "Senha@123"})
        yield c


def test_credito_so_libera_depois_do_pagamento(cliente):
    r = cliente.post("/api/pagamentos/creditos", json={"quantidade": 100}).json()
    ref = r["pedido"]
    assert r["checkout"].endswith(ref)
    assert cliente.get("/api/auth/eu").json()["creditos"] == 8        # ainda não pagou

    FALSO["pagamentos"]["111"] = {"id": 111, "status": "approved", "transaction_amount": 27.90, "external_reference": ref}
    h = assinar_webhook("111")
    assert cliente.post("/api/pagamentos/webhook", json={"type": "payment", "data": {"id": "111"}}, headers=h).status_code == 200
    assert cliente.get("/api/auth/eu").json()["creditos"] == 108

    # aviso repetido não dá crédito duas vezes
    cliente.post("/api/pagamentos/webhook", json={"type": "payment", "data": {"id": "111"}}, headers=h)
    assert cliente.get("/api/auth/eu").json()["creditos"] == 108


def test_webhook_falso_e_recusado(cliente):
    r = cliente.post("/api/pagamentos/webhook", json={"type": "payment", "data": {"id": "999"}},
                     headers={"x-signature": "ts=1,v1=errado", "x-request-id": "x"})
    assert r.status_code == 401


def test_valor_menor_nao_libera(cliente):
    ref = cliente.post("/api/pagamentos/creditos", json={"quantidade": 300}).json()["pedido"]
    FALSO["pagamentos"]["222"] = {"id": 222, "status": "approved", "transaction_amount": 1.00, "external_reference": ref}
    cliente.post("/api/pagamentos/webhook", json={"type": "payment", "data": {"id": "222"}}, headers=assinar_webhook("222"))
    assert cliente.get("/api/auth/eu").json()["creditos"] == 8


def test_verificacao_na_volta_do_checkout(cliente):
    ref = cliente.post("/api/pagamentos/creditos", json={"quantidade": 30}).json()["pedido"]
    FALSO["pagamentos"]["333"] = {"id": 333, "status": "approved", "transaction_amount": 9.90, "external_reference": ref}
    r = cliente.get(f"/api/pagamentos/pedido/{ref}").json()
    assert r["status"] == "aprovado" and r["usuario"]["creditos"] == 38


def test_assinatura_ciclo_completo(cliente):
    r = cliente.post("/api/pagamentos/assinatura", json={"plano": "criador"}).json()
    ref = r["pedido"]
    sub = f"sub_{ref}"
    assert cliente.get("/api/auth/eu").json()["plano"] == "explorador"

    FALSO["assinaturas"][sub] = {"id": sub, "status": "authorized", "external_reference": ref}
    cliente.post("/api/pagamentos/webhook", json={"type": "subscription_preapproval", "data": {"id": sub}}, headers=assinar_webhook(sub))
    eu = cliente.get("/api/auth/eu").json()
    assert eu["plano"] == "criador" and eu["creditos"] == 100 and eu["assinante"]

    # gasta créditos e chega a cobrança do mês seguinte
    from app.database import SessaoBanco
    from app.models import Usuario
    with SessaoBanco() as b:
        u = b.get(Usuario, eu["id"]); u.creditos = 12; b.commit()
    FALSO["cobrancas"]["c1"] = {"id": "c1", "status": "processed", "preapproval_id": sub}
    cliente.post("/api/pagamentos/webhook", json={"type": "subscription_authorized_payment", "data": {"id": "c1"}}, headers=assinar_webhook("c1"))
    assert cliente.get("/api/auth/eu").json()["creditos"] == 100

    # cancelou no Mercado Pago: volta ao grátis
    FALSO["assinaturas"][sub]["status"] = "cancelled"
    cliente.post("/api/pagamentos/webhook", json={"type": "subscription_preapproval", "data": {"id": sub}}, headers=assinar_webhook(sub))
    assert cliente.get("/api/auth/eu").json()["plano"] == "explorador"


def test_pacote_invalido(cliente):
    assert cliente.post("/api/pagamentos/creditos", json={"quantidade": 5000}).status_code == 400
