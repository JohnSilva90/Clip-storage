"""Confere se o Mercado Pago está configurado certo, sem cobrar nada.

Rode na pasta backend:   python verificar_mercadopago.py
(no Windows: .venv\\Scripts\\python verificar_mercadopago.py)
"""
import sys

from app import mercadopago as mp
from app.config import MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, PACOTES_CREDITOS, PRECOS_PLANOS, URL_PUBLICA

OK, AVISO, ERRO = "  [OK]   ", "  [!]    ", "  [ERRO] "
problemas = 0


def linha(tipo, texto):
    global problemas
    if tipo == ERRO:
        problemas += 1
    print(tipo + texto)


print("\nClip Storage - conferindo o Mercado Pago\n")

if not MP_ACCESS_TOKEN:
    linha(AVISO, "MP_ACCESS_TOKEN vazio: os pagamentos estão em MODO SIMULAÇÃO (nada é cobrado).")
    print("\nPreencha o MP_ACCESS_TOKEN no arquivo .env para ligar os pagamentos de verdade.\n")
    sys.exit(0)

linha(OK, "Token encontrado.")
teste = MP_ACCESS_TOKEN.startswith("TEST-")

try:
    conta = mp.conta()
    apelido = str(conta.get("nickname") or conta.get("id"))
    teste = teste or apelido.upper().startswith("TEST")
    linha(OK, f"O Mercado Pago aceitou o token. Conta: {apelido} (país: {conta.get('site_id', '?')}).")
    linha(OK if teste else AVISO, "É uma conta de TESTE (nada é cobrado de verdade)." if teste
          else "É a sua conta REAL: as compras cobram dinheiro de verdade.")
    if conta.get("site_id") not in (None, "MLB"):
        linha(ERRO, "Essa conta não é do Brasil (MLB). Pix e preços em R$ só funcionam com conta brasileira.")
except mp.ErroPagamento as erro:
    if "Sem conexão" in str(erro):
        linha(ERRO, f"Não consegui falar com o Mercado Pago (internet do servidor?): {erro}")
    else:
        linha(ERRO, "O Mercado Pago recusou o token. Confira se copiou o Access Token inteiro, sem espaços.")

if URL_PUBLICA.startswith("https://"):
    linha(OK, f"Endereço público: {URL_PUBLICA}")
else:
    linha(AVISO if teste else ERRO, f"URL_PUBLICA é '{URL_PUBLICA}'. No site de verdade precisa ser https://...")

if MP_WEBHOOK_SECRET:
    linha(OK, "Assinatura secreta dos avisos (MP_WEBHOOK_SECRET) configurada.")
else:
    linha(ERRO if URL_PUBLICA.startswith("https://") else AVISO,
          "MP_WEBHOOK_SECRET vazio. Sem ele, no https, os avisos do Mercado Pago são recusados.")

aviso = mp.url_aviso()
print("\nNo painel do Mercado Pago (Suas integrações > sua aplicação > Webhooks), cadastre:")
print(f"  URL de produção:  {aviso or '(precisa de um endereço público https)'}")
print("  Eventos:          Pagamentos  +  Planos e assinaturas")
print("\nPreços que o site vai cobrar:")
def reais(v):
    return f"R$ {v:.2f}".replace(".", ",")


for qtd, valor in PACOTES_CREDITOS.items():
    print(f"  {qtd} créditos: {reais(valor)}")
for plano, valor in PRECOS_PLANOS.items():
    print(f"  Plano {plano}: {reais(valor)}/mês")

print("\n" + ("Tudo certo!" if not problemas else f"{problemas} problema(s) para resolver acima.") + "\n")
sys.exit(1 if problemas else 0)
