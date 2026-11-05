// Mundo MAIN: lê o scope do AngularJS (sem alterar nada) e entrega ao content.js.
const T = escopo.TecErros;
setInterval(() => {
  const angular = T.Tela.lerAngular(window, document);
  window.postMessage({ src: 'tec-erros-page', angular: angular }, location.origin);
}, 1000);
