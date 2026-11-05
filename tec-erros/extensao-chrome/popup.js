// Popup: contagem, exportação, limpeza em dois cliques e diagnóstico da aba atual.
const T = escopo.TecErros;
const $ = (id) => document.getElementById(id);

function ler() {
  return new Promise((ok) => chrome.storage.local.get({ erros: {}, cads: {}, dev: '?', modoHistorico: true }, ok));
}

function mensagem(texto) {
  $('mensagem').textContent = texto;
}

async function atualizar() {
  const d = await ler();
  const erros = Object.values(d.erros);
  $('erros').textContent = erros.length;
  $('repetidas').textContent = erros.filter((e) => e.v >= 2).length;
  $('cadernos').textContent = Object.keys(d.cads).length;
  $('dev').textContent = d.dev;
  $('historico').checked = d.modoHistorico !== false;
}

async function exportacao() {
  const d = await ler();
  return T.exportar(d.erros, d.cads, d.dev, new Date());
}

$('baixar').addEventListener('click', async () => {
  const arquivo = await exportacao();
  const url = URL.createObjectURL(new Blob([JSON.stringify(arquivo, null, 1)], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = T.Coletor.nomeDoArquivo(arquivo);
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  mensagem('Arquivo baixado: ' + a.download);
});

$('copiar').addEventListener('click', async () => {
  await navigator.clipboard.writeText(JSON.stringify(await exportacao()));
  mensagem('JSON copiado.');
});

$('historico').addEventListener('change', (ev) => chrome.storage.local.set({ modoHistorico: ev.target.checked }));

let confirmando = null;
$('limpar').addEventListener('click', () => {
  if (!confirmando) {
    $('limpar').textContent = 'Clique de novo para apagar tudo';
    confirmando = setTimeout(() => {
      confirmando = null;
      $('limpar').textContent = 'Limpar tudo';
    }, 4000);
    return;
  }
  clearTimeout(confirmando);
  confirmando = null;
  chrome.storage.local.set({ erros: {}, cads: {} }, () => {
    $('limpar').textContent = 'Limpar tudo';
    mensagem('Tudo apagado.');
    atualizar();
  });
});

$('diagnostico').addEventListener('click', () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (abas) => {
    const aba = abas[0];
    if (!aba) return mensagem('Nenhuma aba ativa.');
    chrome.tabs.sendMessage(aba.id, { tipo: 'diagnostico' }, (relatorio) => {
      const pre = $('relatorio');
      pre.hidden = false;
      if (chrome.runtime.lastError || !relatorio) {
        pre.textContent = 'Sem resposta: abra uma questão no tecconcursos.com.br e recarregue a página.';
        return;
      }
      pre.textContent = JSON.stringify(relatorio, null, 1);
      navigator.clipboard.writeText(pre.textContent).then(() => mensagem('Relatório copiado; cole na conversa para corrigir os seletores.'));
    });
  });
});

atualizar();
