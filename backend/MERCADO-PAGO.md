# Ligando os pagamentos do Mercado Pago

Este guia é para **depois que o site estiver no ar na VPS, com https**. No seu PC os pagamentos
ficam em modo simulação (nada é cobrado), e é assim que deve ficar.

A ordem é sempre: **1) testar com dinheiro de mentira → 2) ligar a cobrança de verdade.**

> **Segurança:** o Access Token e a assinatura secreta são como a senha da sua conta do Mercado Pago.
> Eles vão **só** no arquivo `.env` do servidor. Nunca mande no chat, em print ou no GitHub.
> Se vazar, gere outro no painel na hora (Credenciais > Renovar).

---

## Antes de começar (uma vez só)

1. **Conta do Mercado Pago** no seu nome (CPF serve para começar).
2. **Chave Pix cadastrada** na conta do Mercado Pago. Sem ela, o Pix não aparece no checkout.
3. **Termos de uso e Política de privacidade** preenchidos (`termos.html` e `privacidade.html` estão
   com campos `[ENTRE COLCHETES]` para trocar). O Mercado Pago pode pedir o link deles.

## Passo 1: criar a aplicação

1. Entre em <https://www.mercadopago.com.br/developers> com a sua conta e clique em **Suas integrações**.
2. **Criar aplicação**. Nome: `Clip Storage`.
3. Tipo de solução: **Pagamentos online** e escolha **Checkout Pro**. Se perguntar sobre
   assinaturas/pagamentos recorrentes, marque também.
4. Aceite os termos e crie.

## Passo 2: testar com dinheiro de mentira

### 2.1 Credenciais de teste
Na aplicação: **Testes > Credenciais de teste**. Copie o **Access Token** (começa com `APP_USR-`).

### 2.2 Avisos (webhooks)
Na aplicação: **Webhooks > Configurar notificações**.
- **URL** (modo de teste): `https://SEU-SITE/api/pagamentos/webhook`
- **Eventos:** marque **Pagamentos** e **Planos e assinaturas**.
- Salve. Vai aparecer uma **assinatura secreta**: copie.

### 2.3 Colocar no servidor
No `.env` do servidor:
```
MP_ACCESS_TOKEN=APP_USR-...(token de teste)
MP_WEBHOOK_SECRET=...(assinatura secreta)
URL_PUBLICA=https://SEU-SITE
```
Reinicie o Clip Storage e confira:
```
python verificar_mercadopago.py
```
Ele diz se o token funciona, se é conta de teste e qual URL cadastrar. Tem que terminar com **Tudo certo!**

### 2.4 Fazer compras de teste
1. Na aplicação: **Contas de teste > Comprador**. Anote o usuário, a senha e o e-mail.
2. No Clip Storage, crie uma conta usando o **e-mail do comprador de teste**
   (o Mercado Pago exige que vendedor e comprador sejam ambos de teste).
3. Compre o pacote de 30 créditos. No checkout, entre com o comprador de teste e pague com um
   **cartão de teste** (Testes > Cartões de teste), usando como nome do titular:
   - `APRO` → aprovado: os créditos têm que aparecer em segundos
   - `OTHE` → recusado: o site tem que avisar que não foi aprovado
4. Assine o plano Criador do mesmo jeito: o plano e os 100 créditos têm que aparecer.
5. Cancele a assinatura: o plano tem que continuar, com a data "vale até ...".

Tudo certo? Pode ir para produção.

## Passo 3: ligar a cobrança de verdade

1. Na aplicação: **Produção > Credenciais de produção > Ativar credenciais**. Preencha o que pedirem
   (ramo: software/serviços digitais; site: o endereço do Clip Storage).
2. Copie o **Access Token de produção**.
3. Em **Webhooks**, troque para **modo produção**, coloque a mesma URL, os mesmos eventos e salve.
   Copie a **nova** assinatura secreta.
4. Troque os dois valores no `.env`, reinicie e rode `python verificar_mercadopago.py` de novo
   (agora tem que dizer "conta REAL").
5. **Compra real pequena:** com a sua conta pessoal, compre o pacote de R$ 9,90 com Pix.
   - Os créditos têm que cair.
   - Depois, devolva esse pagamento pelo painel do Mercado Pago (Atividade > o pagamento > Devolver).
     Os 30 créditos têm que **sair** da conta: isso prova que o estorno funciona.

Pronto, está vendendo.

---

## O que o site faz sozinho

| Situação | O que acontece |
|---|---|
| Pagou pacote (Pix, cartão, boleto) | Créditos liberados assim que o Mercado Pago confirma |
| Pix/boleto gerado e não pago | Fica pendente; depois de 3 dias vira "expirado" |
| Pagamento recusado | O site avisa; nada é liberado |
| Assinou um plano | Plano e créditos ativados; todo mês, na cobrança, os créditos voltam ao total |
| Trocou de plano | A assinatura antiga só é cancelada **depois** que a nova for paga |
| Cancelou (no site ou no app do Mercado Pago) | Não é mais cobrado; o plano vale até o fim do mês pago e depois volta ao grátis |
| Cartão da assinatura falhou e o Mercado Pago desistiu | Mesmo caso do cancelamento |
| Devolução ou contestação (chargeback) de pacote | Tira os créditos que ainda sobram |
| Um aviso do Mercado Pago se perdeu | De hora em hora o site confere os pedidos pendentes |
| Aviso falso tentando liberar créditos | Recusado (confere a assinatura secreta e o valor pago) |

## Problemas comuns

- **"Uma das partes é de teste"**: em modo de teste, use a conta do comprador de teste (passo 2.4).
- **Pagou e os créditos não caíram**: rode `verificar_mercadopago.py`; confira a URL dos webhooks e
  se a assinatura secreta do `.env` é a do modo certo (teste ou produção têm segredos diferentes).
  Em até 1 hora a conferência automática libera mesmo assim.
- **Pix não aparece no checkout**: cadastre uma chave Pix na sua conta do Mercado Pago.
