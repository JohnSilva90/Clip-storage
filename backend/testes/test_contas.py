"""Conta do dono: créditos ilimitados."""
import os

from fastapi.testclient import TestClient

from app import contas
from app.main import app


def test_conta_ilimitada(monkeypatch):
    dono = f"dono{os.urandom(3).hex()}@exemplo.com"
    monkeypatch.setattr(contas, "CONTAS_ILIMITADAS", {dono})
    with TestClient(app) as c:
        c.post("/api/auth/cadastro", json={"nome": "Dono", "email": dono.upper(), "senha": "Senha@123"})
        eu = c.get("/api/auth/eu").json()
        assert eu["ilimitado"] is True and eu["creditos"] == contas.SALDO_ILIMITADO
        assert eu["max_min"] == 600 and eu["marca_dagua"] is False
    with TestClient(app) as outro:
        outro.post("/api/auth/cadastro", json={"nome": "Outro", "email": f"o{os.urandom(3).hex()}@t.com", "senha": "Senha@123"})
        eu2 = outro.get("/api/auth/eu").json()
        assert eu2["ilimitado"] is False and eu2["creditos"] == 8
