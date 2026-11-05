// As mesmas fixtures são lidas por tests/test_contrato_tec.py: a mesclagem tem de dar o mesmo resultado nos dois lados.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const T = require('../core/nucleo.js');

const PASTA = path.join(__dirname, '..', '..', 'tests', 'contrato_tec');
const ENTRADA = path.join(PASTA, 'entrada');

function exportacoes() {
  return fs
    .readdirSync(ENTRADA)
    .filter((nome) => nome.startsWith('tec-erros-') && nome.endsWith('.json'))
    .sort()
    .map((nome) => T.lerExportacao(fs.readFileSync(path.join(ENTRADA, nome), 'utf8')));
}

test('a mesclagem das exportações do contrato dá o resultado esperado', () => {
  let erros = [];
  let cads = [];
  for (const { dados } of exportacoes()) {
    erros = T.mesclarErros(erros, dados.erros).erros;
    cads = T.mesclarCadernos(cads, dados.cads).cads;
  }
  const esperada = JSON.parse(fs.readFileSync(path.join(PASTA, 'mesclagem_esperada.json'), 'utf8'));
  assert.deepStrictEqual(erros, esperada.erros);
  assert.deepStrictEqual(cads, esperada.cads);
});

test('campo desconhecido na exportação vira aviso, não erro', () => {
  const avisos = exportacoes().flatMap((e) => e.avisos);
  assert.deepStrictEqual(avisos, ['campo desconhecido ignorado: extra']);
});

test('o caderno-estado.json do contrato tem app, versão e as chaves conhecidas', () => {
  const estado = JSON.parse(fs.readFileSync(path.join(ENTRADA, 'caderno-estado.json'), 'utf8'));
  assert.equal(estado.app, 'tec-erros-caderno');
  assert.equal(estado.v, 1);
  for (const chave of ['status', 'removidos', 'aliases', 'materias', 'cadernos']) assert.ok(chave in estado, chave);
});
