"""Casos de produção: troca de plano, cancelamento no fim do mês, estorno e avisos perdidos."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import mercadopago as mp
from app.database import SessaoBanco
from app.main import app
from app.models import Pedido, Usuario
from app.rotas import pagamentos

from test_pagamentos import FALSO, assinar_webhook, cliente, mp_falso  # noqa: F401  (fixtures)

CANCELADAS = []


@pytest.fixture(autouse=True)
def registra_cancelamentos(monkeypatch):
    CANCELADAS.clear()
    monkeypatch.setattr(mp, "cancelar_assinatura", lambda i: CANCELADAS.append(i) or {"status": "cancelled"})


def _assinar(cliente, plano):
    ref = cliente.post("/api/pagamentos/assinatura", json={"plano": plano}).json()["pedido"]
    sub = f"sub_{ref}"
    proxima = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
    FALSO["assinaturas"][sub] = {"id": sub, "status": "authorized", "external_reference": ref, "next_payment_date": proxima}
    return ref, sub


def _confirmar(cliente, sub):
    cliente.post("/api/pagamentos/webhook", json={"type": "subscription_preapproval", "data": {"id": sub}},
                 headers=assinar_webhook(sub))


def test_troca_de_plano_so_cancela_a_antiga_depois_de_pagar(cliente):
    _, sub1 = _assinar(cliente, "criador")
    _confirmar(cliente, sub1)
    _, sub2 = _assinar(cliente, "estudio")
    assert CANCELADAS == []                                  # abriu o checkout mas ainda não pagou
    assert cliente.get("/api/auth/eu").json()["plano"] == "criador"
    _confirmar(cliente, sub2)
    assert CANCELADAS == [sub1]
    eu = cliente.get("/api/auth/eu").json()
    assert eu["plano"] == "estudio" and eu["creditos"] == 250
    # aviso atrasado da assinatura antiga não volta o plano
    _confirmar(cliente, sub1)
    assert cliente.get("/api/auth/eu").json()["plano"] == "estudio"


def test_cancelar_mantem_plano_ate_o_fim_do_mes(cliente):
    _, sub = _assinar(cliente, "criador")
    _confirmar(cliente, sub)
    eu = cliente.post("/api/pagamentos/cancelar").json()
    assert CANCELADAS == [sub]
    assert eu["plano"] == "criador" and eu["plano_ate"] and not eu["assinante"]
    assert cliente.post("/api/pagamentos/cancelar").status_code == 400   # não cancela duas vezes

    # passou a data: a rotina de hora em hora volta para o grátis
    with SessaoBanco() as b:
        u = b.get(Usuario, eu["id"]); u.plano_ate = datetime.now(timezone.utc) - timedelta(minutes=1); b.commit()
    pagamentos.rotina_de_pagamentos()
    eu = cliente.get("/api/auth/eu").json()
    assert eu["plano"] == "explorador" and eu["plano_ate"] is None


def test_reativar_depois_de_cancelar(cliente):
    _, sub = _assinar(cliente, "criador")
    _confirmar(cliente, sub)
    cliente.post("/api/pagamentos/cancelar")
    _, sub2 = _assinar(cliente, "criador")                 # mesmo plano é permitido para reativar
    _confirmar(cliente, sub2)
    eu = cliente.get("/api/auth/eu").json()
    assert eu["plano"] == "criador" and eu["plano_ate"] is None and eu["assinante"]


def test_estorno_tira_os_creditos(cliente):
    ref = cliente.post("/api/pagamentos/creditos", json={"quantidade": 100}).json()["pedido"]
    FALSO["pagamentos"]["e1"] = {"id": "e1", "status": "approved", "transaction_amount": 27.90, "external_reference": ref}
    h = assinar_webhook("e1")
    cliente.post("/api/pagamentos/webhook", json={"type": "payment", "data": {"id": "e1"}}, headers=h)
    assert cliente.get("/api/auth/eu").json()["creditos"] == 108
    FALSO["pagamentos"]["e1"]["status"] = "charged_back"
    cliente.post("/api/pagamentos/webhook", json={"type": "payment", "data": {"id": "e1"}}, headers=h)
    assert cliente.get("/api/auth/eu").json()["creditos"] == 8
    cliente.post("/api/pagamentos/webhook", json={"type": "payment", "data": {"id": "e1"}}, headers=h)
    assert cliente.get("/api/auth/eu").json()["creditos"] == 8          # estorno não repete


def test_aviso_perdido_e_conferido_pela_rotina(cliente):
    ref = cliente.post("/api/pagamentos/creditos", json={"quantidade": 30}).json()["pedido"]
    FALSO["pagamentos"]["p1"] = {"id": "p1", "status": "approved", "transaction_amount": 9.90, "external_reference": ref}
    with SessaoBanco() as b:                                 # pedido de 15 min atrás, sem webhook
        from sqlalchemy import select
        p = b.scalar(select(Pedido).where(Pedido.referencia == ref))
        p.criado_em = datetime.now(timezone.utc) - timedelta(minutes=15); b.commit()
    pagamentos.rotina_de_pagamentos()
    assert cliente.get("/api/auth/eu").json()["creditos"] == 38


def test_pix_nao_pago_expira(cliente):
    ref = cliente.post("/api/pagamentos/creditos", json={"quantidade": 30}).json()["pedido"]
    with SessaoBanco() as b:
        from sqlalchemy import select
        p = b.scalar(select(Pedido).where(Pedido.referencia == ref))
        p.criado_em = datetime.now(timezone.utc) - timedelta(days=4); b.commit()
    pagamentos.rotina_de_pagamentos()
    assert cliente.get(f"/api/pagamentos/pedido/{ref}").json()["status"] == "expirado"


def test_site_https_exige_segredo(monkeypatch):
    monkeypatch.setattr(mp, "MP_WEBHOOK_SECRET", "")
    monkeypatch.setattr(mp, "URL_PUBLICA", "https://clipstorage.exemplo")
    assert mp.assinatura_valida(None, None, "1") is False
    monkeypatch.setattr(mp, "URL_PUBLICA", "http://localhost:8000")
    assert mp.assinatura_valida(None, None, "1") is True
