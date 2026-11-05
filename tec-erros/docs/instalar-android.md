# Usar no tablet Android

O app do TEC não roda scripts. A captura no tablet é pelo site do TEC aberto no **Firefox**, com o **Violentmonkey**. Do app, você aproveita o progresso: ele fica na sua conta, e o modo histórico guarda os erros quando você abre o caderno no navegador.

## Instalar

1. Instale o **Firefox** pela Play Store.
2. No Firefox, abra o menu (⋮), **Extensões**, procure **Violentmonkey** e toque em **Adicionar**.
3. Copie o arquivo `dist/tec-erros.user.js` para o tablet (pela pasta sincronizada, por exemplo) e abra-o no Firefox. O Violentmonkey mostra a tela de instalação; toque em **Confirmar instalação**. Se o Firefox só mostrar o texto, abra o Violentmonkey (menu ⋮, Extensões, Violentmonkey), toque em **+** e cole o conteúdo do arquivo.
4. Abra o tecconcursos.com.br no Firefox e faça login. Um botão vermelho "✗ 0" aparece no canto inferior esquerdo.

## Usar em tempo real

Resolva o caderno pelo site, no Firefox. Errou, aparece "✗ Erro guardado". Toque em "Ver resolução" para o comentário ir junto. É a única forma em que a contagem de vezes que você errou (`v`) é confiável.

## Usar depois do app (modo histórico)

1. Resolva no app do TEC normalmente.
2. Depois, abra o mesmo caderno no Firefox e passe pelas questões. As que já aparecem erradas são guardadas com `origem: historico` e sem data; questões já conhecidas não têm a contagem aumentada.
3. Os totais do caderno (resolvidas, acertos, erros) são atualizados ao abrir o caderno.

O modo histórico vem ligado; desligue no botão "✗" > **Modo histórico** se quiser guardar só os erros feitos com o script rodando.

## Exportar

No botão "✗": **Baixar JSON** salva `tec-erros-<aparelho>-<data>.json` na pasta Downloads; **Copiar JSON** copia o texto. Leve o arquivo para a pasta de entrada do concurso-analise (`[pratica] entrada_tec`) ou importe no `caderno.html`. Arquivos do computador e do tablet podem ser importados juntos: a mesclagem soma os erros do mesmo dia em aparelhos diferentes sem contar duas vezes o mesmo evento.

## Caderno de erros no tablet

Copie `dist/caderno.html` para o tablet e abra no Firefox (ou no Chrome). Ele funciona sem internet e guarda o estado no próprio navegador. Use **Importar arquivos** para escolher os JSON baixados.

## Se algo parar de funcionar

Abra uma questão errada, toque em "✗" > **Diagnóstico**. O relatório é copiado; cole na conversa para corrigir os seletores. O Firefox pode suspender a aba em segundo plano; ao voltar, a contagem retoma, e a regra dos 2 segundos evita contar errado.
