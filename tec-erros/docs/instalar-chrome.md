# Instalar a extensão no Chrome (computador)

1. Gere os pacotes: `node scripts/build.mjs` na pasta do projeto. Eles saem em `dist/`.
2. No Chrome, abra `chrome://extensions`.
3. Ligue o **Modo do desenvolvedor**, no canto superior direito.
4. Clique em **Carregar sem compactação** e escolha a pasta `dist/extensao-chrome`. (Se recebeu o `.zip`, descompacte antes e escolha a pasta.)
5. Fixe a extensão na barra: clique no ícone de quebra-cabeça e no alfinete ao lado de **tec-erros**.

## Testar

1. Abra um caderno no tecconcursos.com.br e espere uma questão sem resolver aparecer por uns 2 segundos.
2. Erre de propósito. No canto inferior direito aparece "✗ Erro guardado (1 no total)" por 5 segundos.
3. Clique em "Ver resolução": o comentário é guardado junto, sem perder o resto.
4. Clique no ícone da extensão: a contagem mostra 1 erro. Use **Diagnóstico desta aba** numa questão errada; o relatório é copiado para você colar na conversa se algo não foi lido.
5. **Baixar JSON** e importe o arquivo no `caderno.html`.

## Ponte opcional para o caderno.html

Com `node scripts/build.mjs --ponte`, a extensão também roda no `caderno.html` aberto do disco e entrega os dados sozinha, sem baixar arquivo. Para isso, em `chrome://extensions`, nos **Detalhes** da tec-erros, ligue **Permitir acesso a URLs de arquivo**. O nome do arquivo precisa conter `caderno` e terminar em `.html`.

## Atualizar

Gere de novo (`node scripts/build.mjs`) e clique no ícone de recarregar da tec-erros em `chrome://extensions`. Os erros guardados continuam lá.
