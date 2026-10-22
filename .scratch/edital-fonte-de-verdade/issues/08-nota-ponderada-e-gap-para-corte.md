# 08: Nota ponderada e gap para o corte

**What to build:** duas funções novas de evolução, sobre o consolidado e os cortes do edital estruturado.

- **`nota_ponderada_por_disciplina`:** o acerto vale o peso do item, sem desconto por erro.
- **`gap_para_corte`:** uma linha por corte aplicável, com a nota atual, o corte, o gap absoluto na unidade do corte, o gap percentual sobre a nota máxima do escopo (em p.p.) e se foi atingido.
  - "Atingido" só vale quando todos os cortes aplicáveis são satisfeitos.
  - A anulada conta como ponto e como acerto, como diz o edital.
  - O corte da discursiva fica fora.

O `config.yaml` aceita um `concurso_alvo` opcional. Sem ele, as funções devolvem todos os concursos.

Ver `docs/spec-fase3.md`, histórias 51–53 e 59.

**Blocked by:** 02 (Notas de corte com unidade e escopo)

**Status:** ready-for-agent

- [ ] Teste: a nota ponderada bate com o cálculo manual numa fixture com pesos 1, 2 e 0,5.
- [ ] Teste: "atingido" falso quando o conjunto passa mas uma disciplina zera ou um bloco fica abaixo.
- [ ] Teste: "atingido" verdadeiro só com todos os cortes satisfeitos.
- [ ] Teste: num corte em acertos, a anulada conta.
- [ ] Teste: sem `concurso_alvo`, saem todos os concursos.
- [ ] `docs/modelo.md` documenta as fórmulas e o `concurso_alvo`.
- [ ] `uv run pytest` e `ruff` verdes.
