const test = require('node:test');
const assert = require('node:assert/strict');
const T = require('../core/nucleo.js');
const fs = require('node:fs');
const path = require('node:path');

const FIXTURE = path.join(__dirname, 'fixtures', 'exportacao-cinco.json');

test('modo todas mantém 5 itens; só erros mantém 2', () => {
  const dados = JSON.parse(fs.readFileSync(FIXTURE, 'utf8'));
  assert.equal(T.filtrarItens(dados.erros, 'todas').length, 5);
  assert.equal(T.filtrarItens(dados.erros, 'so_erros').length, 2);
  assert.deepEqual(
    T.filtrarItens(dados.erros, 'so_erros').map((i) => i.id).sort(),
    ['q-ce-erro', 'q-me-erro']
  );
});

test('exportar aplica tipo, resultado, filtro e avisos_extensao', () => {
  const dados = JSON.parse(fs.readFileSync(FIXTURE, 'utf8'));
  const porId = Object.fromEntries(dados.erros.map((e) => [e.id, e]));
  const todas = T.exportar(porId, { c1: dados.cads[0] }, 'dFIX', new Date('2026-11-02T12:00:00-03:00'), {
    modoExportacao: 'todas',
  });
  assert.equal(todas.erros.length, 5);
  assert.equal(todas.cads[0].ac, 2);
  assert.equal(todas.cads[0].er, 2);
  assert.equal(todas.cads[0].res, 4);
  assert.equal(todas.cads[0].tot, 5);
  assert.ok(todas.erros.every((e) => e.tipo && e.resultado));
  assert.ok(todas.avisos_extensao.some((a) => /marc ausente em 1/.test(a)));

  const so = T.exportar(porId, { c1: dados.cads[0] }, 'dFIX', new Date('2026-11-02T12:00:00-03:00'), {
    modoExportacao: 'so_erros',
  });
  assert.equal(so.erros.length, 2);
  assert.ok(so.avisos_extensao.includes('exportação só de erros (modo antigo)'));
});

test('marc ausente gera aviso e marc null no item', () => {
  const item = {
    id: 'qX',
    enun: 'x',
    gab: 'A',
    alts: [{ l: 'A', t: 'a' }, { l: 'B', t: 'b' }],
  };
  const out = T.exportar({ qX: item }, {}, 'd', new Date(), { modoExportacao: 'todas' });
  assert.equal(out.erros[0].marc, null);
  assert.equal(out.erros[0].resultado, 'branco');
  assert.ok(out.avisos_extensao.some((a) => /marc ausente/.test(a)));
});
