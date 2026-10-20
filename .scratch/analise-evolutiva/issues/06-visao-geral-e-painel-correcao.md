# 06: Visão geral e painel de correção (notebook 01)

**What to build:** um notebook de visão geral que mostra o perfil da base e o efeito de cada regra de correção. É o painel que justifica todas as análises seguintes.

- **Perfil de n** por concurso, prova e tópico, incluindo quantas combinações de tópico têm n ≥ 5.
- **`comparar_bruto_vs_corrigido`:**
  - Ranqueia os concursos pelas três versões (bruta, corrigida pelo edital e ajustada ao acaso), lado a lado.
  - Mostra o percentual de cada versão, a posição em cada ranking e o deslocamento de posições.
  - Anota o modelo de correção e o fator.
  - O CPNU aparece como 3 linhas, uma por variante.
- **Painel de correção:** tabela mais barras agrupadas (bruto, corrigido e ajustado) por concurso, com modelo e fator no hover (plotly).
- **Célula obrigatória** com a tabela de `comparar_bruto_vs_corrigido`.
- O notebook abre com a pergunta que responde e fecha com uma conclusão em prosa. Não contém lógica de negócio, e tabelas longas passam pelo helper de resumo.

Ver `docs/spec-fase2.md` (histórias 47, 50 e 51) e a tabela de percentuais aproximados.

**Blocked by:** 02 (Pesos por faixa de itens e variantes), 04 (Consolidado em parquet e notebook de carregamento)

**Status:** ready-for-agent

- [ ] Testes de `comparar_bruto_vs_corrigido`:
  - um concurso só;
  - correção líquida comparada à bruta, com mudança de posição detectada;
  - variantes viram linhas;
  - anuladas fora;
  - empates.
- [ ] Teste de que a função do painel recebe o DataFrame pronto e devolve uma figura com as três séries e o hover com modelo e fator.
- [ ] Com dados reais, os percentuais por concurso reproduzem a tabela da spec dentro do arredondamento, descontado o efeito de tirar as anuladas.
- [ ] O notebook 01 executa do zero pelo script.
- [ ] `uv run pytest` e `ruff` verdes.
