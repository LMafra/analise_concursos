const test = require('node:test');
const assert = require('node:assert/strict');
const T = require('../core/nucleo.js');

test('marc vazio ou null é branco', () => {
  assert.equal(T.resultadoQuestao('C', '', 'certo_errado'), 'branco');
  assert.equal(T.resultadoQuestao('A', null, 'multipla_escolha'), 'branco');
  assert.equal(T.resultadoQuestao('A', undefined, 'multipla_escolha'), 'branco');
});

test('certo_errado normaliza C/Certo e E/Errado', () => {
  assert.equal(T.resultadoQuestao('Certo', 'C', 'certo_errado'), 'acerto');
  assert.equal(T.resultadoQuestao('C', 'Certo', 'certo_errado'), 'acerto');
  assert.equal(T.resultadoQuestao('Errado', 'E', 'certo_errado'), 'acerto');
  assert.equal(T.resultadoQuestao('Certo', 'E', 'certo_errado'), 'erro');
  assert.equal(T.resultadoQuestao('Errado', 'Certo', 'certo_errado'), 'erro');
});

test('multipla_escolha compara letras maiúsculas', () => {
  assert.equal(T.resultadoQuestao('B', 'b', 'multipla_escolha'), 'acerto');
  assert.equal(T.resultadoQuestao('A', 'C', 'multipla_escolha'), 'erro');
});
