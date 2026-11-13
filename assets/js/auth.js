/* =========================================================
   CLIP STORAGE — Login, cadastro e recuperação de senha
   Nesta fase (só front-end) a conta fica salva no navegador.
   Na Fase 2 estes formulários vão conversar com o servidor.
   ========================================================= */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const CHAVE = 'clipStorage.sessao';
  const emailValido = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);

  function avisar(msg) {
    const t = $('#toast');
    t.textContent = msg; t.classList.add('mostrar');
    clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('mostrar'), 2600);
  }
  function salvarSessao(dados) {
    try { localStorage.setItem(CHAVE, JSON.stringify(dados)); } catch { /* navegador sem armazenamento */ }
  }
  function erro(form, campo, msg) {
    const span = $(`[data-erro="${campo}"]`, form);
    if (span) span.textContent = msg || '';
    const input = form.elements[campo];
    const caixa = input && input.closest('.entrada');
    if (caixa) caixa.classList.toggle('erro', !!msg);
    return !msg;
  }
  function carregar(btn, ligado) {
    btn.classList.toggle('carregando', ligado);
    btn.disabled = ligado;
  }
  function entrarNoPainel(dados, btn) {
    carregar(btn, true);
    salvarSessao(dados);
    setTimeout(() => { location.href = 'painel.html'; }, 900);
  }
  const nomeDoEmail = (e) => e.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());

  // Mostrar / esconder senha
  $$('.ver-senha').forEach((b) => b.addEventListener('click', () => {
    const input = b.parentElement.querySelector('input');
    const mostrar = input.type === 'password';
    input.type = mostrar ? 'text' : 'password';
    b.innerHTML = Icones.svg(mostrar ? 'olhoFechado' : 'olho');
    b.setAttribute('aria-label', mostrar ? 'Esconder senha' : 'Mostrar senha');
  }));

  // Entrar com Google (demonstração)
  $$('[data-google]').forEach((b) => b.addEventListener('click', () => {
    entrarNoPainel({ nome: 'Criador Demo', email: 'demo@clipstorage.com', plano: 'explorador', creditos: 8 }, b);
  }));

  // ---------- LOGIN ----------
  const fLogin = $('#formLogin');
  if (fLogin) fLogin.addEventListener('submit', (e) => {
    e.preventDefault();
    const email = fLogin.email.value.trim(), senha = fLogin.senha.value;
    const ok = [
      erro(fLogin, 'email', !email ? 'Digite seu e-mail.' : !emailValido(email) ? 'E-mail inválido.' : ''),
      erro(fLogin, 'senha', !senha ? 'Digite sua senha.' : senha.length < 6 ? 'A senha tem pelo menos 6 caracteres.' : ''),
    ].every(Boolean);
    if (!ok) return;
    const btn = $('button[type=submit]', fLogin);
    API.verificar().then(async (real) => {
      if (!real) return entrarNoPainel({ nome: nomeDoEmail(email), email, plano: 'explorador', creditos: 8 }, btn);
      carregar(btn, true);
      try {
        await API.post('/api/auth/login', { email, senha, lembrar: fLogin.lembrar.checked });
        location.href = 'painel.html';
      } catch (erroApi) {
        carregar(btn, false);
        erro(fLogin, 'senha', erroApi.message);
      }
    });
  });

  // ---------- CADASTRO ----------
  const fCad = $('#formCadastro');
  if (fCad) {
    const planos = { criador: 'Criador · R$ 29,90/mês', estudio: 'Estúdio · R$ 59,90/mês' };
    const plano = new URLSearchParams(location.search).get('plano');
    if (planos[plano]) { $('#planoEscolhido').hidden = false; $('#planoNome').textContent = planos[plano]; }

    const forca = $('#forca'), forcaTexto = $('#forcaTexto');
    const textos = ['Use letras, números e símbolos.', 'Senha fraca', 'Senha razoável', 'Senha boa', 'Senha forte'];
    fCad.senha.addEventListener('input', () => {
      const s = fCad.senha.value;
      let n = 0;
      if (s.length >= 8) n++;
      if (/[A-Z]/.test(s) && /[a-z]/.test(s)) n++;
      if (/\d/.test(s)) n++;
      if (/[^A-Za-z0-9]/.test(s)) n++;
      if (!s) n = 0;
      forca.dataset.nivel = n;
      forcaTexto.textContent = textos[n];
    });

    fCad.addEventListener('submit', (e) => {
      e.preventDefault();
      const nome = fCad.nome.value.trim(), email = fCad.email.value.trim(), senha = fCad.senha.value;
      const ok = [
        erro(fCad, 'nome', nome.length < 2 ? 'Digite seu nome.' : ''),
        erro(fCad, 'email', !emailValido(email) ? 'Digite um e-mail válido.' : ''),
        erro(fCad, 'senha', senha.length < 8 ? 'A senha precisa ter pelo menos 8 caracteres.' : ''),
        erro(fCad, 'termos', !fCad.termos.checked ? 'Você precisa aceitar os termos.' : ''),
      ].every(Boolean);
      if (!ok) return;
      const btn = $('button[type=submit]', fCad);
      API.verificar().then(async (real) => {
        if (!real) return cadastroDemo();
        carregar(btn, true);
        try {
          await API.post('/api/auth/cadastro', { nome, email, senha });
          avisar('Conta criada! Você ganhou 8 créditos 🎉');
          setTimeout(() => { location.href = planos[plano] ? 'assinatura.html' : 'painel.html'; }, 900);
        } catch (erroApi) {
          carregar(btn, false);
          erro(fCad, erroApi.status === 409 ? 'email' : 'senha', erroApi.message);
        }
      });
    });

    function cadastroDemo() {
      const nome = fCad.nome.value.trim(), email = fCad.email.value.trim();
      avisar(planos[plano] ? 'Conta criada! Seus créditos do plano já estão liberados 🎉' : 'Conta criada! Você ganhou 8 créditos 🎉');
      entrarNoPainel({ nome, email, plano: planos[plano] ? plano : 'explorador', creditos: { criador: 100, estudio: 250 }[plano] || 8, novo: true }, $('button[type=submit]', fCad));
    }
  }

  // ---------- RECUPERAR SENHA ----------
  const fRec = $('#formRecuperar');
  if (fRec) fRec.addEventListener('submit', (e) => {
    e.preventDefault();
    const email = fRec.email.value.trim();
    if (!erro(fRec, 'email', !emailValido(email) ? 'Digite um e-mail válido.' : '')) return;
    const btn = $('button[type=submit]', fRec);
    carregar(btn, true);
    setTimeout(() => {
      $('#emailEnviado').textContent = email;
      $('#etapaPedido').hidden = true;
      $('#etapaEnviado').hidden = false;
    }, 1000);
  });

  // Limpa o erro ao digitar
  $$('input').forEach((i) => i.addEventListener('input', () => {
    const f = i.form; if (f && i.name) erro(f, i.name, '');
  }));
})();
