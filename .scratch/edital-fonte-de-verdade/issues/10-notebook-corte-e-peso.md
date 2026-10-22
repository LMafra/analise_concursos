# 10: Notebook de corte e peso, com o painel de peculiaridades

**What to build:** um notebook novo, no formato jupytext percent, com:

- a tabela de quanto melhorar por disciplina para atingir o corte do concurso-alvo (ou de todos);
- barras horizontais de gap percentual por disciplina, coloridas por atingido;
- a comparação lado a lado de percentual bruto, percentual ponderado e gap por concurso;
- um destaque em markdown quando o ranking muda entre as métricas;
- o painel de peculiaridades do edital, com as descobertas de alto impacto:
  - anuladas fora do mérito;
  - corte em acertos;
  - teto de classificados;
  - corte da discursiva.

As células só chamam funções do pacote, e as tabelas longas passam por `resumir`.

Ver `docs/spec-fase3.md`, histórias 60–64 e 66.

**Blocked by:** 07 (Descoberta dirigida e catálogo), 09 (Ranking entre métricas, simulação e desempate)

**Status:** ready-for-agent

- [ ] Os gráficos e o painel vêm de funções testadas do pacote.
- [ ] As células não têm regra de negócio.
- [ ] O notebook novo e os existentes executam do zero pelo script.
- [ ] A conclusão em prosa cita os números que as células imprimem.
- [ ] `uv run pytest` e `ruff` verdes.
