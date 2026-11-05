// O tick a cada segundo: lê a tela, decide se houve erro e guarda. Igual na extensão e no userscript;
// muda só o armazenamento ({ler, gravar}, assíncronos) e o aviso na tela.
(function (raiz) {
  'use strict';

  const node = typeof module === 'object' && module.exports;
  const T = node ? require('./nucleo.js') : raiz.TecErros;

  function criarColetor(opcoes) {
    const { armazenamento, ler, avisar } = opcoes;
    const relogio = opcoes.relogio || (() => new Date());
    let estado = null;
    let ocupado = false;

    async function dispositivo() {
      let dev = await armazenamento.ler('dev', null);
      if (!dev) {
        dev = T.novoDispositivo();
        await armazenamento.gravar('dev', dev);
      }
      return dev;
    }

    async function tick() {
      if (ocupado) return null;
      ocupado = true;
      try {
        const agora = relogio();
        const agoraMs = agora.getTime();
        const agoraIso = T.dataLocalIso(agora);
        const tela = ler();
        const dev = await dispositivo();
        if (tela.caderno) {
          const cads = await armazenamento.ler('cads', {});
          const c = T.atualizarCaderno(cads, Object.assign({}, tela.caderno, { d: T.dia(agoraIso), t: agoraMs, dev: dev }));
          if (c.mudou) await armazenamento.gravar('cads', c.cads);
        }
        const q = tela.questao;
        const passo = T.proximoEstado(estado, q && q.id, tela.situacao, agoraMs);
        estado = passo.estado;
        if (!q || !q.id || tela.situacao !== 'errou') return null;
        const erros = await armazenamento.ler('erros', {});
        const historico = (await armazenamento.ler('modoHistorico', true)) !== false;
        const acao = passo.acao === 'historico' && !historico ? null : passo.acao;
        const r = T.registrar(erros, q, acao, agoraIso, dev, agoraMs);
        if (!r.mudou) return null;
        await armazenamento.gravar('erros', r.erros);
        if (acao === 'erro' || (acao === 'historico' && !erros[q.id])) {
          const total = Object.keys(r.erros).length;
          let msg = r.registro.v >= 2 ? '⚠ Errada ' + r.registro.v + ' vezes!' : '✗ Erro guardado (' + total + ' no total)';
          if (acao === 'historico') msg = '✗ Erro do histórico guardado (' + total + ' no total)';
          if (!r.registro.com) msg += ' Abra "Ver resolução" para guardar o comentário.';
          avisar(msg);
        }
        return acao || 'complemento';
      } finally {
        ocupado = false;
      }
    }

    async function exportacao() {
      const erros = await armazenamento.ler('erros', {});
      const cads = await armazenamento.ler('cads', {});
      return T.exportar(erros, cads, await dispositivo(), relogio());
    }

    async function limpar() {
      await armazenamento.gravar('erros', {});
      await armazenamento.gravar('cads', {});
    }

    return { tick, exportacao, limpar, dispositivo };
  }

  function nomeDoArquivo(exportacao) {
    return 'tec-erros-' + exportacao.dev + '-' + String(exportacao.em).slice(0, 10) + '.json';
  }

  // Aviso pequeno no canto inferior direito por 5 segundos.
  function avisoNaTela(doc) {
    return function (mensagem) {
      const id = 'tec-erros-aviso';
      let el = doc.getElementById(id);
      if (!el) {
        el = doc.createElement('div');
        el.id = id;
        el.style.cssText =
          'position:fixed;right:12px;bottom:12px;z-index:2147483647;max-width:320px;padding:8px 12px;' +
          'background:#1f2933;color:#fff;font:14px/1.4 system-ui,sans-serif;border-radius:8px;box-shadow:0 2px 8px #0005';
        doc.body.appendChild(el);
      }
      el.textContent = mensagem;
      el.style.display = 'block';
      clearTimeout(el._tecErrosTimer);
      el._tecErrosTimer = setTimeout(() => (el.style.display = 'none'), 5000);
    };
  }

  const Coletor = { criarColetor, nomeDoArquivo, avisoNaTela };
  if (node) module.exports = Coletor;
  else raiz.TecErros = Object.assign(raiz.TecErros || {}, { Coletor: Coletor });
})(typeof globalThis !== 'undefined' ? globalThis : this);
