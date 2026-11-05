const test = require('node:test');
const assert = require('node:assert/strict');
const T = require('../core/nucleo.js');

const CABECALHO = `Matéria: Direito Tributário
Assunto: Simples Nacional
#12345678 CEBRASPE - 2020 - SEFAZ-DF
Enunciado da questão`;

function leitura(extra) {
  return Object.assign(
    { id: 'q1', enun: 'O contribuinte optante pelo Simples Nacional...', mat: 'Direito Tributário', marc: 'B', gab: 'C' },
    extra
  );
}

test('identidade usa o id do TEC e, sem ele, o hash do enunciado', () => {
  assert.equal(T.identidade('12.345.678', 'x'), 'q12345678');
  const h = T.identidade('', 'Enunciado longo');
  assert.match(h, /^h[0-9a-f]{8}$/);
  assert.equal(T.identidade(null, 'Enunciado longo'), h);
  assert.equal(T.identidade('', '   '), null);
});

test('o hash considera só os primeiros 600 caracteres', () => {
  const base = 'a'.repeat(600);
  assert.equal(T.identidade('', base + 'x'), T.identidade('', base + 'y'));
});

test('impressão digital igual para o mesmo texto com acentos, caixa e espaços diferentes', () => {
  assert.equal(T.impressaoDigital('Ação  Pública\nÉ'), T.impressaoDigital('acao publica é'));
  assert.equal(T.impressaoDigital('x'.repeat(400)).length, 300);
});

test('data local ISO com o fuso, não UTC', () => {
  const iso = T.dataLocalIso(new Date(2026, 10, 2, 21, 15, 3));
  assert.match(iso, /^2026-11-02T21:15:03[+-]\d{2}:\d{2}$/);
});

test('lê matéria, assunto e prova do cabeçalho', () => {
  assert.deepEqual(T.lerCabecalho(CABECALHO), {
    mat: 'Direito Tributário',
    ass: 'Simples Nacional',
    idQuestao: '12345678',
    banca: 'CEBRASPE',
    ano: '2020',
    orgao: 'SEFAZ-DF',
  });
});

test('totais do caderno no plural e no singular', () => {
  assert.deepEqual(T.lerTotaisCaderno('Questão 2 de 484 (2 Resolvidas, 0 Acertos e 2 Erros)'), {
    atual: 2, tot: 484, res: 2, ac: 0, er: 2,
  });
  assert.deepEqual(T.lerTotaisCaderno('Questao 1 de 10 (1 Resolvida, 1 Acerto e 0 Erros)'), {
    atual: 1, tot: 10, res: 1, ac: 1, er: 0,
  });
  assert.equal(T.lerTotaisCaderno('nada aqui'), null);
});

test('gabarito em letra e em certo/errado', () => {
  assert.equal(T.lerGabarito('Você errou! Gabarito: c'), 'C');
  assert.equal(T.lerGabarito('Gabarito: ERRADO'), 'Errado');
});

function rodar(passos) {
  let estado = null;
  const acoes = [];
  for (const [id, situacao, agora] of passos) {
    const r = T.proximoEstado(estado, id, situacao, agora);
    estado = r.estado;
    if (r.acao) acoes.push(r.acao);
  }
  return acoes;
}

test('2 s sem resolver e depois errada conta um erro', () => {
  assert.deepEqual(rodar([['q1', 'sem_resolver', 0], ['q1', 'sem_resolver', 2000], ['q1', 'errou', 3000], ['q1', 'errou', 4000]]), ['erro']);
});

test('reabrir uma questão já errada não conta de novo', () => {
  assert.deepEqual(rodar([['q1', 'errou', 0], ['q1', 'errou', 1000], ['q2', 'sem_resolver', 2000], ['q1', 'errou', 3000]]), [
    'historico',
    'historico',
  ]);
});

test('menos de 2 s sem resolver não arma o erro', () => {
  assert.deepEqual(rodar([['q1', 'sem_resolver', 0], ['q1', 'errou', 1500]]), ['historico']);
});

test('resolver de novo depois de 2 s conta outra vez', () => {
  assert.deepEqual(
    rodar([['q1', 'sem_resolver', 0], ['q1', 'sem_resolver', 2000], ['q1', 'errou', 2500], ['q1', 'sem_resolver', 3000], ['q1', 'sem_resolver', 5000], ['q1', 'errou', 5500]]),
    ['erro', 'erro']
  );
});

test('modo histórico registra sem data e não aumenta v de questão conhecida', () => {
  let r = T.registrar({}, leitura(), 'historico', '2026-11-02T10:00:00-03:00', 'dA', 1);
  assert.equal(r.registro.v, 1);
  assert.deepEqual(r.registro.ds, []);
  assert.equal(r.registro.origem, 'historico');
  r = T.registrar(r.erros, leitura(), 'erro', '2026-11-03T10:00:00-03:00', 'dA', 2);
  assert.equal(r.registro.v, 1);
  assert.equal(r.registro.origem, 'tempo_real');
  const depois = T.registrar(r.erros, leitura(), 'historico', '2026-11-04T10:00:00-03:00', 'dA', 3);
  assert.equal(depois.mudou, false);
  assert.equal(depois.registro.v, 1);
});

