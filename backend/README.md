# ⚙️ Clip Storage: servidor

Servidor em **Python + FastAPI** que transforma um vídeo longo em cortes curtos:

1. Recebe o vídeo enviado pelo site, ou baixa pelo link (YouTube, Twitch, Kick), só o trecho escolhido.
2. **Transcreve o áudio** com o [faster-whisper](https://github.com/SYSTRAN/faster-whisper), que roda no seu computador e é grátis.
3. **Escolhe os melhores trechos.** Com a chave da Anthropic, o Claude lê a transcrição e escolhe. Sem chave, o modo grátis procura os trechos com mais energia na voz.
4. **Corta com FFmpeg**: formato vertical 9:16 (ou 1:1 e 16:9), legenda animada palavra por palavra e marca d'água no plano grátis.

## 🪟 Como rodar no Windows

### 1. Instale o que precisa (uma vez só)

Abra o **PowerShell** e rode:

```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
winget install DenoLand.Deno
```

> O **Deno** é usado pelo yt-dlp para ler links do YouTube.

> Use o **Python 3.12**. O 3.14 ainda não tem as bibliotecas de IA. O `iniciar.bat` já escolhe o 3.12 sozinho, mesmo que você tenha outras versões instaladas.

Feche e abra o PowerShell de novo para ele reconhecer os programas.

### 2. Ligue o servidor

Dê **dois cliques em `iniciar.bat`**, dentro desta pasta `backend`.

Na primeira vez ele cria o ambiente Python e instala as bibliotecas, o que leva alguns minutos. Depois abre o site em **http://localhost:8000**.

> Na primeira transcrição, o faster-whisper baixa o modelo de IA (cerca de 500 MB no modelo `small`). Isso só acontece uma vez.

### 3. (Opcional) Configure o `.env`

O `iniciar.bat` cria o arquivo `.env` a partir do `configuracao-exemplo.txt`. Abra ele no VS Code e ajuste:

| Variável | O que faz |
|---|---|
| `CHAVE_SECRETA` | Troque por um texto grande e aleatório (protege os logins) |
| `ANTHROPIC_API_KEY` | Sua chave da API da Anthropic, para a IA escolher os trechos (fica só no seu computador) |
| `WHISPER_MODELO` | `tiny`, `base`, `small` ou `medium` (maior = mais preciso e mais lento) |
| `WHISPER_DISPOSITIVO` | `cpu`, ou `cuda` se você tiver placa NVIDIA com CUDA configurado |

⚠️ **Nunca suba o `.env` para o GitHub.** O `.gitignore` já impede isso.

## 💳 Pagamentos (Mercado Pago)

Sem configurar nada, comprar créditos e trocar de plano funcionam em **modo simulação**, sem cobrança, para você testar.

Para cobrar de verdade (Pix, cartão e boleto nos pacotes, e cartão recorrente nas assinaturas):

1. Crie uma conta em **mercadopago.com.br/developers** e, em **Suas integrações**, crie uma aplicação ("Pagamentos online").
2. Em **Credenciais de teste**, copie o **Access Token** e cole no `.env` em `MP_ACCESS_TOKEN=`.
3. Reinicie o servidor e teste com os [cartões de teste do Mercado Pago](https://www.mercadopago.com.br/developers/pt/docs/checkout-pro/additional-content/your-integrations/test/cards).
4. **No lançamento** (com o site num endereço público):
   - troque para o Access Token de **produção**;
   - coloque o endereço do site em `URL_PUBLICA=` (ex.: `https://clipstorage.com.br`);
   - em **Webhooks**, cadastre `https://SEU-SITE/api/pagamentos/webhook` com os eventos *Pagamentos* e *Planos e assinaturas*, e cole a **assinatura secreta** em `MP_WEBHOOK_SECRET=`.

🔒 **Segurança:** os créditos e o plano só são liberados quando o Mercado Pago confirma o pagamento. O sistema confere o valor pago, recusa avisos falsos (assinatura HMAC) e nunca libera o mesmo pedido duas vezes.

### Testes automáticos

```powershell
.venv\Scripts\activate
pip install pytest
python -m pytest testes
```

## 🧭 Endpoints da API

Com o servidor ligado, a documentação interativa fica em **http://localhost:8000/docs**.

| Método | Rota | O que faz |
|---|---|---|
| POST | `/api/auth/cadastro` | Cria conta (8 créditos grátis) |
| POST | `/api/auth/login` | Entra (cookie seguro httpOnly) |
| GET | `/api/auth/eu` | Dados da conta logada |
| POST | `/api/projetos` | Envia um vídeo e coloca na fila |
| POST | `/api/projetos/link/info` | Lê título e duração de um link (YouTube, Twitch, Kick ou .mp4) |
| POST | `/api/projetos/link` | Cria projeto a partir de um link (baixa só o trecho escolhido) |
| GET | `/api/projetos` | Lista os projetos com status e progresso |
| GET | `/api/projetos/{id}` | Detalhes e cortes (com a legenda palavra por palavra) |
| PATCH | `/api/cortes/{id}` | Edita trecho, estilo, cor, posição, formato e texto |
| POST | `/api/cortes/{id}/exportar` | Gera o vídeo final em 1080p com legenda |
| GET | `/api/cortes/{id}/baixar` | Baixa o corte |
| GET | `/api/conta/historico` | Histórico de créditos |
| POST | `/api/pagamentos/creditos` | Compra um pacote de créditos (abre o checkout) |
| POST | `/api/pagamentos/assinatura` | Assina um plano (abre o checkout) |
| POST | `/api/pagamentos/cancelar` | Cancela a assinatura |
| GET | `/api/pagamentos/pedido/{ref}` | Confere se o pagamento foi aprovado |
| POST | `/api/pagamentos/webhook` | Avisos do Mercado Pago |

## 📁 Estrutura

```
backend/
├── app/
│   ├── main.py            # inicia o servidor e serve o site
│   ├── config.py          # configurações e regras dos planos
│   ├── database.py        # conexão com o banco (SQLite)
│   ├── models.py          # tabelas: usuários, projetos, cortes, créditos
│   ├── seguranca.py       # senhas (bcrypt) e login (JWT em cookie)
│   ├── mercadopago.py     # integração com o Mercado Pago
│   ├── rotas/             # auth, projetos, cortes, conta, pagamentos
│   └── processamento/
│       ├── fila.py        # trabalhador que processa os vídeos em segundo plano
│       ├── download.py    # importação por link (yt-dlp)
│       ├── video.py       # FFmpeg: duração, áudio, volume, corte
│       ├── transcricao.py # faster-whisper
│       ├── destaques.py   # escolha dos trechos (Claude ou volume)
│       └── legendas.py    # legenda animada .ASS
├── testes/                # testes automáticos (pytest)
├── dados/                 # banco e vídeos (criada sozinha, fora do Git)
├── requirements.txt     # bibliotecas principais
├── requirements-ia.txt  # transcrição (faster-whisper)
├── configuracao-exemplo.txt
└── iniciar.bat / iniciar.sh
```

## 🔜 Ainda simulado (próximas fases)

- **Publicação direta** nas redes, **views reais** e **campeonatos** (Fase 4)
- Armazenamento na nuvem (Cloudflare R2/S3) e banco PostgreSQL, para o lançamento
