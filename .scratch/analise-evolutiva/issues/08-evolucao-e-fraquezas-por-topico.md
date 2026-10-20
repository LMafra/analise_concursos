# 08: Evolução e fraquezas por tópico (notebook 03)

**What to build:** um notebook que mostra quais tópicos do edital foram cobrados e quais continuam fracos. Com a amostra pequena por prova (mediana de 2 questões por tópico), a análise principal usa contagens somadas entre concursos.

- **`cobertura_edital`:** por concurso, quantos tópicos do edital estruturado foram efetivamente cobrados na prova. Tópicos nunca cobrados ficam fora da análise de evolução.
- **`evolucao_por_topico`:**
  - slope sobre o percentual ajustado, via `scipy.stats.linregress`, com p-value e n;
  - só para tópicos com 3 pontos ou mais e n ≥ 5 (o mínimo é configurável);
  - nos outros, devolve "amostra insuficiente" em vez de um slope.
- **`topicos_fracos_persistentes`:**
  - limiar padrão de 0,6 sobre o percentual ajustado, em pelo menos 2 concursos;
  - acertos e erros somados entre concursos, com n agregado ≥ 5;
  - devolve a lista dos concursos abaixo do limiar.
- **Gráficos:**
  - heatmap de tópicos (linhas) por concursos (colunas), com o percentual anotado só onde n ≥ 5 e o resto em cinza com o rótulo "n<5";
  - barras empilhadas de acertos e erros dos tópicos fracos persistentes, com n anotado.
- O notebook abre com a pergunta e fecha com uma conclusão em prosa, e não contém lógica de negócio.

Ver `docs/spec-fase2.md` (histórias 37, 43, 44, 54 e 56).

**Blocked by:** 05 (Taxonomia de disciplinas e bloco geral/específico)

**Status:** ready-for-agent

- [ ] Testes:
  - cobertura com tópico nunca cobrado;
  - evolução com n < 5, um concurso só e menos de 3 pontos (sem slope);
  - fracos persistentes com soma entre concursos e a regra de 2 concursos;
  - correção líquida comparada à bruta;
  - tópico sem gabarito.
- [ ] Testes de que o heatmap anota só as células com n ≥ 5 e que as barras trazem n.
- [ ] Com dados reais, a lista de fracos persistentes é coerente com o comparativo da fase 1, e as diferenças são explicadas na conclusão do notebook.
- [ ] O notebook 03 executa do zero pelo script.
- [ ] `uv run pytest` e `ruff` verdes.
