# 01: Correção do edital ponta a ponta (Cebraspe e FGV bruta)

**What to build:** ao rodar `concursos analisar`, cada concurso analisado ganha um arquivo de correção na sua pasta de análise. O arquivo diz qual é o modelo de correção do edital (bruta, líquida ou ponderada), o fator de penalidade, a nota máxima, a nota de corte, a fonte da regra (edital, configuração ou default), a confiança da extração e o trecho citado com o documento e a página.

- A regra é extraída por regex do texto do edital e dos anexos, sem OCR, procurando nas seções de critérios de avaliação, prova objetiva, pontuação e correção. Neste ticket entram dois padrões:
  - penalidade explícita Cebraspe ("1,00 ponto negativo … discordância", fator 1,0);
  - FGV sem desconto ("igual ao total de acertos" ou "valendo 1 ponto cada questão"), modelo bruta.
- O `concurso.yaml` aceita um bloco opcional de correção (modelo, fator, nota máxima, nota de corte). A precedência é edital, depois configuração, depois default (`bruta`, fator 0).
- O pipeline emite aviso visível em dois casos: quando a regra cai no default e o texto do edital menciona penalidade, e quando a `pontuacao` declarada contradiz o edital.
  - A menção a penalidade usa só expressões específicas: "ponto negativo", "desconto de", "descontado" e "anula um acerto". "Anulação", "anulada" e "descontos" soltos não contam: aparecem em todos os editais e, no TCU, como "descontos legais" do salário.
- Sem nota máxima no edital nem na configuração, ela é a soma dos pesos dos itens (o número de itens, quando não há pesos).
- O texto de cada documento do edital (anexos primeiro, depois o principal) é lido uma única vez, sem OCR, e serve tanto para o conteúdo programático quanto para a correção. Com edital manual, a correção ainda sai dos PDFs declarados; sem nenhum PDF, vem da configuração ou do default.
- A aplicação da correção calcula a pontuação de cada item em três versões:
  - bruta: acerto vale 1;
  - corrigida pela regra do edital;
  - ajustada ao acaso: erro vale \(-1/(k-1)\), com k = 2 em Certo/Errado e k = 5 em A–E.
- As anuladas ficam fora das métricas de desempenho. A nota normalizada (0–100, truncada em 0) segue o edital e conta anulada como ponto.
- A versão da análise no manifesto sobe, para que todos os concursos já analisados gerem o arquivo de correção na próxima execução.
- Os CSVs existentes não mudam.
- O modelo de domínio documenta o bloco de correção do `concurso.yaml`, o contrato do arquivo de correção e as fórmulas das três versões.

Ver `docs/spec-fase2.md` (histórias 1–2, 5–12, 15–18 e 32–35).

**Blocked by:** None (can start immediately)

**Status:** done

- [x] TDD do módulo de correção da camada de análise. A extração a partir de texto é a seam pura, testada com trechos reais curtos (Cebraspe, FGV agsus e cprm) e textos sintéticos.
- [x] Casos de borda testados:
  - edital sem menção, que dá default com aviso;
  - default com o texto mencionando penalidade, que dá aviso;
  - fator 1,0;
  - precedência edital, configuração, default;
  - contradição com a `pontuacao` declarada;
  - nota negativa truncada em 0 só na nota normalizada;
  - tópico sem gabarito.
- [x] Teste paramétrico: com penalidade, a versão corrigida difere da bruta em pelo menos uma questão com erro; sem penalidade, as duas coincidem.
- [x] Na Cebraspe, a nota corrigida do concurso é igual à soma da `nota_liquida` legada.
- [x] Sempre que a fonte for o edital, o trecho, o documento e a página de origem vêm preenchidos.
- [x] Teste com trechos reais: "anulação de questão" e "descontos legais" não disparam o aviso de penalidade.
- [x] Teste: sem nota máxima no edital nem na configuração, ela é igual ao número de itens.
- [x] O PDF de cada documento do edital é lido uma vez por análise. Teste de CLI: com edital manual e PDF declarado, a correção tem fonte `edital`.
- [x] Teste de CLI ponta a ponta (prior art: os testes `test_cli_*` da fase 1): o arquivo de correção é gravado com a fonte certa, os CSVs mantêm exatamente as mesmas colunas e a mudança de versão do manifesto provoca a regeneração.
- [x] Com dados reais, os 6 concursos Cebraspe resolvem como `liquida`, fator 1,0 e fonte `edital`, e agsus e cprm como `bruta` e fonte `edital`.
- [x] `docs/modelo.md` atualizado com o bloco de correção, o arquivo de correção e as fórmulas.
- [x] `uv run pytest` e `ruff` verdes.
