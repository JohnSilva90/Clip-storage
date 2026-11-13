/* =========================================================
   CLIP STORAGE — Conexão com o servidor (API)
   Se o servidor Python estiver ligado, o site usa dados reais.
   Se não estiver (ex.: GitHub Pages), o site entra no modo demonstração.
   ========================================================= */
window.API = (function () {
  let ativo = null;

  async function verificar() {
    if (ativo !== null) return ativo;
    if (location.protocol === 'file:') return (ativo = false);
    try {
      const r = await fetch('/api/saude', { cache: 'no-store' });
      const d = r.ok ? await r.json() : null;
      ativo = !!(d && d.ok);
      if (ativo) window.API.recursos = d;
    } catch { ativo = false; }
    return ativo;
  }

  async function chamar(metodo, url, corpo) {
    const opcoes = { method: metodo, credentials: 'same-origin', headers: {} };
    if (corpo !== undefined) {
      opcoes.headers['Content-Type'] = 'application/json';
      opcoes.body = JSON.stringify(corpo);
    }
    const r = await fetch(url, opcoes);
    let dados = null;
    try { dados = await r.json(); } catch { /* resposta sem JSON */ }
    if (!r.ok) {
      const msg = dados && (typeof dados.detail === 'string' ? dados.detail : 'Verifique os dados enviados.');
      const erro = new Error(msg || 'Algo deu errado. Tente de novo.');
      erro.status = r.status;
      throw erro;
    }
    return dados;
  }

  // Envio de arquivo com barra de progresso
  function enviar(url, formData, aoProgredir) {
    return new Promise((resolver, rejeitar) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url);
      xhr.withCredentials = true;
      xhr.upload.onprogress = (e) => { if (e.lengthComputable && aoProgredir) aoProgredir(e.loaded / e.total); };
      xhr.onload = () => {
        let d = null;
        try { d = JSON.parse(xhr.responseText); } catch { /* nada */ }
        if (xhr.status >= 200 && xhr.status < 300) resolver(d);
        else rejeitar(new Error((d && typeof d.detail === 'string' && d.detail) || 'Falha no envio.'));
      };
      xhr.onerror = () => rejeitar(new Error('Sem conexão com o servidor.'));
      xhr.send(formData);
    });
  }

  return {
    verificar,
    get: (u) => chamar('GET', u),
    post: (u, c) => chamar('POST', u, c === undefined ? {} : c),
    patch: (u, c) => chamar('PATCH', u, c),
    del: (u) => chamar('DELETE', u),
    enviar,
  };
})();
