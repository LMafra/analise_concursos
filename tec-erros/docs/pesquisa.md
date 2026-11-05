# Pesquisa: o que o tec-erros assume e o que falta confirmar

Conferido em nov/2026. O que não pôde ser conferido sem a sua conta no TEC está marcado como **hipótese**; o diagnóstico (popup da extensão ou botão do userscript) gera o relatório para confirmar ou corrigir.

## Violentmonkey (Firefox Android e computador)

Fonte: [Violentmonkey, Privileged APIs](https://violentmonkey.github.io/api/gm/).

- O Firefox para Android instala extensões do addons.mozilla.org, e o Violentmonkey é uma delas. O app do TEC não roda scripts; por isso, no tablet, a captura é pelo site do TEC aberto no Firefox.
- `@grant` diferente de `none` liga o sandbox: o `window` do script é um invólucro, e o `window` da página (onde está o `angular`) só é alcançado por `unsafeWindow`.
- `GM_getValue(nome, padrao)` e `GM_setValue(nome, valor)` guardam valores estruturados (objetos e listas) no armazenamento do Violentmonkey, por script. Ficam só no aparelho.
- `GM_setClipboard(texto)` copia para a área de transferência sem pedir permissão da página.
- `GM_download` baixa uma URL, mas passa pelo `GM_xmlhttpRequest`. O userscript não usa: o download é o clássico `<a download href="blob:...">`, que funciona no Firefox Android e não faz pedido de rede.
- Sem `@connect` e sem `GM_xmlhttpRequest`, o script não tem como falar com nenhum servidor.

## Chrome (Manifest V3)

- `content_scripts` com `"world": "MAIN"` roda no contexto da página (lê o `angular`); o script isolado não lê variáveis da página e conversa com o MAIN por `window.postMessage`.
- `chrome.storage.local` guarda até 10 MB sem a permissão `unlimitedStorage`; um erro com comentário tem poucos KB, então cabem milhares.
- O popup fala com a aba atual por `chrome.tabs.sendMessage`, o que não exige a permissão `tabs` quando a extensão já tem acesso ao site.

## TEC Concursos (hipóteses, do seu prompt)

- Aplicação de página única com AngularJS: a questão muda sem recarregar, por isso o `tick` a cada 1 s. `angular.element(el).scope()` só funciona com o debug info ligado; se o diagnóstico mostrar "AngularJS: não", a leitura segue só pelo texto da tela.
- Seletores: `.questao-enunciado-resolucao-errou`, `.questao-enunciado-resolucao-acertou`, `[tec-formatar-html="vm.questao.enunciado"]`/`.questao-enunciado-texto`, `.questao-enunciado-alternativas > li` (com `.questao-enunciado-alternativa-opcao` e `.questao-enunciado-alternativa-texto`), `.questao-alternativa-selecionada`, `[tec-formatar-html="vm.comentario.textoComentario"]` e `[ng-bind="vm.comentario.nomeProfessor"]`.
- Cabeçalho em texto: `Matéria: …`, `Assunto: …`, `#12345678 BANCA - ANO - ÓRGÃO`.
- Totais do caderno: `Questão 2 de 484 (2 Resolvidas, 0 Acertos e 2 Erros)`.
- Id do caderno: o número depois de `/cadernos/` na URL (**hipótese**; o diagnóstico mostra o que foi lido).
- Filtro "questões que errei" no TEC: **não confirmado**. Sem ele, o modo histórico exige percorrer o caderno no navegador depois de resolver no app.

## O que eu preciso de você

O HTML de uma questão errada aberta no TEC (botão direito, "Inspecionar", copiar o elemento da questão) ou o relatório do diagnóstico numa questão errada, com o comentário aberto. Com isso eu confirmo ou corrijo os seletores em `core/tela.js`.
