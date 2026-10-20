# 09: Insights e relatório de evolução (notebook 04)

**What to build:** um notebook de insights que transforma as análises anteriores em conclusões acionáveis, escritas em markdown, e um relatório de evolução com imagens estáticas para ler fora do Jupyter.

- **`comparar_com_meta`:** distância entre a nota normalizada e uma meta configurável (padrão 0,7), por concurso e variante. O CPNU aparece com as 3 variantes.
- **O notebook responde em markdown:**
  1. Em quais disciplinas meu desempenho melhorou de forma estatisticamente significativa (p < 0,05)?
  2. Quais tópicos continuam fracos apesar do volume de estudo?
  3. Qual a correlação entre a ordem e o z-score médio?
  4. O ranking de concursos muda entre bruta, corrigida e ajustada? Em quantas posições? Se mudar, isso entra como achado.
- **Sensibilidade:** os achados principais são recalculados sem o `cd_25` (nível médio), e as diferenças são declaradas.
- **Exportação:** a linha de evolução, o heatmap e o painel de correção são exportados como PNG estático (matplotlib) para a pasta do consolidado. Um relatório de evolução em markdown os referencia e traz as 4 respostas.
- O radar opcional fica fora (corte de escopo).
- O notebook abre com a pergunta e fecha com uma conclusão em prosa, e não contém lógica de negócio.

Ver `docs/spec-fase2.md` (histórias 24, 45, 58 e 59).

**Blocked by:** 06 (Visão geral e painel de correção), 07 (Evolução por disciplina), 08 (Evolução e fraquezas por tópico)

**Status:** ready-for-agent

- [ ] Testes de `comparar_com_meta`: variantes, nota truncada em 0 e um concurso só.
- [ ] Teste das funções de exportação: cada uma grava o PNG esperado a partir de um DataFrame pronto.
- [ ] O relatório de evolução é gerado com as 3 imagens e as 4 respostas.
- [ ] As 4 perguntas são respondidas em markdown com números (slope, p, n e posições) e a sensibilidade sem o `cd_25`.
- [ ] O notebook 04 executa do zero pelo script.
- [ ] `uv run pytest` e `ruff` verdes.
