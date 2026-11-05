const test = require('node:test');
const assert = require('node:assert/strict');
const Tela = require('../core/tela.js');

// Documento falso: cada seletor da tabela SELETORES devolve os elementos dados.
function documento(porSeletor, corpo, titulo) {
  const el = (texto, extra) => Object.assign({ innerText: texto, getClientRects: () => [1], querySelector: () => null }, extra);
  const mapa = {};
  for (const [nome, valor] of Object.entries(porSeletor)) mapa[Tela.SELETORES[nome]] = valor.map((v) => (typeof v === 'string' ? el(v) : v));
  return {
    title: titulo || 'Caderno 20. Simples Nacional - TEC Concursos',
    body: el(corpo || ''),
    querySelectorAll: (s) => mapa[s] || [],
    querySelector: (s) => (mapa[s] || [])[0] || null,
  };
}

test('situação pela classe da resolução', () => {
  assert.equal(Tela.situacao(documento({ errou: ['Gabarito: C'], enunciado: ['x'] })), 'errou');
  assert.equal(Tela.situacao(documento({ acertou: ['ok'] })), 'acertou');
  assert.equal(Tela.situacao(documento({ enunciado: ['x'] })), 'sem_resolver');
  assert.equal(Tela.situacao(documento({})), 'nenhuma');
});

test('lê a questão pelo texto e completa pelo AngularJS', () => {
  const doc = documento(
    { errou: ['Você errou. Gabarito: C'], enunciado: ['Enunciado da questão'] },
    'Matéria: Direito Tributário\nAssunto: Simples Nacional\n#12345678 CEBRASPE - 2020 - SEFAZ-DF'
  );
  const q = Tela.lerQuestao(doc, { professor: 'Fulano', comentario: 'Porque sim' }, 'https://www.tecconcursos.com.br/x');
  assert.equal(q.id, 'q12345678');
  assert.equal(q.gab, 'C');
  assert.equal(q.mat, 'Direito Tributário');
  assert.equal(q.com, 'Porque sim');
  assert.equal(q.cad, 'Caderno 20. Simples Nacional');
});

test('caderno pelo id da URL e pelos totais', () => {
  const doc = documento({}, 'Questão 2 de 484 (2 Resolvidas, 0 Acertos e 2 Erros)');
  const c = Tela.lerCaderno(doc, 'https://www.tecconcursos.com.br/questoes/cadernos/87654321', '2026-11-02T10:00:00-03:00', 5, 'dA');
  assert.deepEqual(
    { id: c.id, tot: c.tot, res: c.res, ac: c.ac, er: c.er, d: c.d },
    { id: 'c87654321', tot: 484, res: 2, ac: 0, er: 2, d: '2026-11-02' }
  );
  assert.equal(Tela.lerCaderno(doc, 'https://www.tecconcursos.com.br/', '', 0, ''), null);
});

test('lerAngular sobe pelos $parent até vm.questao e não altera nada', () => {
  const raiz = { vm: { questao: { idQuestao: 99, nomeMateria: 'Português' }, nomeAssuntoExibicao: 'Crase', comentario: { textoComentario: '<p>Texto</p>', nomeProfessor: 'P' } } };
  const filho = { $parent: { $parent: raiz } };
  const win = { angular: { element: () => ({ scope: () => filho }) } };
  const doc = { querySelector: () => ({}) };
  const r = Tela.lerAngular(win, doc);
  assert.equal(r.detectado, true);
  assert.equal(r.questao.idQuestao, 99);
  assert.equal(r.questao.assunto, 'Crase');
  assert.equal(r.questao.comentario, 'Texto');
  assert.deepEqual(Tela.lerAngular({}, doc), { detectado: false, questao: null });
});
