// O tick a cada segundo: lê a tela, decide se houve erro/acerto/branco e guarda. Igual na extensão e no userscript;
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
    let anterior = null;
    let anteriorEstavel = false;
    const tratadosAcerto = Object.create(null);

    async function dispositivo() {
      let dev = await armazenamento.ler('dev', null);
      if (!dev) {
        dev = T.novoDispositivo();
        await armazenamento.gravar('dev', dev);
      }
      return dev;
    }

    function atualizarAnterior(idAtual, tela, q) {
      if (idAtual && tela.situacao === 'sem_resolver' && q) {
        if (anterior && anterior.id === idAtual && anterior.situacao === 'sem_resolver') {
          anteriorEstavel = true;
          anterior = { id: idAtual, situacao: tela.situacao, questao: Object.assign({}, q) };
        } else {
          anteriorEstavel = false;
          anterior = { id: idAtual, situacao: tela.situacao, questao: Object.assign({}, q) };
        }
        return;
      }
      anterior = idAtual && q ? { id: idAtual, situacao: tela.situacao, questao: Object.assign({}, q) } : null;
      anteriorEstavel = false;
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
        const idAtual = q && q.id ? q.id : null;

        if (
          anteriorEstavel &&
          anterior &&
          anterior.id &&
          anterior.id !== idAtual &&
          anterior.situacao === 'sem_resolver' &&
          (!anterior.questao.marc || anterior.questao.marc === '')
        ) {
          const errosB = await armazenamento.ler('erros', {});
          const rBranco = T.registrar(errosB, anterior.questao, 'branco', agoraIso, dev, agoraMs);

          if (rBranco.mudou) {
            await armazenamento.gravar('erros', rBranco.erros);
            avisar('○ Em branco guardado (' + Object.keys(rBranco.erros).length + ' no total)');
          }
        }

        const passo = T.proximoEstado(estado, idAtual, tela.situacao, agoraMs);
        estado = passo.estado;

        if (q && q.id && tela.situacao === 'acertou' && !tratadosAcerto[q.id]) {
          const errosA = await armazenamento.ler('erros', {});
          const rA = T.registrar(errosA, q, 'acerto', agoraIso, dev, agoraMs);
          if (rA.mudou) {
            await armazenamento.gravar('erros', rA.erros);
            tratadosAcerto[q.id] = true;
            avisar('✓ Acerto guardado (' + Object.keys(rA.erros).length + ' no total)');
            atualizarAnterior(idAtual, tela, q);
            return 'acerto';
          }
          tratadosAcerto[q.id] = true;
        }

        if (q && q.id && tela.situacao === 'errou') {
          const erros = await armazenamento.ler('erros', {});
          const historico = (await armazenamento.ler('modoHistorico', true)) !== false;
          const acao = passo.acao === 'historico' && !historico ? null : passo.acao;
          const r = T.registrar(erros, q, acao, agoraIso, dev, agoraMs);
          if (r.mudou) {
            await armazenamento.gravar('erros', r.erros);
            if (acao === 'erro' || (acao === 'historico' && !erros[q.id])) {
              const total = Object.keys(r.erros).length;
              let msg = r.registro.v >= 2 ? '⚠ Errada ' + r.registro.v + ' vezes!' : '✗ Erro guardado (' + total + ' no total)';
              if (acao === 'historico') msg = '✗ Erro do histórico guardado (' + total + ' no total)';
              if (!r.registro.com) msg += ' Abra "Ver resolução" para guardar o comentário.';
              avisar(msg);
            }
            atualizarAnterior(idAtual, tela, q);
            return acao || 'complemento';
          }
        }

        atualizarAnterior(idAtual, tela, q);
        return null;
      } finally {
        ocupado = false;
      }
    }

    async function exportacao() {
      const erros = await armazenamento.ler('erros', {});
      const cads = await armazenamento.ler('cads', {});
      const modo = (await armazenamento.ler('modoExportacao', 'todas')) || 'todas';
      return T.exportar(erros, cads, await dispositivo(), relogio(), { modoExportacao: modo });
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
