# 03: Retificações declaradas

**What to build:** o `concurso.yaml` aceita uma lista de PDFs de retificação no bloco do edital.

- As retificações são lidas depois do edital e dos anexos, e a mais recente vence campo a campo.
- Quando uma retificação define um campo, a fonte dele vira `retificacao`, com o trecho e o documento da retificação.
- As notas "(Retificado por meio do Edital nº N)" no texto do edital também marcam a fonte como retificação.

Ver `docs/spec-fase3.md`, histórias 28–30.

**Blocked by:** 02 (Notas de corte com unidade e escopo)

**Status:** ready-for-agent

- [ ] Teste de CLI: uma retificação declarada sobrescreve o corte e marca a fonte como `retificacao`.
- [ ] Teste puro: um trecho com nota inline de retificação sai com fonte `retificacao`.
- [ ] Teste de CLI: `edital.retificacoes` é validado como os demais campos (lista de PDFs existentes).
- [ ] `docs/modelo.md` documenta o campo.
- [ ] `uv run pytest` e `ruff` verdes.
