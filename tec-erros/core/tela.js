// Leitura da tela do TEC (só leitura). Os seletores são hipóteses; o diagnóstico mostra o que cada um achou.
(function (raiz) {
  'use strict';

  const T = typeof module === 'object' && module.exports ? require('./nucleo.js') : raiz.TecErros;

  const SELETORES = {
    errou: '.questao-enunciado-resolucao-errou',
    acertou: '.questao-enunciado-resolucao-acertou',
    enunciado: '[tec-formatar-html="vm.questao.enunciado"], .questao-enunciado-texto',
    alternativas: '.questao-enunciado-alternativas > li',
    letra: '.questao-enunciado-alternativa-opcao',
    textoAlternativa: '.questao-enunciado-alternativa-texto',
    marcada: '.questao-alternativa-selecionada',
    comentario: '[tec-formatar-html="vm.comentario.textoComentario"]',
    professor: '[ng-bind="vm.comentario.nomeProfessor"]',
  };

  function texto(el) {
    return el ? String(el.innerText || el.textContent || '').trim() : '';
  }

  function visivel(el) {
    if (!el) return false;
    if (typeof el.getClientRects === 'function' && el.getClientRects().length === 0) return false;
    return true;
  }

  function primeiro(doc, seletor) {
    const lista = Array.from(doc.querySelectorAll(seletor));
    return lista.find(visivel) || null;
  }

  function situacao(doc) {
    if (primeiro(doc, SELETORES.errou)) return 'errou';
    if (primeiro(doc, SELETORES.acertou)) return 'acertou';
    if (primeiro(doc, SELETORES.enunciado)) return 'sem_resolver';
    return 'nenhuma';
  }

  function letraDe(li) {
    return texto(li.querySelector(SELETORES.letra)).replace(/[).\s]/g, '');
  }

  // Lê a questão visível; `angular` (de lerAngular) complementa o texto da tela.
  function lerQuestao(doc, angular, url) {
    const a = angular || {};
    const enunciadoEl = primeiro(doc, SELETORES.enunciado);
    const enun = texto(enunciadoEl) || a.enunciado || '';
    const corpo = texto(doc.body);
    const cab = T.lerCabecalho(corpo);
    const itens = Array.from(doc.querySelectorAll(SELETORES.alternativas));
    const alts = itens.map((li) => ({ l: letraDe(li), t: texto(li.querySelector(SELETORES.textoAlternativa)) || texto(li) }));
    const marcadaEl = doc.querySelector(SELETORES.marcada);
    const liMarcado = marcadaEl ? marcadaEl.closest('li') : null;
    let marc = liMarcado ? letraDe(liMarcado) || texto(liMarcado.querySelector(SELETORES.textoAlternativa)) : '';
    if (!marc && a.alternativaSelecionada) marc = letraPorIndice(a.alternativaSelecionada, alts);
    let gab = T.lerGabarito(texto(primeiro(doc, SELETORES.errou)));
    if (!gab && a.numeroAlternativaCorreta) gab = letraPorIndice(a.numeroAlternativaCorreta, alts);
    const idQuestao = cab.idQuestao || a.idQuestao || '';
    return {
      id: T.identidade(idQuestao, enun),
      enun: enun,
      alts: alts,
      marc: marc,
      gab: gab,
      mat: cab.mat || a.nomeMateria || '',
      ass: cab.ass || a.assunto || '',
      banca: cab.banca || a.bancaSigla || '',
      orgao: cab.orgao || a.orgaoNome || '',
      ano: cab.ano || '',
      com: texto(doc.querySelector(SELETORES.comentario)) || a.comentario || '',
      prof: texto(doc.querySelector(SELETORES.professor)) || a.professor || '',
      cad: tituloCaderno(doc),
      url: url || '',
    };
  }

  function letraPorIndice(valor, alts) {
    const n = Number(valor);
    if (Number.isInteger(n) && n >= 1 && alts[n - 1]) return alts[n - 1].l || String(n);
    return String(valor);
  }

  function tituloCaderno(doc) {
    return String(doc.title || '').replace(/\s*[-|]\s*TEC Concursos.*$/i, '').trim();
  }

  function lerCaderno(doc, url, agoraIso, agoraMs, dev) {
    const m = String(url || '').match(/cadernos?\/(\d+)/i);
    const totais = T.lerTotaisCaderno(texto(doc.body));
    if (!m || !totais) return null;
    return {
      id: 'c' + m[1],
      cad: tituloCaderno(doc),
      mat: T.lerCabecalho(texto(doc.body)).mat,
      tot: totais.tot,
      res: totais.res,
      ac: totais.ac,
      er: totais.er,
      d: T.dia(agoraIso),
      t: agoraMs,
      dev: dev,
    };
  }

  // Roda no contexto da página (MAIN no Chrome, unsafeWindow no Violentmonkey). Só lê o scope.
  function lerAngular(win, doc) {
    const ng = win && win.angular;
    const el = doc.querySelector(SELETORES.enunciado);
    if (!ng || !el) return { detectado: !!ng, questao: null };
    let scope = null;
    try {
      scope = ng.element(el).scope();
    } catch (erro) {
      return { detectado: true, questao: null };
    }
    for (let i = 0; scope && i < 30; i++, scope = scope.$parent) {
      const vm = scope.vm;
      if (vm && vm.questao) {
        const q = vm.questao;
        const c = vm.comentario || {};
        return {
          detectado: true,
          questao: {
            idQuestao: q.idQuestao || '',
            nomeMateria: q.nomeMateria || '',
            bancaSigla: q.bancaSigla || '',
            orgaoNome: q.orgaoNome || '',
            numeroAlternativaCorreta: q.numeroAlternativaCorreta || '',
            alternativaSelecionada: q.alternativaSelecionada || '',
            anulada: !!q.anulada,
            formatoQuestao: q.formatoQuestao || '',
            enunciado: '',
            assunto: vm.nomeAssuntoExibicao || '',
            comentario: c.textoComentario ? String(c.textoComentario).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() : '',
            professor: c.nomeProfessor || '',
          },
        };
      }
    }
    return { detectado: true, questao: null };
  }

  function diagnostico(doc, angular, url, agoraIso) {
    const contagem = {};
    for (const [nome, seletor] of Object.entries(SELETORES)) contagem[nome] = doc.querySelectorAll(seletor).length;
    return {
      url: url,
      seletores: contagem,
      angular: angular ? (angular.detectado ? (angular.questao ? 'sim, com vm.questao' : 'sim, sem vm.questao') : 'não') : 'não consultado',
      situacao: situacao(doc),
      questao: lerQuestao(doc, angular && angular.questao, url),
      caderno: lerCaderno(doc, url, agoraIso, 0, ''),
    };
  }

  const Tela = { SELETORES, situacao, lerQuestao, lerCaderno, lerAngular, diagnostico };
  if (typeof module === 'object' && module.exports) module.exports = Tela;
  else raiz.TecErros = Object.assign(raiz.TecErros || {}, { Tela: Tela });
})(typeof globalThis !== 'undefined' ? globalThis : this);
