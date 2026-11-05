// Violentmonkey (Firefox Android e computador): o mesmo núcleo da extensão, com GM_* no lugar do
// chrome.storage e um botão flutuante no lugar do popup.
const T = escopo.TecErros;
const pagina = typeof unsafeWindow !== 'undefined' ? unsafeWindow : window;

const armazenamento = {
  ler: async (chave, padrao) => GM_getValue(chave, padrao),
  gravar: async (chave, valor) => GM_setValue(chave, valor),
};

function lerTela() {
  const url = location.href;
  const situacao = T.Tela.situacao(document);
  const angular = situacao === 'nenhuma' ? null : T.Tela.lerAngular(pagina, document);
  return {
    situacao: situacao,
    questao: situacao === 'nenhuma' ? null : T.Tela.lerQuestao(document, angular && angular.questao, url),
    caderno: T.Tela.lerCaderno(document, url, '', 0, ''),
  };
}

const coletor = T.Coletor.criarColetor({ armazenamento, ler: lerTela, avisar: T.Coletor.avisoNaTela(document) });

function baixar(nome, texto) {
  const url = URL.createObjectURL(new Blob([texto], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

function criarPainel() {
  const botao = document.createElement('button');
  botao.id = 'tec-erros-botao';
  botao.style.cssText =
    'position:fixed;left:10px;bottom:10px;z-index:2147483646;padding:6px 10px;border:0;border-radius:16px;' +
    'background:#b42318;color:#fff;font:13px system-ui,sans-serif;box-shadow:0 2px 6px #0005;opacity:.85';
  const painel = document.createElement('div');
  painel.style.cssText =
    'position:fixed;left:10px;bottom:48px;z-index:2147483646;width:280px;max-height:70vh;overflow:auto;display:none;' +
    'background:#fff;color:#1f2933;border:1px solid #c5ccd6;border-radius:8px;padding:10px;font:13px/1.4 system-ui,sans-serif;' +
    'box-shadow:0 2px 10px #0004';
  const acoes = [
    ['Baixar JSON', async () => {
      const arquivo = await coletor.exportacao();
      baixar(T.Coletor.nomeDoArquivo(arquivo), JSON.stringify(arquivo, null, 1));
      return 'Arquivo baixado.';
    }],
    ['Copiar JSON', async () => {
      GM_setClipboard(JSON.stringify(await coletor.exportacao()));
      return 'JSON copiado.';
    }],
    ['Diagnóstico', async () => {
      const relatorio = T.Tela.diagnostico(document, T.Tela.lerAngular(pagina, document), location.href, T.dataLocalIso(new Date()));
      const texto = JSON.stringify(relatorio, null, 1);
      GM_setClipboard(texto);
      pre.textContent = texto;
      pre.style.display = 'block';
      return 'Relatório copiado; cole na conversa para corrigir os seletores.';
    }],
    ['Modo histórico: ?', async () => {
      const ligado = (await armazenamento.ler('modoHistorico', true)) !== false;
      await armazenamento.gravar('modoHistorico', !ligado);
      return !ligado ? 'Questões que já aparecem erradas serão guardadas.' : 'Só erros feitos com o script rodando.';
    }],
    ['Limpar tudo', null],
    ['Fechar', async () => {
      painel.style.display = 'none';
      return '';
    }],
  ];
  const msg = document.createElement('p');
  const pre = document.createElement('pre');
  pre.style.cssText = 'display:none;white-space:pre-wrap;font-size:10px;background:#f7f8fa;padding:4px';
  const botoes = {};
  for (const [rotulo, acao] of acoes) {
    const b = document.createElement('button');
    b.textContent = rotulo;
    b.style.cssText = 'display:block;width:100%;margin:3px 0;padding:6px;border:1px solid #c5ccd6;border-radius:6px;background:#fff';
    b.addEventListener('click', async () => {
      if (acao) msg.textContent = await acao();
      await atualizar();
    });
    botoes[rotulo] = b;
    painel.appendChild(b);
  }
  let confirmando = null;
  botoes['Limpar tudo'].addEventListener('click', async () => {
    if (!confirmando) {
      botoes['Limpar tudo'].textContent = 'Toque de novo para apagar tudo';
      confirmando = setTimeout(() => {
        confirmando = null;
        botoes['Limpar tudo'].textContent = 'Limpar tudo';
      }, 4000);
      return;
    }
    clearTimeout(confirmando);
    confirmando = null;
    await coletor.limpar();
    botoes['Limpar tudo'].textContent = 'Limpar tudo';
    msg.textContent = 'Tudo apagado.';
    await atualizar();
  });
  painel.append(msg, pre);
  botao.addEventListener('click', () => (painel.style.display = painel.style.display === 'none' ? 'block' : 'none'));
  document.body.append(painel, botao);

  async function atualizar() {
    const erros = Object.values(await armazenamento.ler('erros', {}));
    const repetidas = erros.filter((e) => e.v >= 2).length;
    botao.textContent = '✗ ' + erros.length + (repetidas ? ' (' + repetidas + ' rep.)' : '');
    const ligado = (await armazenamento.ler('modoHistorico', true)) !== false;
    botoes['Modo histórico: ?'].textContent = 'Modo histórico: ' + (ligado ? 'ligado' : 'desligado');
  }
  return atualizar;
}

const atualizarPainel = criarPainel();
atualizarPainel();
setInterval(() => {
  coletor
    .tick()
    .then((acao) => acao && atualizarPainel())
    .catch((erro) => console.warn('tec-erros:', erro));
}, 1000);