test('erro repetido aumenta v e guarda as datas', () => {
  let r = T.registrar({}, leitura(), 'erro', '2026-11-02T10:00:00-03:00', 'dA', 1);
  r = T.registrar(r.erros, leitura(), 'erro', '2026-11-05T10:00:00-03:00', 'dA', 2);
  assert.equal(r.registro.v, 2);
  assert.deepEqual(r.registro.ds, ['2026-11-02T10:00:00-03:00', '2026-11-05T10:00:00-03:00']);
  assert.equal(r.registro.d, '2026-11-02');
});

test('comentário que chega depois é preservado e não regrava sem mudança', () => {
  let r = T.registrar({}, leitura(), 'erro', '2026-11-02T10:00:00-03:00', 'dA', 1);
  r = T.registrar(r.erros, leitura({ com: 'Comentário do professor', prof: 'Fulano' }), null, '2026-11-02T10:00:05-03:00', 'dA', 2);
  assert.equal(r.mudou, true);
  assert.equal(r.registro.com, 'Comentário do professor');
  const de_novo = T.registrar(r.erros, leitura({ com: 'Comentário do professor' }), null, '2026-11-02T10:00:09-03:00', 'dA', 3);
  assert.equal(de_novo.mudou, false);
  const sem = T.registrar(r.erros, leitura({ com: '' }), null, '2026-11-02T10:00:10-03:00', 'dA', 4);
  assert.equal(sem.registro.com, 'Comentário do professor');
});

test('dois aparelhos no mesmo dia somam v = 2', () => {
  const pc = T.registrar({}, leitura(), 'erro', '2026-11-02T09:00:00-03:00', 'dPC', 1).registro;
  const tablet = T.registrar({}, leitura(), 'erro', '2026-11-02T21:00:00-03:00', 'dTAB', 2).registro;
  const { erros, mudou } = T.mesclarErros([pc], [tablet]);
  assert.equal(mudou, true);
  assert.equal(erros.length, 1);
  assert.equal(erros[0].v, 2);
  assert.equal(erros[0].dev, 'dPC');
});

test('mesclar casa pela impressão digital quando o id muda', () => {
  const a = T.registrar({}, leitura({ id: 'q1' }), 'erro', '2026-11-02T09:00:00-03:00', 'd', 1).registro;
  const b = T.registrar({}, leitura({ id: 'h0000abcd' }), 'erro', '2026-11-03T09:00:00-03:00', 'd', 2).registro;
  const { erros } = T.mesclarErros([a], [b]);
  assert.equal(erros.length, 1);
  assert.equal(erros[0].id, 'q1');
  assert.equal(erros[0].v, 2);
});

test('mesclar o mesmo arquivo de novo não muda nada', () => {
  const a = T.registrar({}, leitura({ com: 'c' }), 'erro', '2026-11-02T09:00:00-03:00', 'd', 1).registro;
  const r = T.mesclarErros([a], [JSON.parse(JSON.stringify(a))]);
  assert.equal(r.mudou, false);
  assert.equal(r.erros[0], a);
});

test('histórico sem data não soma com tempo real', () => {
  const hist = T.registrar({}, leitura(), 'historico', '2026-11-02T09:00:00-03:00', 'dTAB', 1).registro;
  const real = T.registrar({}, leitura(), 'erro', '2026-11-03T09:00:00-03:00', 'dPC', 2).registro;
  const { erros } = T.mesclarErros([hist], [real]);
  assert.equal(erros[0].v, 1);
  assert.equal(erros[0].origem, 'tempo_real');
});

test('caderno só atualiza quando res não diminui, também entre aparelhos', () => {
  const c = { id: 'c1', res: 5, ac: 3, er: 2, tot: 10, t: 1 };
  let r = T.atualizarCaderno({ c1: c }, Object.assign({}, c, { res: 3, ac: 1, er: 2, t: 2 }));
  assert.equal(r.mudou, false);
  r = T.atualizarCaderno({ c1: c }, Object.assign({}, c, { res: 6, ac: 3, er: 3, t: 3 }));
  assert.equal(r.cads.c1.res, 6);
  const m = T.mesclarCadernos([c], [Object.assign({}, c, { res: 4, t: 9 })]);
  assert.equal(m.mudou, false);
  assert.equal(m.cads[0].res, 5);
});

test('exportação válida e campo desconhecido vira aviso', () => {
  const arquivo = T.exportar({ q1: { id: 'q1' } }, {}, 'dA', new Date(2026, 10, 2));
  assert.equal(arquivo.app, 'tec-erros');
  const lido = T.lerExportacao(JSON.stringify(Object.assign({}, arquivo, { extra: 1 })));
  assert.equal(lido.dados.erros.length, 1);
  assert.deepEqual(lido.avisos, ['campo desconhecido ignorado: extra']);
  assert.throws(() => T.lerExportacao('{"app":"outro","v":1}'), /campo app/);
});
