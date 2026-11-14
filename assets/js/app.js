/* =========================================================
   CLIP STORAGE — Área logada
   Monta a barra lateral e o topo de todas as páginas internas
   e cuida da lógica de cada tela. Nesta fase os dados são
   simulados e ficam salvos no navegador (localStorage).
   ========================================================= */
(async function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const CHAVE = 'clipStorage.sessao';
  const app = $('.app');
  const pagina = app.dataset.pagina;

  // ---------- Sessão ----------
  function lerSessao() {
    try { return JSON.parse(localStorage.getItem(CHAVE)); } catch { return null; }
  }
  function salvarSessao() {
    try { localStorage.setItem(CHAVE, JSON.stringify(sessao)); } catch { /* sem armazenamento */ }
  }
  // Servidor ligado? Então usa a conta real. Senão, modo demonstração.
  const real = await API.verificar();
  let sessao = null;
  if (real) {
    try { sessao = await API.get('/api/auth/eu'); }
    catch { location.href = 'login.html'; return; }
  } else {
    sessao = lerSessao();
  }
  const demo = !sessao;
  if (demo) sessao = { nome: 'Criador Demo', email: 'demo@clipstorage.com', plano: 'explorador', creditos: 8 };

  const PLANOS = {
    explorador: { nome: 'Explorador', preco: 'Grátis', creditos: 8, maxMin: 5 },
    criador: { nome: 'Criador', preco: 'R$ 29,90/mês', creditos: 100, maxMin: 80 },
    estudio: { nome: 'Estúdio', preco: 'R$ 59,90/mês', creditos: 250, maxMin: 240 },
  };
  const plano = () => PLANOS[sessao.plano] || PLANOS.explorador;
  const iniciais = (n) => n.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('');

  window.avisar = function (msg) {
    const t = $('#toast');
    t.textContent = msg; t.classList.add('mostrar');
    clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('mostrar'), 2800);
  };

  // ---------- Barra lateral e topo (iguais em todas as páginas) ----------
  const LOGO = '<svg viewBox="0 0 32 32" aria-hidden="true"><rect x="10" y="2" width="12" height="3" rx="1.5" fill="#a78bfa" opacity=".35"/><rect x="6.5" y="5.5" width="19" height="3.5" rx="1.75" fill="#a78bfa" opacity=".6"/><rect x="3" y="10" width="26" height="20" rx="6" fill="#7c4df3"/><path d="M13.5 15.5v9l7.5-4.5z" fill="#fff"/><circle cx="25" cy="13.5" r="1.6" fill="#ff8a3d"/></svg>';
  const links = [
    ['painel', 'painel.html', 'casa', 'Início'],
    ['importar', 'importar.html', 'upload', 'Novo projeto'],
    ['editor', 'editor.html', 'tesoura', 'Editor de cortes'],
    // ['campeonatos', 'campeonatos.html', 'trofeu', 'Campeonatos'],  // desativado no beta
  ];
  const links2 = [
    ['assinatura', 'assinatura.html', 'cartao', 'Planos e créditos'],
  ];
  const navHtml = (lista) => lista.map(([id, href, ic, txt]) =>
    `<a href="${href}" class="${id === pagina ? 'ativo' : ''}"><i data-icone="${ic}"></i>${txt}</a>`).join('');

  $('#lateral').innerHTML = `
    <a href="index.html" class="logo">${LOGO}<span>Clip<b>Storage</b></span></a>
    <nav class="nav-app" aria-label="Área do criador">${navHtml(links)}
      <span class="nav-titulo">Conta</span>${navHtml(links2)}
    </nav>
    <div class="lateral-creditos">
      <small>Créditos disponíveis</small>
      <strong data-creditos>${sessao.creditos}</strong>
      <div class="barra"><span data-barra-creditos></span></div>
      <a href="assinatura.html" class="btn btn-destaque btn-bloco"><i data-icone="raio"></i> Mais créditos</a>
    </div>`;

  $('#topoApp').innerHTML = `
    <button class="botao-redondo menu-app-botao" id="menuApp" aria-label="Abrir menu"><i data-icone="menu"></i></button>
    <div class="busca"><div class="entrada"><i data-icone="busca"></i><input type="search" placeholder="Buscar projetos e cortes..." aria-label="Buscar"></div></div>
    <div class="topo-app-acoes">
      <span class="pilula-creditos" title="1 crédito = 1 minuto analisado"><i data-icone="raio"></i><span data-creditos>${sessao.creditos}</span> créditos</span>
      <button class="botao-redondo" id="btnNotif" aria-label="Notificações"><i data-icone="sino"></i><span class="ponto"></span></button>
      <div class="perfil">
        <button class="perfil-botao" id="perfilBotao" aria-expanded="false"><span class="perfil-avatar">${iniciais(sessao.nome)}</span><span class="perfil-nome">${sessao.nome}</span></button>
        <div class="perfil-menu" id="perfilMenu">
          <div class="info"><b></b><small></small></div>
          <a href="assinatura.html"><i data-icone="cartao"></i> Plano ${plano().nome}</a>
          <a href="#" data-em-breve><i data-icone="config"></i> Configurações</a>
          <button id="btnSair"><i data-icone="sair"></i> Sair</button>
        </div>
      </div>
    </div>`;
  $('#perfilMenu .info b').textContent = sessao.nome;
  $('#perfilMenu .info small').textContent = sessao.email;
  $('.perfil-nome').textContent = sessao.nome;

  if (demo) {
    const aviso = document.createElement('div');
    aviso.className = 'aviso-demo';
    aviso.innerHTML = '<i data-icone="brilho"></i> Você está no modo demonstração. <a href="cadastro.html" class="link" style="margin-left:auto">Criar conta grátis</a>';
    $('.conteudo-app').prepend(aviso);
  }

  function atualizarCreditos() {
    $$('[data-creditos]').forEach((el) => { el.textContent = sessao.ilimitado ? '∞' : sessao.creditos; });
    const pct = Math.min(100, (sessao.creditos / plano().creditos) * 100);
    $$('[data-barra-creditos]').forEach((el) => { el.style.width = pct + '%'; });
  }
  atualizarCreditos();

  // Menus
  const perfilMenu = $('#perfilMenu');
  $('#perfilBotao').addEventListener('click', (e) => {
    e.stopPropagation();
    const aberto = perfilMenu.classList.toggle('aberto');
    $('#perfilBotao').setAttribute('aria-expanded', aberto);
  });
  document.addEventListener('click', () => perfilMenu.classList.remove('aberto'));
  $('#btnSair').addEventListener('click', async () => {
    try { localStorage.removeItem(CHAVE); } catch { /* nada */ }
    if (real) { try { await API.post('/api/auth/sair'); } catch { /* nada */ } }
    location.href = 'login.html';
  });
  $('#btnNotif').addEventListener('click', () => avisar('Seus cortes da "Live de sexta" estão prontos!'));
  $('#menuApp').addEventListener('click', (e) => { e.stopPropagation(); $('#lateral').classList.toggle('aberta'); });
  document.addEventListener('click', (e) => { if (!e.target.closest('#lateral')) $('#lateral').classList.remove('aberta'); });
  $$('[data-em-breve]').forEach((a) => a.addEventListener('click', (e) => { e.preventDefault(); avisar('Disponível em breve.'); }));

  // ---------- Dados simulados ----------
  const GRADS = ['#5b3fc4,#1d1240', '#c25a24,#2a1208', '#1f7a64,#08201a', '#2a5bd7,#0b1636', '#b8327a,#2a0a1c', '#7a6a1f,#1f1a08'];
  const grad = (i) => `linear-gradient(170deg, ${GRADS[i % GRADS.length]})`;
  const PROJETOS = [
    { titulo: 'Live de sexta — Especial 100 mil', dur: '1:24:08', min: 85, cortes: 12, status: 'pronto', quando: 'Hoje, 14:32' },
    { titulo: 'Podcast Ep. 42 — Empreender do zero', dur: '52:10', min: 52, cortes: 0, status: 'processando', prog: 64, quando: 'Hoje, 16:05' },
    { titulo: 'Gameplay ranqueada até o mestre', dur: '2:08:00', min: 128, cortes: 0, status: 'fila', quando: 'Hoje, 16:10' },
    { titulo: 'Aula: marketing para iniciantes', dur: '38:20', min: 38, cortes: 8, status: 'pronto', quando: 'Ontem, 20:11' },
  ];
  const CORTES = [
    { leg: ['ELE', 'NÃO', 'ACREDITOU', 'NO', 'QUE', 'VIU'], nota: 98, dur: 34, views: '184 mil', ini: 1262 },
    { leg: ['O', 'SEGREDO', 'É', 'ESSE', 'AQUI'], nota: 95, dur: 41, views: '92 mil', ini: 2140 },
    { leg: ['MELHOR', 'MOMENTO', 'DA', 'LIVE'], nota: 93, dur: 28, views: '47 mil', ini: 3015 },
    { leg: ['NINGUÉM', 'TE', 'CONTA', 'ISSO'], nota: 90, dur: 52, views: '—', ini: 3720 },
    { leg: ['A', 'REAÇÃO', 'FOI', 'ÉPICA'], nota: 88, dur: 22, views: '—', ini: 4190 },
    { leg: ['PRESTA', 'ATENÇÃO', 'NESSA', 'DICA'], nota: 85, dur: 45, views: '—', ini: 4710 },
  ];
  const mmss = (s) => {
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), seg = String(Math.floor(s % 60)).padStart(2, '0');
    return h ? `${h}:${String(m).padStart(2, '0')}:${seg}` : `${m}:${seg}`;
  };

  // Com o servidor ligado, estas telas usam dados reais (arquivo app-real.js)
  if (real && ['painel', 'importar', 'editor', 'assinatura'].includes(pagina)) {
    window.AppReal.iniciar({ $, $$, sessao, pagina, avisar, grad, mmss, atualizarCreditos, iniciais, PLANOS });
    Icones.desenhar();
    return;
  }

  // =========================================================
  //   PAINEL
  // =========================================================
  if (pagina === 'painel') {
    const primeiro = sessao.nome.split(' ')[0];
    $('#saudacao').textContent = `Olá, ${primeiro}!`;
    $('#estCreditos').textContent = sessao.ilimitado ? '∞' : sessao.creditos;
    $('#estPlano').textContent = 'Plano ' + plano().nome;

    const lista = $('#listaProjetos');
    function desenharProjetos() {
      lista.innerHTML = PROJETOS.map((p, i) => `
        <a class="projeto" href="${p.status === 'pronto' ? 'editor.html' : '#'}" data-i="${i}">
          <div class="miniatura" style="background:${grad(i)}"><i data-icone="${p.status === 'pronto' ? 'play' : 'filme'}"></i><span class="duracao">${p.dur}</span></div>
          <div style="min-width:0">
            <h3></h3>
            <div class="projeto-meta"><span>${p.quando}</span><span>${p.min} créditos</span>${p.cortes ? `<span>${p.cortes} cortes</span>` : ''}</div>
            ${p.status === 'processando' ? `<div class="progresso-mini"><span style="width:${p.prog}%"></span></div>` : ''}
          </div>
          <span class="status ${p.status}">${{ pronto: 'Pronto', processando: `Processando ${p.prog}%`, fila: 'Na fila' }[p.status]}</span>
        </a>`).join('');
      $$('.projeto h3', lista).forEach((h, i) => { h.textContent = PROJETOS[i].titulo; });
      Icones.desenhar(lista);
      $$('.projeto', lista).forEach((el) => el.addEventListener('click', (e) => {
        const p = PROJETOS[el.dataset.i];
        if (p.status !== 'pronto') { e.preventDefault(); avisar('Esse projeto ainda está sendo processado.'); }
      }));
    }
    desenharProjetos();

    // Simula o processamento andando
    const timer = setInterval(() => {
      const p = PROJETOS[1];
      p.prog = Math.min(100, p.prog + 3);
      if (p.prog >= 100) { p.status = 'pronto'; p.cortes = 9; clearInterval(timer); avisar('"Podcast Ep. 42" ficou pronto: 9 cortes!'); }
      desenharProjetos();
    }, 1500);

    $('#cortesDestaque').innerHTML = CORTES.slice(0, 6).map((c, i) => `
      <a class="corte-card" href="editor.html?corte=${i}" style="background:${grad(i)}">
        <span class="nota">${c.nota}</span>
        <span class="leg">${c.leg.slice(0, -1).join(' ')} <b>${c.leg[c.leg.length - 1]}</b></span>
        <span class="vw"><i data-icone="olho"></i> ${c.views}</span>
      </a>`).join('');
    Icones.desenhar($('#cortesDestaque'));
  }

  // =========================================================
  //   IMPORTAR (novo projeto)
  // =========================================================
  if (pagina === 'importar') {
    let duracaoMin = 0, origem = 'arquivo';
    const resumoDur = $('#resumoDur'), resumoCred = $('#resumoCred'), resumoSaldo = $('#resumoSaldo'), aviso = $('#avisoResumo'), btnGerar = $('#btnGerar');

    function trecho() {
      const ini = Math.max(0, +$('#trechoIni').value || 0);
      const fim = Math.min(duracaoMin, +$('#trechoFim').value || duracaoMin);
      return Math.max(0, Math.ceil(fim - ini));
    }
    function atualizarResumo() {
      const min = duracaoMin ? trecho() : 0;
      resumoDur.textContent = min ? min + ' min' : '—';
      resumoCred.textContent = min;
      resumoSaldo.textContent = sessao.creditos - min;
      aviso.classList.remove('aviso-erro');
      btnGerar.disabled = !min;
      if (!min) { aviso.textContent = 'Escolha um vídeo para ver o custo.'; return; }
      if (min > sessao.creditos) {
        aviso.textContent = `Faltam ${min - sessao.creditos} créditos. Escolha um trecho menor ou compre mais créditos.`;
        aviso.classList.add('aviso-erro'); btnGerar.disabled = true;
      } else if (min > plano().maxMin) {
        aviso.textContent = `Seu plano analisa até ${plano().maxMin} minutos por vídeo. Escolha um trecho menor.`;
        aviso.classList.add('aviso-erro'); btnGerar.disabled = true;
      } else aviso.textContent = 'Você só paga pelos minutos analisados.';
    }
    function definirVideo(nome, info, minutos) {
      duracaoMin = minutos;
      $('#escolhidoNome').textContent = nome;
      $('#escolhidoInfo').textContent = info;
      $('#arquivoEscolhido').hidden = false;
      $('#trechoIni').value = 0;
      $('#trechoFim').value = Math.min(minutos, plano().maxMin, Math.max(1, sessao.creditos));
      $('#trechoFim').max = minutos; $('#trechoIni').max = minutos;
      $('#opcoes').hidden = false;
      atualizarResumo();
    }
    function limpar() {
      duracaoMin = 0;
      $('#arquivoEscolhido').hidden = true; $('#opcoes').hidden = true;
      atualizarResumo();
    }

    // Abas
    $$('.abas-app button').forEach((b) => b.addEventListener('click', () => {
      origem = b.dataset.origem;
      $$('.abas-app button').forEach((x) => x.classList.toggle('ativa', x === b));
      $('#painelArquivo').hidden = origem !== 'arquivo';
      $('#painelLink').hidden = origem === 'arquivo';
      $('#rotuloLink').textContent = origem === 'link' ? 'Link direto do vídeo (.mp4)' : 'Link do YouTube, Twitch ou Kick';
      $('#entradaLink').placeholder = origem === 'link' ? 'https://meusite.com/video.mp4' : 'https://youtube.com/watch?v=...';
      limpar();
    }));

    // Arquivo: clicar ou arrastar. Lê a duração real do vídeo no navegador.
    const soltar = $('#soltar'), input = $('#inputArquivo');
    soltar.addEventListener('click', () => input.click());
    soltar.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
    ['dragenter', 'dragover'].forEach((ev) => soltar.addEventListener(ev, (e) => { e.preventDefault(); soltar.classList.add('arrastando'); }));
    ['dragleave', 'drop'].forEach((ev) => soltar.addEventListener(ev, (e) => { e.preventDefault(); soltar.classList.remove('arrastando'); }));
    soltar.addEventListener('drop', (e) => { if (e.dataTransfer.files[0]) lerArquivo(e.dataTransfer.files[0]); });
    input.addEventListener('change', () => { if (input.files[0]) lerArquivo(input.files[0]); });

    function lerArquivo(arq) {
      if (!arq.type.startsWith('video/') && !/\.(mp4|mov|mkv|webm|avi)$/i.test(arq.name)) { avisar('Escolha um arquivo de vídeo.'); return; }
      const tamanho = arq.size > 1e9 ? (arq.size / 1e9).toFixed(1).replace('.', ',') + ' GB' : Math.round(arq.size / 1e6) + ' MB';
      const v = document.createElement('video');
      v.preload = 'metadata';
      v.onloadedmetadata = () => {
        const min = Math.max(1, Math.ceil(v.duration / 60));
        URL.revokeObjectURL(v.src);
        definirVideo(arq.name, `${mmss(v.duration)} · ${tamanho}`, min);
      };
      v.onerror = () => definirVideo(arq.name, `${tamanho} · duração estimada`, 30);
      v.src = URL.createObjectURL(arq);
    }
    $('#btnLimpar').addEventListener('click', limpar);

    // Link
    $('#btnLink').addEventListener('click', () => {
      const url = $('#entradaLink').value.trim();
      let ok = false;
      try { ok = /^https?:$/.test(new URL(url).protocol); } catch { ok = false; }
      if (!ok) { avisar('Cole um link válido, começando com https://'); return; }
      const host = new URL(url).hostname.replace('www.', '');
      const min = 20 + (url.length * 7) % 100; // duração simulada
      definirVideo(url, `${host} · ${Math.floor(min / 60)}h ${min % 60}min`, min);
    });

    ['trechoIni', 'trechoFim'].forEach((id) => $('#' + id).addEventListener('input', atualizarResumo));
    atualizarResumo();

    // Gerar cortes: simula as etapas do processamento
    btnGerar.addEventListener('click', () => {
      const custo = trecho();
      sessao.creditos -= custo;
      if (!demo) salvarSessao();
      atualizarCreditos();
      $('#etapaConfig').hidden = true;
      $('#etapaProc').hidden = false;
      $('#resumoBloco').hidden = true;
      const etapas = $$('#etapasProc li');
      const barra = $('#barraProc');
      let i = 0;
      (function proxima() {
        etapas.forEach((li, j) => { li.className = j < i ? 'feito' : j === i ? 'agora' : ''; });
        barra.style.width = (i / etapas.length) * 100 + '%';
        $('#textoProc').textContent = i < etapas.length ? etapas[i].dataset.texto : 'Tudo pronto!';
        if (i < etapas.length) { i++; setTimeout(proxima, 1300); }
        else {
          $('#tituloProc').textContent = 'Seus cortes estão prontos! 🎉';
          $('#btnVerCortes').hidden = false;
        }
      })();
    });
  }

  // =========================================================
  //   EDITOR
  // =========================================================
  if (pagina === 'editor') {
    const params = new URLSearchParams(location.search);
    let atual = Math.min(CORTES.length - 1, +params.get('corte') || 0);
    let tocando = false, t = 0, timer = null;
    const estado = { estilo: 'destaque', formato: '9:16', posicao: 'baixo', marca: sessao.plano === 'explorador' };
    const leg = $('#legenda'), video = $('#previewVideo');

    // Lista lateral de cortes
    $('#totalCortes').textContent = CORTES.length + ' cortes';
    $('#listaCortes').insertAdjacentHTML('beforeend', CORTES.map((c, i) => `
      <button class="item-corte" data-i="${i}">
        <span class="thumb" style="background:${grad(i)}"></span>
        <span><b>${c.leg.join(' ').toLowerCase().replace(/^./, (l) => l.toUpperCase())}</b>
        <small><span class="nota">${c.nota}</span> · ${c.dur}s · ${mmss(c.ini)}</small></span>
      </button>`).join(''));
    $$('.item-corte').forEach((b) => b.addEventListener('click', () => selecionar(+b.dataset.i)));

    function desenharLegenda() {
      const c = CORTES[atual];
      const palavras = c.leg.map((p, i) => `<span class="palavra" data-i="${i}">${p}</span>`).join(' ');
      leg.innerHTML = estado.estilo === 'classica' ? `<span class="texto-fundo">${palavras}</span>` : palavras;
      leg.className = 'preview-legenda estilo-' + estado.estilo;
      leg.style.bottom = { baixo: '22%', meio: '45%', cima: '72%' }[estado.posicao];
      $('#textoLegenda').value = c.leg.join(' ');
    }
    function selecionar(i) {
      atual = i; t = 0; pausar();
      $$('.item-corte').forEach((b) => b.classList.toggle('ativo', +b.dataset.i === i));
      $('#previewCena').style.background = grad(i);
      $('#tituloCorte').textContent = `Corte ${i + 1} · nota ${CORTES[i].nota}`;
      sel.ini = 0.3; sel.fim = 0.3 + CORTES[i].dur / 120;
      desenharLegenda(); desenharTrilha(); tick();
    }

    // Reprodução simulada (a legenda acende palavra por palavra)
    function tick() {
      const c = CORTES[atual], dur = c.dur;
      $('#tempoAtual').textContent = `${mmss(t)} / ${mmss(dur)}`;
      $('#barraPreview').style.width = (t / dur) * 100 + '%';
      const idx = Math.min(c.leg.length - 1, Math.floor((t / dur) * c.leg.length * 2) % c.leg.length);
      $$('.palavra', leg).forEach((p) => p.classList.toggle('atual', +p.dataset.i === idx));
      $('#cursorTrilha').style.left = (sel.ini + (sel.fim - sel.ini) * (t / dur)) * 100 + '%';
    }
    function tocar() {
      tocando = true; $('#btnPlay').innerHTML = Icones.svg('pausa');
      timer = setInterval(() => { t += 0.1; if (t >= CORTES[atual].dur) t = 0; tick(); }, 100);
    }
    function pausar() { tocando = false; clearInterval(timer); $('#btnPlay').innerHTML = Icones.svg('play'); }
    $('#btnPlay').addEventListener('click', () => (tocando ? pausar() : tocar()));
    $('#barraPreviewFundo').addEventListener('click', (e) => {
      const r = e.currentTarget.getBoundingClientRect();
      t = ((e.clientX - r.left) / r.width) * CORTES[atual].dur; tick();
    });

    // Linha do tempo com alças arrastáveis (início e fim do corte)
    const trilha = $('#trilha'), selecao = $('#selecao');
    const sel = { ini: 0.3, fim: 0.6 };
    const TOTAL = 84 * 60; // vídeo original de 1h24
    function desenharTrilha() {
      selecao.style.left = sel.ini * 100 + '%';
      selecao.style.width = (sel.fim - sel.ini) * 100 + '%';
      const durSel = Math.round((sel.fim - sel.ini) * 120);
      CORTES[atual].dur = Math.max(5, durSel);
      $('#infoTrecho').textContent = `${mmss(CORTES[atual].ini)} → ${mmss(CORTES[atual].ini + CORTES[atual].dur)} · ${CORTES[atual].dur}s`;
    }
    function arrastar(lado) {
      return (e) => {
        e.preventDefault();
        const r = trilha.getBoundingClientRect();
        const mover = (ev) => {
          const x = Math.min(1, Math.max(0, ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) / r.width));
          if (lado === 'ini') sel.ini = Math.min(x, sel.fim - 0.04);
          else sel.fim = Math.max(x, sel.ini + 0.04);
          desenharTrilha(); tick();
        };
        const soltar = () => { removeEventListener('pointermove', mover); removeEventListener('pointerup', soltar); };
        addEventListener('pointermove', mover); addEventListener('pointerup', soltar);
      };
    }
    $('.alca.ini').addEventListener('pointerdown', arrastar('ini'));
    $('.alca.fim').addEventListener('pointerdown', arrastar('fim'));
    $('#escalaFim').textContent = mmss(TOTAL);

    // Opções de estilo
    function grupo(id, chave, depois) {
      $$(`#${id} .opcao`).forEach((b) => b.addEventListener('click', () => {
        $$(`#${id} .opcao`).forEach((x) => x.classList.toggle('ativa', x === b));
        estado[chave] = b.dataset.valor; depois();
      }));
    }
    grupo('optEstilo', 'estilo', desenharLegenda);
    grupo('optPosicao', 'posicao', desenharLegenda);
    grupo('optFormato', 'formato', () => { video.dataset.formato = estado.formato; });
    grupo('optLayout', 'layout', () => avisar('No modo real, o vídeo é refeito com o novo enquadramento.'));
    $$('.cor').forEach((c) => c.addEventListener('click', () => {
      $$('.cor').forEach((x) => x.classList.toggle('ativa', x === c));
      document.documentElement.style.setProperty('--destaque-legenda', c.dataset.cor);
      $$('.palavra').forEach((p) => p.style.setProperty('--c', c.dataset.cor));
      leg.style.setProperty('--cor-destaque', c.dataset.cor);
      $('#estiloDinamico').textContent = `.preview-legenda.estilo-destaque .palavra.atual{background:${c.dataset.cor}}.preview-legenda.estilo-classica .palavra.atual{color:${c.dataset.cor}}.preview-legenda.estilo-neon .palavra.atual{color:${c.dataset.cor};text-shadow:0 0 8px ${c.dataset.cor},0 0 18px ${c.dataset.cor}}`;
    }));
    $('#textoLegenda').addEventListener('input', (e) => {
      const palavras = e.target.value.toUpperCase().split(/\s+/).filter(Boolean);
      CORTES[atual].leg = palavras.length ? palavras : ['...'];
      const v = e.target.value; desenharLegenda(); e.target.value = v;
    });
    const marca = $('#optMarca');
    marca.checked = estado.marca;
    $('#previewMarca').hidden = !estado.marca;
    marca.addEventListener('change', () => {
      if (sessao.plano === 'explorador' && !marca.checked) {
        marca.checked = true;
        avisar('Remover a marca d\'água é do plano Criador ou Estúdio.');
        return;
      }
      $('#previewMarca').hidden = !marca.checked;
    });

    // Baixar e publicar
    $('#btnBaixar').addEventListener('click', () => avisar(`Exportando corte em 1080p (${estado.formato})... (demonstração)`));
    const modal = $('#modalPublicar');
    $('#btnPublicar').addEventListener('click', () => modal.classList.add('aberto'));
    $$('[data-fechar]').forEach((b) => b.addEventListener('click', () => modal.classList.remove('aberto')));
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('aberto'); });
    $('#btnConfirmarPub').addEventListener('click', () => {
      const redes = $$('#modalPublicar input:checked').map((i) => i.dataset.rede);
      if (!redes.length) { avisar('Escolha pelo menos uma rede.'); return; }
      modal.classList.remove('aberto');
      avisar(`Corte enviado para ${redes.join(', ')}! (demonstração)`);
    });

    selecionar(atual);
  }

  // =========================================================
  //   PLANOS E CRÉDITOS
  // =========================================================
  if (pagina === 'assinatura') {
    const p = plano();
    $('#nomePlanoAtual').textContent = p.nome;
    $('#precoPlanoAtual').textContent = p.preco;
    $('#credAtual').textContent = sessao.creditos;
    $('#credTotal').textContent = p.creditos;
    $('#barraUso').style.width = Math.min(100, (sessao.creditos / p.creditos) * 100) + '%';
    $$('.plano-app').forEach((card) => {
      const atual = card.dataset.plano === sessao.plano;
      card.classList.toggle('atual', atual);
      const btn = $('.btn', card);
      if (atual) { btn.textContent = 'Plano atual'; btn.disabled = true; btn.className = 'btn btn-contorno btn-bloco'; }
      btn.addEventListener('click', () => {
        if (atual) return;
        sessao.plano = card.dataset.plano;
        sessao.creditos = PLANOS[sessao.plano].creditos;
        if (!demo) salvarSessao();
        avisar(`Plano alterado para ${PLANOS[sessao.plano].nome}! (simulação: o pagamento entra na Fase 3)`);
        setTimeout(() => location.reload(), 1400);
      });
    });
    $$('.pacote').forEach((pc) => pc.addEventListener('click', () => {
      $$('.pacote').forEach((x) => x.classList.toggle('ativo', x === pc));
      $('#btnComprar').textContent = `Comprar ${pc.dataset.qtd} créditos por ${pc.dataset.preco}`;
      $('#btnComprar').disabled = false;
      $('#btnComprar').dataset.qtd = pc.dataset.qtd;
    }));
    $('#btnComprar').addEventListener('click', (e) => {
      const qtd = +e.currentTarget.dataset.qtd;
      if (!qtd) return;
      sessao.creditos += qtd;
      if (!demo) salvarSessao();
      atualizarCreditos();
      $('#credAtual').textContent = sessao.creditos;
      avisar(`+${qtd} créditos adicionados! (simulação)`);
    });
  }

  // =========================================================
  //   CAMPEONATOS
  // =========================================================
  if (pagina === 'campeonatos') {
    const CAMPS = [
      { titulo: 'Copa dos Cortes de Podcast', desc: 'Cortes de podcasts brasileiros de entrevista e humor.', premio: 'R$ 3.000', status: 'aberto', fim: 'Termina em 4 dias', part: 312, req: 'Plano Criador ou Estúdio', g: 0 },
      { titulo: 'Desafio Gameplay Épico', desc: 'Os melhores momentos de lives de jogos, em formato vertical.', premio: 'R$ 2.000', status: 'aberto', fim: 'Termina em 9 dias', part: 188, req: 'Plano Criador ou Estúdio', g: 3 },
      { titulo: 'Liga dos Educadores', desc: 'Cortes de aulas e dicas que ensinam algo em menos de 60 segundos.', premio: 'R$ 1.500', status: 'breve', fim: 'Começa em 3 dias', part: 0, req: 'Plano Estúdio', g: 2 },
      { titulo: 'Maratona de Humor', desc: 'Cortes de stand-up, reacts e momentos engraçados.', premio: 'R$ 2.500', status: 'encerrado', fim: 'Encerrado em 02/11', part: 540, req: 'Plano Criador ou Estúdio', g: 1 },
    ];
    const ROTULO = { aberto: 'Inscrições abertas', breve: 'Em breve', encerrado: 'Encerrado' };
    const inscritos = new Set();
    let filtro = 'todos';
    function desenhar() {
      const lista = CAMPS.filter((c) => filtro === 'todos' || c.status === filtro);
      $('#listaCamps').innerHTML = lista.map((c) => {
        const i = CAMPS.indexOf(c);
        const insc = inscritos.has(i);
        const botao = c.status === 'aberto'
          ? `<button class="btn ${insc ? 'btn-contorno' : 'btn-destaque'} btn-bloco" data-i="${i}">${insc ? '✓ Inscrito · Enviar link' : 'Participar'}</button>`
          : c.status === 'breve' ? `<button class="btn btn-contorno btn-bloco" data-lembrar="${i}">Me avise quando abrir</button>`
          : `<button class="btn btn-contorno btn-bloco" disabled>Ver resultado</button>`;
        return `<article class="camp cartao">
          <div class="camp-capa" style="background:${grad(c.g)}">
            <span class="status ${c.status === 'aberto' ? 'pronto' : c.status === 'breve' ? 'processando' : 'fila'}">${ROTULO[c.status]}</span>
            <div class="camp-premio">${c.premio}<small>em prêmios</small></div>
          </div>
          <div class="camp-corpo">
            <h3>${c.titulo}</h3><p>${c.desc}</p>
            <div class="camp-info"><span><i data-icone="relogio"></i>${c.fim}</span><span><i data-icone="usuario"></i>${c.part} participantes</span><span><i data-icone="escudo"></i>${c.req}</span></div>
            ${botao}
          </div></article>`;
      }).join('') || '<p style="color:var(--text-3)">Nenhum campeonato aqui por enquanto.</p>';
      Icones.desenhar($('#listaCamps'));
      $$('#listaCamps [data-i]').forEach((b) => b.addEventListener('click', () => {
        const i = +b.dataset.i;
        if (sessao.plano === 'explorador') { avisar('Campeonatos são para os planos Criador e Estúdio.'); return; }
        if (inscritos.has(i)) { avisar('Envio de links chega na Fase 4. Por enquanto, é uma demonstração.'); return; }
        inscritos.add(i); CAMPS[i].part++; desenhar(); avisar('Inscrição feita! Agora é cortar e postar. 🏆');
      }));
      $$('#listaCamps [data-lembrar]').forEach((b) => b.addEventListener('click', () => avisar('Combinado! Vamos te avisar quando abrir.')));
    }
    $$('.filtro').forEach((f) => f.addEventListener('click', () => {
      filtro = f.dataset.filtro;
      $$('.filtro').forEach((x) => x.classList.toggle('ativo', x === f));
      desenhar();
    }));
    desenhar();

    const RANK = [['@mariacortes', 'MC', '#8b5cf6', '1,2 mi', 'R$ 1.500'], ['@lucas.podcuts', 'LP', '#ff8a3d', '870 mil', 'R$ 800'], ['@jvclips', 'JV', '#34d399', '640 mil', 'R$ 400'], ['@anacortez', 'AN', '#60a5fa', '512 mil', 'R$ 200'], ['@cortesdobruno', 'CB', '#f472b6', '430 mil', 'R$ 100']];
    $('#listaRanking').innerHTML = RANK.map((r, i) => `<li><span class="pos">${i + 1}</span><span class="avatar" style="--c:${r[2]}">${r[1]}</span><b>${r[0]}</b><span class="r-views">${r[3]}</span><span class="premio">${r[4]}</span></li>`).join('') +
      `<li class="voce"><span class="pos">12</span><span class="avatar" style="--c:#a78bfa">${iniciais(sessao.nome)}</span><b></b><span class="r-views">98 mil</span><span class="premio">—</span></li>`;
    $('#listaRanking .voce b').textContent = 'Você';
  }

  Icones.desenhar();
})();
