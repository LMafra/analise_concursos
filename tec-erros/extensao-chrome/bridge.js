// Ponte opcional: entrega os dados ao caderno.html aberto no navegador. Só age depois do pong.
const T = escopo.TecErros;
let sid = null;
let ativo = false;

function enviar() {
  chrome.storage.local.get({ erros: {}, cads: {}, dev: '?' }, (d) => {
    window.postMessage({ src: 'tec-bridge', t: 'data', json: T.exportar(d.erros, d.cads, d.dev, new Date()) }, '*');
  });
}

window.addEventListener('message', (ev) => {
  const d = ev.data;
  if (ev.source !== window || !d || d.src !== 'tec-panel' || d.t !== 'pong') return;
  ativo = true;
  if (d.sid !== sid) {
    sid = d.sid;
    enviar();
  }
});

chrome.storage.onChanged.addListener((mudancas, area) => {
  if (ativo && area === 'local' && (mudancas.erros || mudancas.cads)) enviar();
});

setInterval(() => window.postMessage({ src: 'tec-bridge', t: 'ping' }, '*'), 3000);
