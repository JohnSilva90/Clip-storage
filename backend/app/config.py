"""Configurações do Clip Storage, lidas do arquivo .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

PASTA_BACKEND = Path(__file__).resolve().parent.parent
PASTA_SITE = PASTA_BACKEND.parent          # onde estão index.html, painel.html...
PASTA_DADOS = PASTA_BACKEND / "dados"      # banco, vídeos enviados e cortes
PASTA_UPLOADS = PASTA_DADOS / "uploads"
PASTA_CORTES = PASTA_DADOS / "cortes"

load_dotenv(PASTA_BACKEND / ".env")

CHAVE_SECRETA = os.getenv("CHAVE_SECRETA", "chave-de-desenvolvimento-troque-no-env")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODELO_CLAUDE = os.getenv("MODELO_CLAUDE", "claude-haiku-5-5")
WHISPER_MODELO = os.getenv("WHISPER_MODELO", "small")
WHISPER_DISPOSITIVO = os.getenv("WHISPER_DISPOSITIVO", "cpu")
URL_BANCO = os.getenv("URL_BANCO", f"sqlite:///{PASTA_DADOS / 'clipstorage.db'}")
DIAS_SESSAO = 30
DIAS_GUARDAR = int(os.getenv("DIAS_GUARDAR", "30"))   # projetos mais antigos são apagados (economiza disco)
FOLGA_FONTE = 30   # segundos guardados antes e depois de cada corte, para ajustar no editor

# ---------- Pagamentos (Mercado Pago) ----------
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "").strip()        # comece com as credenciais de TESTE
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "").strip()    # "assinatura secreta" dos webhooks
URL_PUBLICA = os.getenv("URL_PUBLICA", "http://localhost:8000").rstrip("/")
# Sem token do Mercado Pago, trocar de plano e comprar créditos funciona em modo simulação (só para testes)
PAGAMENTO_SIMULADO = not MP_ACCESS_TOKEN

PRECOS_PLANOS = {"criador": 29.90, "estudio": 59.90}
PACOTES_CREDITOS = {30: 9.90, 100: 27.90, 300: 74.90}

# Regras de cada plano
PLANOS = {
    "explorador": {"nome": "Explorador", "creditos": 8, "max_min": 5, "max_cortes": 5, "marca_dagua": True},
    "criador": {"nome": "Criador", "creditos": 100, "max_min": 80, "max_cortes": 30, "marca_dagua": False},
    "estudio": {"nome": "Estúdio", "creditos": 250, "max_min": 240, "max_cortes": 50, "marca_dagua": False},
}

for pasta in (PASTA_DADOS, PASTA_UPLOADS, PASTA_CORTES):
    pasta.mkdir(parents=True, exist_ok=True)
