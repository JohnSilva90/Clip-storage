"""Contas do dono da plataforma: créditos ilimitados e tudo liberado.

Os e-mails ficam no .env (CONTAS_ILIMITADAS), nunca no código, porque o repositório é público.
"""
from .config import CONTAS_ILIMITADAS, PLANOS

SALDO_ILIMITADO = 99999


def ilimitado(usuario) -> bool:
    return bool(usuario and usuario.email and usuario.email.strip().lower() in CONTAS_ILIMITADAS)


def plano_de(usuario) -> dict:
    """Regras do plano do usuário (conta ilimitada: tudo do Estúdio, sem limite de duração)."""
    if ilimitado(usuario):
        return {**PLANOS["estudio"], "nome": "Ilimitado", "creditos": SALDO_ILIMITADO, "max_min": 600, "marca_dagua": False}
    return PLANOS[usuario.plano]


def saldo(usuario) -> int:
    return SALDO_ILIMITADO if ilimitado(usuario) else usuario.creditos
