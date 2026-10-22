# 09: Ranking entre métricas, simulação de cenário e desempate

**What to build:** mais duas funções de evolução e a exibição do desempate.

- **`ranking_concursos_por_metrica`:** ordena os concursos por percentual bruto, corrigido e ponderado, e diz quantas posições cada um muda.
- **`simular_cenario`:** responde "se eu subir X p.p. na disciplina Y", convertendo round(X% × n) itens que não são acerto em acerto, na proporção atual de erros e brancos, e recalculando a nota e o gap.
  - A saída é rotulada como estimativa e nunca usa linguagem de previsão.
  - Não estima colocação.
- **Desempate:** os critérios de desempate aparecem na ordem do edital, sem cálculo.

Ver `docs/spec-fase3.md`, histórias 54–58.

**Blocked by:** 08 (Nota ponderada e gap para o corte)

**Status:** ready-for-agent

- [ ] Teste: o deslocamento do ranking entre as três métricas confere com um exemplo calculado à mão.
- [ ] Teste: a simulação muda a nota e o gap.
- [ ] Teste: a simulação é rotulada como estimativa e não contém "vou passar" nem "serei aprovado".
- [ ] Teste: o desempate sai na ordem do edital.
- [ ] `docs/modelo.md` documenta a fórmula da simulação.
- [ ] `uv run pytest` e `ruff` verdes.
