# 08: Leitura da folha de resposta Cebraspe

**What to build:** um concurso Cebraspe com a folha de resposta em PDF ou imagem, em vez de `respostas.txt`, gera `respostas_extraidas.csv` com a alternativa (C/E), o estado (marcada, branco, múltipla), a confiança, a flag `revisar` (abaixo do limiar), o arquivo e a página. Também gera uma imagem de depuração com as bolhas detectadas sobrepostas. A grade é parametrizada por itens por coluna e total de itens, e é localizada pelos marcadores de canto e pelo agrupamento das bolhas. Assim, funciona nos layouts 7×15, 8×15, 9×20 e 10×20 e em posições variadas.

**Blocked by:** 01, 03

**Status:** done

- [x] Testes com imagens sintéticas: bolha cheia, vazia, dupla e parcial, grade levemente rotacionada e dimensões de grade diferentes.
- [x] A confiança é a margem entre a bolha mais preenchida e a segunda, e o limiar vem da configuração global.
- [x] A calibração manual em `cd_25`, `telebras` e `infrasa` tem 100% das questões listadas. As questões com `revisar` são conferidas visualmente e o resultado fica registrado no ticket.
- [x] Falha de leitura é rastreável até arquivo, página e questão.

## Calibração manual (folhas reais, limiar 0,75)

Preenchimento medido no centro das bolhas: vazias entre 0,0 e 0,2; marcadas acima de 0,9. Normalização: `VAZIO = 0,2`, `CHEIO = 0,9`.

| Concurso | Grade | Questões listadas | `revisar` | Conferência visual |
|---|---|---|---|---|
| cd_25 | 9×20 | 180/180 | 0 | itens 1–20 conferidos um a um; sobreposição alinhada em toda a grade |
| telebras | 8×15 | 120/120 | 0 | sobreposição alinhada em toda a grade |
| infrasa | 7×15 (última coluna 91–100) | 100/100 | 0 | sobreposição alinhada, coluna parcial lida |
| tcu_25, funpresp_jud, pf_perito | 10×20, 8×15, 8×15 | 200, 120, 120 | 0 | confiança mínima 1,0 |
