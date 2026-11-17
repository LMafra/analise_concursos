const test = require('node:test');
const assert = require('node:assert/strict');
const T = require('../core/nucleo.js');

test('dois alts Certo/Errado viram certo_errado', () => {
  assert.equal(T.tipoQuestao([{ l: 'C', t: 'Certo' }, { l: 'E', t: 'Errado' }]), 'certo_errado');
  assert.equal(T.tipoQuestao([{ l: 'C', t: 'CERTO' }, { l: 'E', t: 'errado' }]), 'certo_errado');
});

test('mais de dois alts ou textos outros viram multipla_escolha', () => {
  assert.equal(
    T.tipoQuestao([
      { l: 'A', t: 'um' },
      { l: 'B', t: 'dois' },
      { l: 'C', t: 'três' },
    ]),
    'multipla_escolha'
  );
  assert.equal(T.tipoQuestao([{ l: 'A', t: 'sim' }, { l: 'B', t: 'não' }]), 'multipla_escolha');
  assert.equal(T.tipoQuestao([]), 'multipla_escolha');
  assert.equal(T.tipoQuestao(null), 'multipla_escolha');
});
