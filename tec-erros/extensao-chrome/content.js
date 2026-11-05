// Mundo isolado: lê a tela, decide quando houve erro e guarda no chrome.storage.local.
const T = escopo.TecErros;
let angular = null;

window.addEventListener('message', (ev) => {
  if (ev.source !== window || !ev.data || ev.data.src !== 'tec-erros-page') return;
  angular = ev.data.angular;
});

const armazenamento = {
  ler: (chave, padrao) => new Promise((ok) => chrome.storage.local.get({ [chave]: padrao }, (r) => ok(r[chave]))),
  gravar: (chave, valor) => new Promise((ok) => chrome.storage.local.set({ [chave]: valor }, ok)),
};

function lerTela() {
  const url = location.href;
  const situacao = T.Tela.situacao(document);
  return {
    situacao: situacao,
    questao: situacao === 'nenhuma' ? null : T.Tela.lerQuestao(document, angular && angular.questao, url),
    caderno: T.Tela.lerCaderno(document, url, '', 0, ''),
  };
}

const coletor = T.Coletor.criarColetor({ armazenamento, ler: lerTela, avisar: T.Coletor.avisoNaTela(document) });
setInterval(() => coletor.tick().catch((erro) => console.warn('tec-erros:', erro)), 1000);

chrome.runtime.onMessage.addListener((mensagem, _remetente, responder) => {
  if (mensagem && mensagem.tipo === 'diagnostico') {
    responder(T.Tela.diagnostico(document, angular, location.href, T.dataLocalIso(new Date())));
  }
});
