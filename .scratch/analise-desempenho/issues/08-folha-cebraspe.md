# 08: Leitura da folha de resposta Cebraspe

**What to build:** um concurso Cebraspe com a folha de resposta em PDF ou imagem, em vez de `respostas.txt`, gera `respostas_extraidas.csv` com a alternativa (C/E), o estado (marcada, branco, múltipla), a confiança, a flag `revisar` (abaixo do limiar), o arquivo e a página. Também gera uma imagem de depuração com as bolhas detectadas sobrepostas. A grade é parametrizada por itens por coluna e total de itens, e é localizada pelos marcadores de canto e pelo agrupamento das bolhas. Assim, funciona nos layouts 7×15, 8×15, 9×20 e 10×20 e em posições variadas.

**Blocked by:** 01, 03

**Status:** ready-for-agent

- [ ] Testes com imagens sintéticas: bolha cheia, vazia, dupla e parcial, grade levemente rotacionada e dimensões de grade diferentes.
- [ ] A confiança é a margem entre a bolha mais preenchida e a segunda, e o limiar vem da configuração global.
- [ ] A calibração manual em `cd_25`, `telebras` e `infrasa` tem 100% das questões listadas. As questões com `revisar` são conferidas visualmente e o resultado fica registrado no ticket.
- [ ] Falha de leitura é rastreável até arquivo, página e questão.
