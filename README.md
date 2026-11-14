# 🎬 Clip Storage

**Um vídeo entra. Dezenas de cortes saem.**

Clip Storage é uma plataforma (SaaS) que transforma vídeos longos, como lives, podcasts e vídeos do YouTube, em cortes curtos para TikTok, Instagram Reels e YouTube Shorts usando inteligência artificial.

> 🚧 **Fases 1, 2 e 3 concluídas:** site completo, servidor Python que corta vídeos de verdade com IA e pagamentos pelo Mercado Pago (Pix, cartão e assinaturas). Falta a Fase 4 (redes sociais e campeonatos reais).
>
> Sem o servidor ligado (ex.: GitHub Pages), o site abre no **modo demonstração**. Com o servidor, tudo é real. Veja [`backend/README.md`](backend/README.md).

## ✨ Telas

| Página | O que tem |
|---|---|
| `index.html` | Página inicial: hero animado, como funciona, demonstração de créditos, recursos, campeonatos, planos (mensal/anual) e dúvidas |
| `login.html` | Login com validação, mostrar senha e "manter conectado" |
| `cadastro.html` | Cadastro com medidor de força da senha e plano escolhido |
| `recuperar-senha.html` | Recuperação de senha por e-mail |
| `painel.html` | Painel do criador: créditos, projetos, processamento ao vivo, melhores cortes e desempenho |
| `importar.html` | Novo projeto: envio de arquivo (lê a duração real do vídeo), link ou YouTube/Twitch/Kick, cálculo de créditos e etapas de processamento |
| `editor.html` | Editor de cortes: prévia com legenda animada, estilos, cores, posição, **enquadramento (câmera em cima, rosto, tela inteira)**, formato (9:16, 1:1, 16:9) e linha do tempo com alças |
| `assinatura.html` | Plano atual, uso de créditos, pacotes avulsos, troca de plano e histórico |
| `campeonatos.html` | Arena de campeonatos (**desativada no beta**, sem link no site) |
| `termos.html` · `privacidade.html` | Termos de uso e política de privacidade (LGPD), em modelo para revisar |

## 💰 Modelo de negócio

- **Assinaturas:** Explorador (grátis, 8 créditos), Criador (R$ 29,90/mês, 100 créditos) e Estúdio (R$ 59,90/mês, 250 créditos).
- **Créditos avulsos:** pacotes de 30, 100 e 300 créditos.
- **Campeonatos** (para depois do beta): competições por visualizações com prêmios.
- **Regra:** 1 crédito = 1 minuto de vídeo analisado.

## 🛠️ Tecnologias

- **Servidor:** Python, FastAPI, SQLAlchemy, SQLite, bcrypt, JWT, FFmpeg, faster-whisper e API do Claude
- HTML5 semântico, CSS3 (variáveis, grid, flexbox, animações) e JavaScript puro, sem frameworks
- Design system próprio em `assets/css/base.css`
- Ícones SVG próprios em `assets/js/icones.js`
- Layout responsivo (celular, tablet e computador)
- Acessibilidade: link "pular para o conteúdo", rótulos ARIA e respeito a `prefers-reduced-motion`

## 📁 Estrutura

```
├── index.html, login.html, cadastro.html, recuperar-senha.html
├── painel.html, importar.html, editor.html, assinatura.html, campeonatos.html
├── backend/   servidor Python (veja backend/README.md)
└── assets/
    ├── css/  base.css · landing.css · auth.css · app.css
    ├── js/   icones.js · api.js · main.js · auth.js · app.js · app-real.js
    └── img/  logo.svg
```

## ▶️ Como rodar

- **Só o visual (modo demonstração):** abra o `index.html` no navegador.
- **Completo, com IA de verdade:** siga o [`backend/README.md`](backend/README.md). No Windows, é dar dois cliques em `backend/iniciar.bat`.

## 🗺️ Próximas fases

1. ✅ **Site visual:** todas as telas
2. ✅ **Motor de IA:** servidor Python (FastAPI), banco de dados, contas, upload, transcrição (faster-whisper), IA escolhendo os trechos (Claude) e corte com legenda (FFmpeg)
3. ✅ **Começar a ganhar:** créditos reais, pacotes avulsos e assinaturas pelo Mercado Pago (com webhook seguro e testes automáticos), termos de uso e política de privacidade (LGPD). ⏳ Falta a hospedagem e o domínio.
4. ⏳ **Crescer:** publicação direta nas redes, painel de desempenho real, campeonatos com prêmios via Pix e painel de administrador

---

Desenvolvido por **John Herbet Silva Trindade**, estudante de Análise e Desenvolvimento de Sistemas.
