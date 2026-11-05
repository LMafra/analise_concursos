const test = require('node:test');
const assert = require('node:assert/strict');
const { criarColetor, nomeDoArquivo } = require('../core/coletor.js');

function memoria(inicial) {
  const dados = Object.assign({}, inicial);
  let gravacoes = 0;
  return {
    dados,
    get gravacoes() {
      return gravacoes;
    },
    ler: async (chave, padrao) => (chave in dados ? dados[chave] : padrao),
    gravar: async (chave, valor) => {
      gravacoes++;
      dados[chave] = valor;
    },
  };
}

function cenario(passos, inicial) {
  const armazenamento = memoria(Object.assign({ dev: 'dTESTE' }, inicial));
  const avisos = [];
  let i = 0;
  let agora = new Date(2026, 10, 2, 21, 0, 0).getTime();
  const coletor = criarColetor({
    armazenamento,
    ler: () => passos[i],
    avisar: (m) => avisos.push(m),
    relogio: () => new Date(agora),
  });
  return {
    armazenamento,
    avisos,
    coletor,
    async rodar() {
      for (i = 0; i < passos.length; i++) {
        await coletor.tick();
        agora += 1000;
      }
    },
  };
}

const Q = { id: 'q1', enun: 'Enunciado', marc: 'A', gab: 'B', mat: 'Português' };
const sem = { situacao: 'sem_resolver', questao: Q };
const errou = { situacao: 'errou', questao: Q };

test('erro em tempo real é guardado uma vez, com aviso e lembrete do comentário', async () => {
  const c = cenario([sem, sem, sem, errou, errou, errou]);
  await c.rodar();
  const erros = c.armazenamento.dados.erros;
  assert.equal(erros.q1.v, 1);
  assert.equal(erros.q1.origem, 'tempo_real');
  assert.equal(erros.q1.dev, 'dTESTE');
  assert.equal(c.avisos.length, 1);
  assert.match(c.avisos[0], /Erro guardado \(1 no total\).*Ver resolução/);
});

test('questão que já aparece errada entra como histórico, e o modo pode ser desligado', async () => {
  const c = cenario([errou, errou]);
  await c.rodar();
  assert.equal(c.armazenamento.dados.erros.q1.origem, 'historico');
  const desligado = cenario([errou], { modoHistorico: false });
  await desligado.rodar();
  assert.equal(desligado.armazenamento.dados.erros, undefined);
});

test('repetida avisa quantas vezes', async () => {
  const c = cenario([sem, sem, sem, errou], {
    erros: { q1: { id: 'q1', v: 1, ds: ['2026-10-01T10:00:00-03:00'], origem: 'tempo_real', d: '2026-10-01', t: 1 } },
  });
  await c.rodar();
  assert.equal(c.armazenamento.dados.erros.q1.v, 2);
  assert.match(c.avisos[0], /Errada 2 vezes/);
});

test('caderno não regrava sem mudança', async () => {
  const caderno = { id: 'c9', cad: 'Caderno', tot: 10, res: 2, ac: 1, er: 1 };
  const c = cenario([{ situacao: 'nenhuma', caderno }, { situacao: 'nenhuma', caderno }]);
  await c.rodar();
  assert.equal(c.armazenamento.dados.cads.c9.res, 2);
  assert.equal(c.armazenamento.gravacoes, 1);
});

test('exportação e nome do arquivo', async () => {
  const c = cenario([]);
  const arquivo = await c.coletor.exportacao();
  assert.equal(arquivo.app, 'tec-erros');
  assert.match(nomeDoArquivo(arquivo), /^tec-erros-dTESTE-2026-11-02\.json$/);
});
