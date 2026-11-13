"""Configuração comum dos testes: banco temporário e Mercado Pago de mentira."""
import os
import tempfile

os.environ["URL_BANCO"] = f"sqlite:///{tempfile.mkdtemp()}/teste.db"
os.environ["MP_ACCESS_TOKEN"] = "TEST-token-falso"
os.environ["MP_WEBHOOK_SECRET"] = "segredo-teste"
