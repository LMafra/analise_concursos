// Núcleo sem DOM: identidade, datas, leitura de texto, máquina de estados e mesclagem.
// Roda no Chrome, no Violentmonkey, no caderno.html e no node (testes).
(function (raiz) {
  'use strict';

  const APP = 'tec-erros';
  const VERSAO = 1;
  const ESPERA_SEM_RESOLVER_MS = 2000;
  const TAMANHO_HASH = 600;
  const TAMANHO_DIGITAL = 300;
  const CAMPOS_TEXTO = ['mat', 'ass', 'cad', 'banca', 'orgao', 'ano', 'enun', 'marc', 'gab', 'prof', 'url'];

  function normalizar(texto) {
    return String(texto || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim();
  }

  // FNV-1a de 32 bits: estável entre navegadores e fácil de repetir em Python.
  function hash(texto) {
    let h = 0x811c9dc5;
    for (const unidade of String(texto)) {
      const codigo = unidade.codePointAt(0);
      h ^= codigo;
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h.toString(16).padStart(8, '0');
  }

  function impressaoDigital(enunciado) {
    return normalizar(enunciado).slice(0, TAMANHO_DIGITAL);
  }

  function identidade(idQuestao, enunciado) {
    const id = String(idQuestao || '').replace(/\D/g, '');
    if (id) return 'q' + id;
    const texto = String(enunciado || '').trim();
    return texto ? 'h' + hash(texto.slice(0, TAMANHO_HASH)) : null;
  }

  function doisDigitos(n) {
    return String(n).padStart(2, '0');
  }

  // Data e hora locais com o fuso (toISOString daria UTC).
  function dataLocalIso(data) {
    const d = data instanceof Date ? data : new Date(data);
    const minutos = -d.getTimezoneOffset();
    const sinal = minutos >= 0 ? '+' : '-';
    const abs = Math.abs(minutos);
    return (
      d.getFullYear() + '-' + doisDigitos(d.getMonth() + 1) + '-' + doisDigitos(d.getDate()) +
      'T' + doisDigitos(d.getHours()) + ':' + doisDigitos(d.getMinutes()) + ':' + doisDigitos(d.getSeconds()) +
      sinal + doisDigitos(Math.floor(abs / 60)) + ':' + doisDigitos(abs % 60)
    );
  }

  function dia(iso) {
    return String(iso || '').slice(0, 10);
  }

  function lerCabecalho(texto) {
    const t = String(texto || '');
    const linha = (rotulo) => {
      const m = t.match(new RegExp(rotulo + '\\s*:\\s*([^\\n]+)', 'i'));
      return m ? m[1].trim() : '';
    };
    const prova = t.match(/#(\d{3,})\s+([^\n]+?)\s+-\s+(\d{4})\s+-\s+([^\n]+)/);
    return {
      mat: linha('Mat[eé]ria'),
      ass: linha('Assunto'),
      idQuestao: prova ? prova[1] : '',
      banca: prova ? prova[2].trim() : '',
      ano: prova ? prova[3] : '',
      orgao: prova ? prova[4].trim() : '',
    };
  }

  function lerTotaisCaderno(texto) {
    const m = String(texto || '').match(
      /Quest[aã]o\s+(\d+)\s+de\s+(\d+)\s*\(\s*(\d+)\s+Resolvidas?\s*,\s*(\d+)\s+Acertos?\s+e\s+(\d+)\s+Erros?\s*\)/i
    );
    if (!m) return null;
    return { atual: +m[1], tot: +m[2], res: +m[3], ac: +m[4], er: +m[5] };
  }

  function lerGabarito(texto) {
    const m = String(texto || '').match(/Gabarito\s*:\s*(Certo|Errado|[A-E])\b/i);
    if (!m) return '';
    const valor = m[1];
    return valor.length === 1 ? valor.toUpperCase() : valor[0].toUpperCase() + valor.slice(1).toLowerCase();
  }

  // Máquina de estados de uma questão na tela. situacao: sem_resolver, errou, acertou ou nenhuma.
  // Devolve o estado novo e a ação: 'erro' (conta), 'historico' (já veio errada) ou null.
  function proximoEstado(estado, id, situacao, agora) {
    let e = estado && estado.id === id ? Object.assign({}, estado) : { id: id, desde: null, armado: false, tratado: false };
    let acao = null;
    if (!id || situacao === 'nenhuma') return { estado: e, acao: null };
    if (situacao === 'sem_resolver') {
      if (e.desde === null) e.desde = agora;
      if (agora - e.desde >= ESPERA_SEM_RESOLVER_MS) {
        e.armado = true;
        e.tratado = false;
      }
    } else {
      e.desde = null;
      if (situacao === 'errou' && !e.tratado) acao = e.armado ? 'erro' : 'historico';
      e.tratado = true;
      e.armado = false;
    }
    return { estado: e, acao: acao };
  }

  function vazio(valor) {
    return valor === undefined || valor === null || valor === '' || (Array.isArray(valor) && valor.length === 0);
  }

  function contagem(ds) {
    return ds.length > 0 ? ds.length : 1;
  }

  function ordenarUnicos(lista) {
    return Array.from(new Set(lista.filter(Boolean))).sort();
  }

  function novoRegistro(leitura, acao, agoraIso, dev, agoraMs) {
    const ds = acao === 'erro' ? [agoraIso] : [];
    const r = {
      id: leitura.id,
      fp: impressaoDigital(leitura.enun),
      d: dia(agoraIso),
      t: agoraMs,
      v: contagem(ds),
      ds: ds,
      dev: dev,
      origem: acao === 'erro' ? 'tempo_real' : 'historico',
    };
    for (const campo of CAMPOS_TEXTO) if (!vazio(leitura[campo])) r[campo] = leitura[campo];
    if (!vazio(leitura.alts)) r.alts = leitura.alts;
    if (!vazio(leitura.com)) r.com = leitura.com;
    return r;
  }

  // Funde dois registros da mesma questão; devolve `a` (o mesmo objeto) se nada mudou.
  function fundir(a, b) {
    const r = Object.assign({}, a);
    for (const campo of CAMPOS_TEXTO.concat(['alts', 'fp'])) if (vazio(r[campo]) && !vazio(b[campo])) r[campo] = b[campo];
    if (!vazio(b.com) && String(b.com).length > String(r.com || '').length) {
      r.com = b.com;
      if (!vazio(b.prof)) r.prof = b.prof;
    }
    r.ds = ordenarUnicos((a.ds || []).concat(b.ds || []));
    r.v = contagem(r.ds);
    r.origem = a.origem === 'tempo_real' || b.origem === 'tempo_real' || r.ds.length > 0 ? 'tempo_real' : 'historico';
    const datas = [a.d, b.d, r.ds.length ? dia(r.ds[0]) : ''].filter(Boolean).sort();
    if (datas.length) r.d = datas[0];
    if (b.dev && (!a.dev || (b.d && a.d && b.d < a.d))) r.dev = b.dev;
    if (JSON.stringify(Object.assign({}, r, { t: a.t })) === JSON.stringify(a)) return a;
    r.t = Math.max(a.t || 0, b.t || 0);
    return r;
  }

  // Aplica a ação de um tick à coleção de erros (objeto por id).
  function registrar(erros, leitura, acao, agoraIso, dev, agoraMs) {
    const atual = erros[leitura.id];
    let registro;
    if (!atual) {
      if (acao !== 'erro' && acao !== 'historico') return { erros: erros, registro: null, mudou: false };
      registro = novoRegistro(leitura, acao, agoraIso, dev, agoraMs);
    } else {
      const extra = novoRegistro(leitura, acao === 'erro' ? 'erro' : 'historico', agoraIso, dev, agoraMs);
      if (acao !== 'erro') extra.ds = [];
      registro = fundir(atual, extra);
      if (registro !== atual) registro.t = agoraMs;
    }
    if (registro === atual) return { erros: erros, registro: atual, mudou: false };
    const novos = Object.assign({}, erros);
    novos[leitura.id] = registro;
    return { erros: novos, registro: registro, mudou: true };
  }

  function atualizarCaderno(cads, caderno) {
    const atual = cads[caderno.id];
    if (atual && (caderno.res < atual.res || (caderno.res === atual.res && caderno.ac === atual.ac && caderno.er === atual.er && caderno.tot === atual.tot))) {
      return { cads: cads, mudou: false };
    }
    const novos = Object.assign({}, cads);
    novos[caderno.id] = Object.assign({}, atual || {}, caderno);
    return { cads: novos, mudou: true };
  }

  function mesclarErros(base, novos) {
    const lista = Array.isArray(base) ? base.slice() : Object.values(base || {});
    const porId = new Map();
    const porDigital = new Map();
    lista.forEach((r, i) => {
      porId.set(r.id, i);
      if (r.fp) porDigital.set(r.fp, i);
    });
    let mudou = false;
    for (const original of novos || []) {
      const r = Object.assign({ ds: [] }, original);
      if (!r.fp && r.enun) r.fp = impressaoDigital(r.enun);
      if (!Array.isArray(r.ds)) r.ds = [];
      let i = porId.has(r.id) ? porId.get(r.id) : r.fp && porDigital.has(r.fp) ? porDigital.get(r.fp) : -1;
      if (i < 0) {
        r.v = contagem(r.ds);
        lista.push(r);
        i = lista.length - 1;
        mudou = true;
      } else {
        const fundido = fundir(lista[i], r);
        if (fundido !== lista[i]) {
          lista[i] = fundido;
          mudou = true;
        }
      }
      porId.set(r.id, i);
      if (r.fp) porDigital.set(r.fp, i);
    }
    return { erros: lista, mudou: mudou };
  }

  function mesclarCadernos(base, novos) {
    const porId = {};
    for (const c of Array.isArray(base) ? base : Object.values(base || {})) porId[c.id] = c;
    let mudou = false;
    for (const c of novos || []) {
      const atual = porId[c.id];
      if (!atual || c.res > atual.res || (c.res === atual.res && (c.t || 0) > (atual.t || 0))) {
        porId[c.id] = Object.assign({}, atual || {}, c);
        mudou = true;
      }
    }
    return { cads: Object.values(porId), mudou: mudou };
  }

  function exportar(erros, cads, dev, agora) {
    return {
      app: APP,
      v: VERSAO,
      em: dataLocalIso(agora || new Date()),
      dev: dev,
      erros: Object.values(erros || {}),
      cads: Object.values(cads || {}),
    };
  }

  // Lê um arquivo exportado; devolve {dados, avisos} ou lança Error com o motivo.
  function lerExportacao(texto) {
    const dados = typeof texto === 'string' ? JSON.parse(texto) : texto;
    if (!dados || dados.app !== APP) throw new Error('não é um arquivo do tec-erros (campo app)');
    if (dados.v !== VERSAO) throw new Error('versão ' + dados.v + ' do arquivo; esperada ' + VERSAO);
    const conhecidos = ['app', 'v', 'em', 'dev', 'erros', 'cads'];
    const avisos = Object.keys(dados)
      .filter((k) => !conhecidos.includes(k))
      .map((k) => 'campo desconhecido ignorado: ' + k);
    return { dados: { erros: dados.erros || [], cads: dados.cads || [], dev: dados.dev, em: dados.em }, avisos: avisos };
  }

  function novoDispositivo(aleatorio) {
    const r = aleatorio || Math.random;
    let id = 'd';
    for (let i = 0; i < 8; i++) id += Math.floor(r() * 16).toString(16);
    return id;
  }

  const TecErros = {
    APP, VERSAO, ESPERA_SEM_RESOLVER_MS,
    normalizar, hash, impressaoDigital, identidade, dataLocalIso, dia,
    lerCabecalho, lerTotaisCaderno, lerGabarito, proximoEstado,
    fundir, registrar, atualizarCaderno, mesclarErros, mesclarCadernos,
    exportar, lerExportacao, novoDispositivo,
  };
  if (typeof module === 'object' && module.exports) module.exports = TecErros;
  else raiz.TecErros = Object.assign(raiz.TecErros || {}, TecErros);
})(typeof globalThis !== 'undefined' ? globalThis : this);
