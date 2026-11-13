/* =========================================================
   CLIP STORAGE — Interações da página inicial
   ========================================================= */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // Aviso flutuante
  window.avisar = function (msg) {
    const t = $('#toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('mostrar');
    clearTimeout(t._tempo);
    t._tempo = setTimeout(() => t.classList.remove('mostrar'), 2600);
  };

  // Cabeçalho muda ao rolar
  const topo = $('#topo');
  const aoRolar = () => topo && topo.classList.toggle('rolou', scrollY > 10);
  addEventListener('scroll', aoRolar, { passive: true });
  aoRolar();

  // Menu no celular
  const menu = $('#menu'), botao = $('#menuBotao');
  if (menu && botao) {
    botao.addEventListener('click', () => {
      const aberto = menu.classList.toggle('aberto');
      botao.setAttribute('aria-expanded', aberto);
      botao.innerHTML = Icones.svg(aberto ? 'fechar' : 'menu');
    });
    $$('a', menu).forEach((a) => a.addEventListener('click', () => {
      menu.classList.remove('aberto');
      botao.innerHTML = Icones.svg('menu');
    }));
  }

  // Elementos aparecem ao rolar
  const obs = new IntersectionObserver((itens) => {
    itens.forEach((i) => { if (i.isIntersecting) { i.target.classList.add('visivel'); obs.unobserve(i.target); } });
  }, { threshold: 0.15 });
  $$('.revelar').forEach((el) => obs.observe(el));

  // Demonstração: abas e cálculo de créditos
  const origens = {
    arquivo: { nome: 'live-de-sexta.mp4', info: '1h 24min · 2,1 GB', max: 85 },
    link: { nome: 'https://meusite.com/podcast-ep42.mp4', info: '52min · link direto', max: 52 },
    youtube: { nome: 'youtube.com/watch?v=Ep42Podcast', info: '2h 08min · YouTube', max: 128 },
  };
  const range = $('#demoRange');
  function atualizarCusto() {
    if (!range) return;
    $('#demoMin').textContent = range.value + ' min';
    $('#demoCreditos').textContent = range.value;
  }
  $$('.aba').forEach((aba) => aba.addEventListener('click', () => {
    $$('.aba').forEach((a) => a.classList.toggle('ativa', a === aba));
    const o = origens[aba.dataset.aba];
    $('#demoNome').textContent = o.nome;
    $('#demoInfo').textContent = o.info;
    range.max = o.max; range.value = o.max;
    $('.demo-trecho-escala span:last-child').textContent = `${Math.floor(o.max / 60)}:${String(o.max % 60).padStart(2, '0')}:00`;
    atualizarCusto();
  }));
  if (range) range.addEventListener('input', atualizarCusto);

  // Estilo da legenda no mini editor
  const legenda = $('#legendaDemo');
  $$('#chipsLegenda .chip').forEach((chip) => chip.addEventListener('click', () => {
    $$('#chipsLegenda .chip').forEach((c) => c.classList.toggle('ativo', c === chip));
    legenda.className = 'legenda-demo estilo-' + chip.dataset.estilo;
  }));

  // Botão de publicar (demonstração)
  const pub = $('#btnPublicarDemo');
  if (pub) pub.addEventListener('click', () => avisar('Corte publicado em 3 redes! (demonstração)'));

  // Planos: mensal x anual
  $$('.ciclo-btn').forEach((b) => b.addEventListener('click', () => {
    $$('.ciclo-btn').forEach((x) => x.classList.toggle('ativo', x === b));
    const anual = b.dataset.ciclo === 'anual';
    $('.planos').classList.toggle('anual', anual);
    $$('.preco[data-mensal]').forEach((p) => {
      $('strong', p).textContent = anual ? p.dataset.anual : p.dataset.mensal;
    });
  }));
})();
