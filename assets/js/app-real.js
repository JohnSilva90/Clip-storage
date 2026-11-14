/* =========================================================
   CLIP STORAGE — Telas com dados reais (servidor Python ligado)
   ========================================================= */
window.AppReal = (function () {
  let $, $$, sessao, avisar, grad, mmss, atualizarCreditos;

  function iniciar(ctx) {
    ({ $, $$, sessao, avisar, grad, mmss, atualizarCreditos } = ctx);
    ({ painel, importar, editor, assinatura })[ctx.pagina]();
  }

  const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const quando = (iso) => {
    const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z');
    const hoje = new Date();
    const hora = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    if (d.toDateString() === hoje.toDateString()) return 'Hoje, ' + hora;
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }) + ', ' + hora;
  };
  function setCreditos(n) { sessao.creditos = n; atualizarCreditos(); }

  // =========================================================
  //   PAINEL
  // =========================================================
  async function painel() {
    $('#saudacao').textContent = `Olá, ${sessao.nome.split(' ')[0]}!`;
    $('#estCreditos').textContent = sessao.creditos;
    $('#estPlano').textContent = 'Plano ' + sessao.plano_nome;
    $('#estViews').textContent = '—'; $('#estViewsInfo').textContent = 'Conecte as redes (em breve)';
    $('#estViewsInfo').className = 'neutro';
    $('#estPub').textContent = '0'; $('#estPubInfo').textContent = 'publicação direta em breve';

    const lista = $('#listaProjetos');
    let timer = null;
    async function carregar() {
      const projetos = await API.get('/api/projetos');
      const totalCortes = projetos.reduce((s, p) => s + p.cortes, 0);
      $('#estCortes').textContent = totalCortes;
      $('#estCortesInfo').textContent = `em ${projetos.length} projeto${projetos.length === 1 ? '' : 's'}`;
      if (!projetos.length) {
        lista.innerHTML = '<p style="color:var(--text-3);padding:20px;text-align:center">Nenhum projeto ainda. <a class="link" href="importar.html">Envie seu primeiro vídeo</a></p>';
      } else {
        lista.innerHTML = projetos.map((p, i) => {
          const rotulo = { pronto: 'Pronto', processando: `Processando ${p.progresso}%`, fila: 'Na fila', erro: 'Erro' }[p.status];
          const capa = p.miniatura ? `background:url('${p.miniatura}') center/cover` : `background:${grad(i)}`;
          return `<a class="projeto" href="${p.status === 'pronto' ? 'editor.html?projeto=' + p.id : '#'}" data-status="${p.status}" data-erro="${esc(p.erro || '')}">
            <div class="miniatura" style="${capa}">${p.miniatura ? '' : '<i data-icone="filme"></i>'}<span class="duracao">${mmss(p.fim - p.inicio)}</span></div>
            <div style="min-width:0"><h3>${esc(p.titulo)}</h3>
              <div class="projeto-meta"><span>${quando(p.criado_em)}</span><span>${p.creditos} créditos</span>${p.cortes ? `<span>${p.cortes} cortes</span>` : ''}</div>
              ${p.status === 'processando' ? `<div class="progresso-mini"><span style="width:${p.progresso}%"></span></div><div class="projeto-meta"><span>${esc(p.etapa)}</span></div>` : ''}
            </div>
            <span class="status ${p.status === 'erro' ? 'fila' : p.status}">${rotulo}</span></a>`;
        }).join('');
        Icones.desenhar(lista);
        $$('.projeto', lista).forEach((el) => el.addEventListener('click', (e) => {
          if (el.dataset.status === 'pronto') return;
          e.preventDefault();
          avisar(el.dataset.status === 'erro' ? 'Erro: ' + (el.dataset.erro || 'tente enviar de novo.') : 'Esse projeto ainda está sendo processado.');
        }));
      }
      // Melhores cortes do projeto pronto mais recente
      const pronto = projetos.find((p) => p.status === 'pronto' && p.cortes);
      if (pronto && !$('#cortesDestaque').dataset.ok) {
        const det = await API.get('/api/projetos/' + pronto.id);
        $('#cortesDestaque').dataset.ok = '1';
        $('#cortesDestaque').innerHTML = det.lista_cortes.slice(0, 6).map((c) => `
          <a class="corte-card" href="editor.html?projeto=${pronto.id}&corte=${c.id}" style="background:url('${c.miniatura}') center/cover">
            <span class="nota">${c.nota}</span><span class="leg">${esc(c.titulo)}</span><span class="vw"><i data-icone="relogio"></i> ${Math.round(c.duracao)}s</span></a>`).join('');
        Icones.desenhar($('#cortesDestaque'));
      } else if (!pronto) {
        $('#cortesDestaque').innerHTML = '<p style="grid-column:1/-1;color:var(--text-3);font-size:14px">Seus melhores cortes aparecem aqui.</p>';
      }
      clearTimeout(timer);
      if (projetos.some((p) => p.status === 'processando' || p.status === 'fila')) timer = setTimeout(carregar, 2000);
    }
    carregar().catch((e) => avisar(e.message));
  }

  // =========================================================
  //   IMPORTAR
  // =========================================================
  function importar() {
    let arquivo = null, duracaoMin = 0, link = null;
    const btnGerar = $('#btnGerar'), aviso = $('#avisoResumo');

    const trecho = () => {
      const ini = Math.max(0, +$('#trechoIni').value || 0);
      const fim = Math.min(duracaoMin, +$('#trechoFim').value || duracaoMin);
      return Math.max(0, fim - ini);
    };
    function resumo() {
      const min = (arquivo || link) ? trecho() : 0;
      const custo = Math.ceil(min);
      $('#resumoDur').textContent = min ? mmss(min * 60) : '—';
      $('#resumoCred').textContent = custo;
      $('#resumoSaldo').textContent = sessao.creditos - custo;
      aviso.classList.remove('aviso-erro');
      btnGerar.disabled = !min;
      if (!min) { aviso.textContent = 'Escolha um vídeo para ver o custo.'; return; }
      let erro = '';
      if (custo > sessao.creditos) erro = `Faltam ${custo - sessao.creditos} créditos. Escolha um trecho menor ou compre mais créditos.`;
      else if (min > sessao.max_min + 0.01) erro = `Seu plano analisa até ${sessao.max_min} minutos por vídeo. Escolha um trecho menor.`;
      else if (min < 10 / 60) erro = 'O trecho precisa ter pelo menos 10 segundos.';
      aviso.textContent = erro || 'Você só paga pelos minutos analisados.';
      if (erro) { aviso.classList.add('aviso-erro'); btnGerar.disabled = true; }
    }
    function escolher(arq) {
      if (!arq.type.startsWith('video/') && !/\.(mp4|mov|mkv|webm|avi|m4v)$/i.test(arq.name)) { avisar('Escolha um arquivo de vídeo.'); return; }
      const v = document.createElement('video');
      v.preload = 'metadata';
      v.onloadedmetadata = () => {
        URL.revokeObjectURL(v.src);
        arquivo = arq;
        duracaoMin = v.duration / 60;
        const tam = arq.size > 1e9 ? (arq.size / 1e9).toFixed(1).replace('.', ',') + ' GB' : Math.round(arq.size / 1e6) + ' MB';
        $('#escolhidoNome').textContent = arq.name;
        $('#escolhidoInfo').textContent = `${mmss(v.duration)} · ${tam}`;
        $('#arquivoEscolhido').hidden = false; $('#opcoes').hidden = false;
        $('#trechoIni').value = 0;
        $('#trechoFim').value = Math.round(Math.min(duracaoMin, sessao.max_min, Math.max(1, sessao.creditos)) * 10) / 10;
        $('#trechoIni').step = $('#trechoFim').step = '0.5';
        resumo();
      };
      v.onerror = () => avisar('Não consegui ler esse vídeo no navegador. Tente MP4.');
      v.src = URL.createObjectURL(arq);
    }
    function limpar() { arquivo = null; link = null; duracaoMin = 0; $('#arquivoEscolhido').hidden = true; $('#opcoes').hidden = true; $('#inputArquivo').value = ''; resumo(); }

    $$('.abas-app button').forEach((b) => b.addEventListener('click', () => {
      $$('.abas-app button').forEach((x) => x.classList.toggle('ativa', x === b));
      const arq = b.dataset.origem === 'arquivo';
      $('#painelArquivo').hidden = !arq; $('#painelLink').hidden = arq;
      $('#rotuloLink').textContent = b.dataset.origem === 'link' ? 'Link direto do vídeo (.mp4)' : 'Link do YouTube, Twitch ou Kick';
      $('#entradaLink').placeholder = b.dataset.origem === 'link' ? 'https://meusite.com/video.mp4' : 'https://www.youtube.com/watch?v=...';
      limpar();
    }));
    // Link (YouTube, Twitch, Kick ou link direto): lê título e duração antes de cobrar
    async function carregarLink() {
      const url = $('#entradaLink').value.trim();
      if (!url) { avisar('Cole o link do vídeo.'); return; }
      const btn = $('#btnLink');
      btn.disabled = true; btn.textContent = 'Lendo...';
      try {
        const info = await API.post('/api/projetos/link/info', { url });
        link = info.url; arquivo = null;
        duracaoMin = info.duracao / 60;
        $('#escolhidoNome').textContent = info.titulo;
        $('#escolhidoInfo').textContent = `${mmss(info.duracao)}${info.canal ? ' · ' + info.canal : ''}`;
        $('#arquivoEscolhido').hidden = false; $('#opcoes').hidden = false;
        $('#trechoIni').value = 0;
        $('#trechoFim').value = Math.round(Math.min(duracaoMin, sessao.max_min, Math.max(1, sessao.creditos)) * 10) / 10;
        $('#trechoIni').step = $('#trechoFim').step = '0.5';
        resumo();
        if (duracaoMin > sessao.max_min) avisar(`O vídeo tem ${Math.round(duracaoMin)} min. Escolha o trecho que a IA vai analisar.`);
      } catch (e) { avisar(e.message); }
      btn.disabled = false; btn.textContent = 'Carregar';
    }
    $('#btnLink').addEventListener('click', carregarLink);
    $('#entradaLink').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); carregarLink(); } });

    const soltar = $('#soltar'), input = $('#inputArquivo');
    soltar.addEventListener('click', () => input.click());
    soltar.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
    ['dragenter', 'dragover'].forEach((ev) => soltar.addEventListener(ev, (e) => { e.preventDefault(); soltar.classList.add('arrastando'); }));
    ['dragleave', 'drop'].forEach((ev) => soltar.addEventListener(ev, (e) => { e.preventDefault(); soltar.classList.remove('arrastando'); }));
    soltar.addEventListener('drop', (e) => { if (e.dataTransfer.files[0]) escolher(e.dataTransfer.files[0]); });
    input.addEventListener('change', () => { if (input.files[0]) escolher(input.files[0]); });
    $('#btnLimpar').addEventListener('click', limpar);
    ['trechoIni', 'trechoFim'].forEach((id) => $('#' + id).addEventListener('input', resumo));
    resumo();

    const etapas = () => $$('#etapasProc li');
    function marcarEtapa(indice, texto, pct) {
      etapas().forEach((li, j) => { li.className = j < indice ? 'feito' : j === indice ? 'agora' : ''; });
      $('#textoProc').textContent = texto;
      $('#barraProc').style.width = pct + '%';
    }

    btnGerar.addEventListener('click', async () => {
      if (link) return gerarPorLink();
      const dados = new FormData();
      dados.append('arquivo', arquivo);
      dados.append('inicio_min', $('#trechoIni').value || 0);
      dados.append('fim_min', $('#trechoFim').value || duracaoMin);
      dados.append('quantidade', $('#qtdCortes').value);
      dados.append('duracao', $('#durCortes').value);
      dados.append('idioma', $('#idioma').value);
      dados.append('formato', $('#formato').value);

      $('#etapaConfig').hidden = true; $('#resumoBloco').hidden = true; $('#etapaProc').hidden = false;
      $('#tituloProc').textContent = 'Enviando seu vídeo...';
      try {
        const proj = await API.enviar('/api/projetos', dados, (f) => marcarEtapa(0, `Enviando o vídeo: ${Math.round(f * 100)}%`, f * 10));
        setCreditos(proj.saldo);
        $('#tituloProc').textContent = 'Processando seu vídeo...';
        acompanhar(proj.id);
      } catch (e) {
        $('#tituloProc').textContent = 'Não deu certo 😕';
        $('#textoProc').textContent = e.message;
        mostrarVoltar();
      }
    });

    async function gerarPorLink() {
      $('#etapaConfig').hidden = true; $('#resumoBloco').hidden = true; $('#etapaProc').hidden = false;
      $('#tituloProc').textContent = 'Preparando o download...';
      marcarEtapa(0, 'Conferindo o link...', 2);
      try {
        const proj = await API.post('/api/projetos/link', {
          url: link, inicio_min: +$('#trechoIni').value || 0, fim_min: +$('#trechoFim').value || duracaoMin,
          quantidade: $('#qtdCortes').value, duracao: $('#durCortes').value, idioma: $('#idioma').value, formato: $('#formato').value,
        });
        setCreditos(proj.saldo);
        $('#tituloProc').textContent = 'Processando seu vídeo...';
        acompanhar(proj.id);
      } catch (e) {
        $('#tituloProc').textContent = 'Não deu certo 😕';
        $('#textoProc').textContent = e.message;
        mostrarVoltar();
      }
    }

    function mostrarVoltar() {
      const b = $('#btnVerCortes');
      b.hidden = false; b.href = 'importar.html'; b.innerHTML = 'Tentar de novo';
    }
    async function acompanhar(id) {
      try {
        const p = await API.get('/api/projetos/' + id);
        if (p.status === 'erro') {
          $('#tituloProc').textContent = 'Não deu certo 😕';
          $('#textoProc').textContent = (p.erro || 'Erro no processamento.') + ' Seus créditos foram devolvidos.';
          const s = await API.get('/api/auth/eu'); setCreditos(s.creditos);
          mostrarVoltar(); return;
        }
        const pct = p.progresso;
        const indice = p.status === 'fila' || pct < 10 ? 0 : pct < 58 ? 1 : pct < 70 ? 2 : 3;
        marcarEtapa(p.status === 'pronto' ? 4 : indice, p.status === 'fila' ? 'Na fila, já vamos começar...' : p.etapa, p.status === 'pronto' ? 100 : pct);
        if (p.status === 'pronto') {
          $('#tituloProc').textContent = `Seus ${p.cortes} cortes estão prontos! 🎉`;
          const b = $('#btnVerCortes'); b.hidden = false; b.href = 'editor.html?projeto=' + id;
          return;
        }
      } catch (e) { avisar(e.message); }
      setTimeout(() => acompanhar(id), 1500);
    }
  }

  // =========================================================
  //   EDITOR
  // =========================================================
  async function editor() {
    const params = new URLSearchParams(location.search);
    let projetoId = +params.get('projeto');
    if (!projetoId) {
      const projetos = await API.get('/api/projetos');
      const pronto = projetos.find((p) => p.status === 'pronto' && p.cortes);
      if (!pronto) {
        $('.editor').innerHTML = `<div class="bloco cartao" style="grid-column:1/-1;text-align:center;padding:60px 20px">
          <h2 style="font-size:22px">Nenhum corte ainda</h2><p style="color:var(--text-2);margin:8px 0 20px">Envie um vídeo e a IA cria os cortes para você editar aqui.</p>
          <a href="importar.html" class="btn btn-primario">Novo projeto</a></div>`;
        $('#tituloCorte').textContent = '';
        return;
      }
      projetoId = pronto.id;
    }
    const projeto = await API.get('/api/projetos/' + projetoId);
    const cortes = projeto.lista_cortes;
    $('.cabeca-pagina p').innerHTML = `${esc(projeto.titulo)} · <span id="tituloCorte"></span>`;
    if (!cortes.length) { avisar('Esse projeto não tem cortes.'); return; }

    // Troca a cena de demonstração por um player de vídeo de verdade
    const caixa = $('#previewVideo');
    $('#previewCena').outerHTML = '<video id="player" playsinline preload="metadata" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"></video>';
    const player = $('#player'), leg = $('#legenda');
    $('#previewMarca').hidden = !sessao.marca_dagua;
    $('#optMarca').checked = sessao.marca_dagua;
    $('#optMarca').addEventListener('change', (e) => {
      if (sessao.marca_dagua) { e.target.checked = true; avisar('Remover a marca d\'água é do plano Criador ou Estúdio.'); }
      else { e.target.checked = false; avisar('Seu plano já exporta sem marca d\'água.'); }
    });

    let atual = Math.max(0, cortes.findIndex((c) => c.id === +params.get('corte')));
    const corte = () => cortes[atual];

    // Lista lateral
    $('#totalCortes').textContent = cortes.length + ' cortes';
    function desenharLista() {
      $$('.item-corte').forEach((b) => b.remove());
      $('#listaCortes').insertAdjacentHTML('beforeend', cortes.map((c, i) => `
        <button class="item-corte ${i === atual ? 'ativo' : ''}" data-i="${i}">
          <span class="thumb" style="background:url('${c.miniatura}?v=${c._v || 0}') center/cover"></span>
          <span><b>${esc(c.titulo)}</b><small><span class="nota">${c.nota}</span> · ${Math.round(c.duracao)}s · ${mmss(c.inicio)}</small></span>
        </button>`).join(''));
      $$('.item-corte').forEach((b) => b.addEventListener('click', () => selecionar(+b.dataset.i)));
    }

    // Legenda por cima do vídeo, sincronizada com o tempo
    function blocoAtual(t) {
      const ps = corte().palavras;
      const idx = ps.findIndex((w) => t >= w.i && t < w.f + 0.25);
      if (idx < 0) return null;
      const ini = idx - (idx % 3);
      return { palavras: ps.slice(ini, ini + 3), atual: idx - ini };
    }
    function desenharLegenda() {
      const e = corte().estilo;
      leg.className = 'preview-legenda estilo-' + (e.legenda || 'destaque');
      leg.style.bottom = { baixo: '22%', meio: '45%', cima: '72%' }[e.posicao || 'baixo'];
      $('#estiloDinamico').textContent = `.preview-legenda.estilo-destaque .palavra.atual{background:${e.cor}}.preview-legenda.estilo-classica .palavra.atual{color:${e.cor}}.preview-legenda.estilo-neon .palavra.atual{color:${e.cor};text-shadow:0 0 8px ${e.cor},0 0 18px ${e.cor}}`;
      atualizarTempo();
    }
    function atualizarTempo() {
      const c = corte(), t = player.currentTime || 0;
      const b = blocoAtual(t);
      if (!c.palavras.length) leg.innerHTML = '<span style="font-size:13px;opacity:.6">(sem legenda: instale o faster-whisper)</span>';
      else if (!b) leg.innerHTML = '';
      else {
        const html = b.palavras.map((w, k) => `<span class="palavra ${k === b.atual ? 'atual' : ''}">${esc(w.p.toUpperCase())}</span>`).join(' ');
        leg.innerHTML = c.estilo.legenda === 'classica' ? `<span class="texto-fundo">${html}</span>` : html;
      }
      const dur = player.duration || c.duracao;
      $('#tempoAtual').textContent = `${mmss(t)} / ${mmss(dur)}`;
      $('#barraPreview').style.width = (t / dur) * 100 + '%';
      $('#cursorTrilha').style.left = (((c.inicio + t) - janela.ini) / (janela.fim - janela.ini)) * 100 + '%';
    }
    player.addEventListener('timeupdate', atualizarTempo);
    player.addEventListener('play', () => { $('#btnPlay').innerHTML = Icones.svg('pausa'); (function loop() { atualizarTempo(); if (!player.paused) requestAnimationFrame(loop); })(); });
    player.addEventListener('pause', () => { $('#btnPlay').innerHTML = Icones.svg('play'); });
    $('#btnPlay').addEventListener('click', () => (player.paused ? player.play() : player.pause()));
    caixa.addEventListener('click', (e) => { if (e.target === player) player.paused ? player.play() : player.pause(); });
    $('#barraPreviewFundo').addEventListener('click', (e) => {
      const r = e.currentTarget.getBoundingClientRect();
      player.currentTime = ((e.clientX - r.left) / r.width) * (player.duration || corte().duracao);
    });

    // Linha do tempo: janela de 30s antes e depois do corte
    const janela = { ini: 0, fim: 1 }, sel = { ini: 0, fim: 0 };
    function montarJanela() {
      const c = corte();
      janela.ini = Math.max(c.limite_inicio ?? projeto.inicio, c.inicio - 30);
      janela.fim = Math.min(c.limite_fim ?? projeto.fim, c.fim + 30);
      sel.ini = c.inicio; sel.fim = c.fim;
      $('.escala span:first-child').textContent = mmss(janela.ini);
      $('#escalaFim').textContent = mmss(janela.fim);
      desenharTrilha();
    }
    function desenharTrilha() {
      const tam = janela.fim - janela.ini;
      $('#selecao').style.left = ((sel.ini - janela.ini) / tam) * 100 + '%';
      $('#selecao').style.width = ((sel.fim - sel.ini) / tam) * 100 + '%';
      $('#infoTrecho').textContent = `${mmss(sel.ini)} → ${mmss(sel.fim)} · ${Math.round(sel.fim - sel.ini)}s`;
    }
    function arrastar(lado) {
      return (e) => {
        e.preventDefault();
        const r = $('#trilha').getBoundingClientRect();
        const mover = (ev) => {
          const x = Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width));
          const t = janela.ini + x * (janela.fim - janela.ini);
          if (lado === 'ini') sel.ini = Math.min(t, sel.fim - 3); else sel.fim = Math.max(t, sel.ini + 3);
          desenharTrilha();
        };
        const soltarAlca = () => {
          removeEventListener('pointermove', mover); removeEventListener('pointerup', soltarAlca);
          salvar({ inicio: sel.ini, fim: sel.fim }, true);
        };
        addEventListener('pointermove', mover); addEventListener('pointerup', soltarAlca);
      };
    }
    $('.alca.ini').addEventListener('pointerdown', arrastar('ini'));
    $('.alca.fim').addEventListener('pointerdown', arrastar('fim'));

    // Salvar alterações no servidor
    let salvando = Promise.resolve();
    function salvar(mudancas, recarregarVideo) {
      if (recarregarVideo) avisar('Atualizando o corte...');
      salvando = salvando.then(async () => {
        try {
          const novo = await API.patch('/api/cortes/' + corte().id, mudancas);
          novo._v = Date.now();
          cortes[atual] = novo;
          if (recarregarVideo) { carregarVideo(); montarJanela(); desenharLista(); avisar('Corte atualizado!'); }
          desenharLegenda();
        } catch (e) { avisar(e.message); }
      });
      return salvando;
    }
    function carregarVideo() {
      player.src = corte().previa + '?v=' + (corte()._v || 0);
      caixa.dataset.formato = corte().estilo.formato || '9:16';
    }

    function marcarOpcoes() {
      const e = corte().estilo;
      [['optEstilo', e.legenda || 'destaque'], ['optPosicao', e.posicao || 'baixo'], ['optFormato', e.formato || '9:16'], ['optLayout', e.layout || 'auto']].forEach(([id, v]) =>
        $$(`#${id} .opcao`).forEach((b) => b.classList.toggle('ativa', b.dataset.valor === v)));
      $$('.cor').forEach((c) => c.classList.toggle('ativa', c.dataset.cor === e.cor));
      $('#textoLegenda').value = e.texto || corte().palavras.map((w) => w.p).join(' ');
    }
    function selecionar(i) {
      atual = i;
      player.pause();
      $$('.item-corte').forEach((b) => b.classList.toggle('ativo', +b.dataset.i === i));
      $('#tituloCorte').textContent = `Corte ${i + 1} · nota ${corte().nota}`;
      carregarVideo(); montarJanela(); marcarOpcoes(); desenharLegenda();
      history.replaceState(null, '', `editor.html?projeto=${projetoId}&corte=${corte().id}`);
    }

    // Opções de estilo
    [['optEstilo', 'legenda', false], ['optPosicao', 'posicao', false], ['optFormato', 'formato', true], ['optLayout', 'layout', true]].forEach(([id, campo, pesado]) =>
      $$(`#${id} .opcao`).forEach((b) => b.addEventListener('click', () => {
        $$(`#${id} .opcao`).forEach((x) => x.classList.toggle('ativa', x === b));
        corte().estilo[campo] = b.dataset.valor;
        if (campo === 'formato') caixa.dataset.formato = b.dataset.valor;
        desenharLegenda();
        salvar({ [campo]: b.dataset.valor }, pesado);
      })));
    $$('.cor').forEach((c) => c.addEventListener('click', () => {
      $$('.cor').forEach((x) => x.classList.toggle('ativa', x === c));
      corte().estilo.cor = c.dataset.cor; desenharLegenda(); salvar({ cor: c.dataset.cor });
    }));
    let tempoTexto;
    $('#textoLegenda').addEventListener('input', (e) => {
      clearTimeout(tempoTexto);
      tempoTexto = setTimeout(() => salvar({ texto: e.target.value }), 700);
    });

    // Exportar e baixar em 1080p
    $('#btnBaixar').addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true; btn.textContent = 'Gerando vídeo em 1080p...';
      try {
        await salvando;
        const r = await API.post(`/api/cortes/${corte().id}/exportar`);
        const a = document.createElement('a'); a.href = r.baixar; a.download = ''; document.body.appendChild(a); a.click(); a.remove();
        avisar('Pronto! O download começou.');
      } catch (erro) { avisar(erro.message); }
      btn.disabled = false; btn.innerHTML = Icones.svg('baixar') + ' Baixar em 1080p';
    });
    const modal = $('#modalPublicar');
    $('#btnPublicar').addEventListener('click', () => modal.classList.add('aberto'));
    $$('[data-fechar]').forEach((b) => b.addEventListener('click', () => modal.classList.remove('aberto')));
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('aberto'); });
    $('#btnConfirmarPub').addEventListener('click', () => {
      modal.classList.remove('aberto');
      avisar('A publicação direta chega na Fase 4. Por enquanto, baixe o corte e poste.');
    });

    desenharLista();
    selecionar(atual);
  }

  // =========================================================
  //   PLANOS E CRÉDITOS
  // =========================================================
  async function assinatura() {
    const cfg = await API.get('/api/pagamentos/config').catch(() => ({ simulado: true }));
    function preencher() {
      $('#nomePlanoAtual').textContent = sessao.plano_nome;
      $('#precoPlanoAtual').textContent = { explorador: 'Grátis', criador: 'R$ 29,90/mês', estudio: 'R$ 59,90/mês' }[sessao.plano];
      $('#credAtual').textContent = sessao.creditos;
      $('#credTotal').textContent = sessao.creditos_plano;
      $('#barraUso').style.width = Math.min(100, (sessao.creditos / sessao.creditos_plano) * 100) + '%';
      const ate = sessao.plano_ate ? new Date(sessao.plano_ate).toLocaleDateString('pt-BR') : null;
      $('#btnCancelar').hidden = sessao.plano === 'explorador' || !!ate;
      let nota = $('#notaPlanoAte');
      if (!nota) { nota = document.createElement('p'); nota.id = 'notaPlanoAte'; nota.style.color = 'var(--text-2, #a9a3c4)'; nota.style.fontSize = '.9rem';
        nota.style.marginTop = '10px'; $('#btnCancelar').after(nota); }
      nota.hidden = !ate;
      nota.textContent = ate ? `Assinatura cancelada. Seu plano continua até ${ate}; depois volta para o grátis.` : '';
      $$('.plano-app').forEach((card) => {
        const ehAtual = card.dataset.plano === sessao.plano, btn = $('.btn', card);
        card.classList.toggle('atual', ehAtual);
        btn.disabled = ehAtual && !ate;
        btn.textContent = ehAtual ? (ate ? 'Reativar ' + $('h3', card).textContent : 'Plano atual')
          : card.dataset.plano === 'explorador' ? 'Voltar ao grátis' : 'Assinar ' + $('h3', card).textContent;
      });
      atualizarCreditos();
    }
    async function historico() {
      const movs = await API.get('/api/conta/historico');
      $('.tabela thead').innerHTML = '<tr><th>Data</th><th>Descrição</th><th>Créditos</th></tr>';
      $('.tabela tbody').innerHTML = movs.map((m) => `<tr><td>${quando(m.data)}</td><td><b>${esc(m.descricao)}</b></td>
        <td style="color:${m.quantidade > 0 ? 'var(--success)' : 'inherit'}">${m.quantidade > 0 ? '+' : ''}${m.quantidade}</td></tr>`).join('');
    }
    function atualizarSessao(u) { Object.assign(sessao, u); preencher(); historico(); }
    preencher(); historico();
    if (cfg.simulado) avisar('Pagamentos em modo simulação (configure o Mercado Pago no .env).');

    // Voltou do checkout do Mercado Pago? Confere o pagamento.
    const pedido = new URLSearchParams(location.search).get('pedido');
    if (pedido) {
      history.replaceState(null, '', 'assinatura.html');
      let tentativas = 0;
      (async function conferir() {
        try {
          const r = await API.get('/api/pagamentos/pedido/' + pedido);
          if (r.status === 'aprovado') { atualizarSessao(r.usuario); avisar('Pagamento confirmado! 🎉'); return; }
          if (r.status === 'recusado') { avisar('O pagamento não foi aprovado. Tente outra forma de pagamento.'); return; }
          if (r.status === 'expirado') { avisar('Esse pagamento venceu. Faça um novo pedido.'); return; }
          if (++tentativas < 20) { if (tentativas === 1) avisar('Aguardando a confirmação do pagamento...'); setTimeout(conferir, 3000); }
          else avisar('Ainda não recebemos a confirmação. Se pagou com Pix, ela chega em alguns minutos.');
        } catch (e) { avisar(e.message); }
      })();
    }

    async function irParaPagamento(url, corpo, btn) {
      btn.disabled = true;
      const texto = btn.textContent; btn.textContent = 'Abrindo o pagamento...';
      try {
        const r = await API.post(url, corpo);
        if (r.checkout) { location.href = r.checkout; return; }
        atualizarSessao(r.usuario);
        avisar('Feito! (modo simulação: nenhum valor foi cobrado)');
      } catch (e) { avisar(e.message); }
      btn.disabled = false; btn.textContent = texto; preencher();
    }

    $$('.plano-app').forEach((card) => $('.btn', card).addEventListener('click', (e) => {
      if (card.dataset.plano === 'explorador') { if (sessao.plano_ate) return avisar('Seu plano já vai voltar ao grátis no fim do período pago.'); return $('#btnCancelar').click(); }
      irParaPagamento('/api/pagamentos/assinatura', { plano: card.dataset.plano }, e.currentTarget);
    }));
    $$('.pacote').forEach((pc) => pc.addEventListener('click', () => {
      $$('.pacote').forEach((x) => x.classList.toggle('ativo', x === pc));
      const b = $('#btnComprar'); b.disabled = false; b.dataset.qtd = pc.dataset.qtd;
      b.textContent = `Comprar ${pc.dataset.qtd} créditos por ${pc.dataset.preco}`;
    }));
    $('#btnComprar').addEventListener('click', (e) => irParaPagamento('/api/pagamentos/creditos', { quantidade: +e.currentTarget.dataset.qtd }, e.currentTarget));
    $('#btnCancelar').addEventListener('click', async () => {
      if (!window.confirm('Cancelar a assinatura? Você não será mais cobrado e o plano continua até o fim do mês já pago.')) return;
      try { atualizarSessao(await API.post('/api/pagamentos/cancelar')); avisar('Assinatura cancelada.'); }
      catch (e) { avisar(e.message); }
    });
  }

  return { iniciar };
})();
