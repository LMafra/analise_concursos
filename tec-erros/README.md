# tec-erros

Guarda as questões que você erra no TEC Concursos, com gabarito e comentário do professor, e os totais de cada caderno. Funciona no Chrome do computador (extensão) e no Firefox do Android (userscript do Violentmonkey). O `caderno.html` mostra os erros, conta as repetidas e ajuda a revisar, offline. O `concurso-analise` importa o mesmo arquivo como prática.

Uso pessoal, com a sua conta. O script só lê o que já aparece na tela: não clica, não responde, não baixa questões em lote e não faz nenhum pedido de rede. Tudo fica no navegador até você exportar. Verifique os termos de uso do TEC antes de compartilhar com terceiros.

## Peças

| Pasta | O que é |
|---|---|
| `core/` | Núcleo em JavaScript puro: identidade, impressão digital, máquina de estados do erro, leitura do cabeçalho e dos totais, data local, mesclagem (`nucleo.js`); leitura da tela e do AngularJS (`tela.js`); o tick e o aviso (`coletor.js`). |
| `extensao-chrome/` | Manifest V3, `page.js` (mundo MAIN, só leitura do AngularJS), `content.js`, popup com contagem, exportação, limpeza em dois cliques e diagnóstico, e a ponte opcional `bridge.js`. |
| `userscript/` | O mesmo núcleo para o Violentmonkey, com `GM_getValue`/`GM_setValue` e um botão flutuante no lugar do popup. |
| `caderno/caderno.html` | Caderno de erros: importar ou colar JSON de vários aparelhos, removidos, filtros, destaque para repetidas, matérias por palavra-chave, assunto → tópico do edital e registro da diferença dos cadernos. |
| `scripts/build.mjs` | Monta tudo em `dist/`, sem dependências. |

## Começar

```bash
node --test                  # testes do núcleo
node scripts/build.mjs       # dist/extensao-chrome, dist/tec-erros-extensao-<versão>.zip, dist/tec-erros.user.js, dist/caderno.html
node scripts/build.mjs --ponte   # inclui a ponte para o caderno.html aberto do disco
```

- Chrome: [docs/instalar-chrome.md](docs/instalar-chrome.md).
- Tablet Android: [docs/instalar-android.md](docs/instalar-android.md).
- Formato do arquivo exportado: [docs/contrato.md](docs/contrato.md).
- O que foi conferido e o que ainda é hipótese (seletores do TEC): [docs/pesquisa.md](docs/pesquisa.md).

## Como um erro é contado

A questão precisa aparecer sem resolver por 2 segundos seguidos e depois ficar errada. Reabrir uma questão que você já errou não conta de novo. Uma questão que já aparece errada (resolvida no app) entra pelo modo histórico, sem data e sem aumentar a contagem de uma questão conhecida. Cada erro guarda a data e a hora locais, com o fuso, e o aparelho; arquivos de aparelhos diferentes se mesclam sem perder nem duplicar eventos.

## Quando o TEC mudar a página

Use o diagnóstico (popup da extensão ou botão "✗" do userscript) numa questão errada, com o comentário aberto, e cole o relatório na conversa. Os seletores ficam todos em `core/tela.js` (`SELETORES`).
