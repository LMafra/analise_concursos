# 14: Precedência completa com a configuração

**What to build:** a precedência retificação → edital → configuração → default da história 33 em todos os campos que o `concurso.yaml` declara. Hoje a configuração só entra como reserva do corte do conjunto (`nota_corte`).

- **Distribuição:** sem o total de questões no edital, usar o `total_itens` do `concurso.yaml` com `FonteRegra.CONFIG`, antes do aviso de default.
- **Pesos:** sem quadro de eixos nem regra de pontuação no edital, usar os `pesos` do `correcao` (ou das variantes) com `FonteRegra.CONFIG`; o tipo é uniforme quando todos os pesos são iguais e por faixa de itens quando não são.
- **Aviso de divergência:** quando o edital e a configuração declaram valores diferentes, o edital vence e sai um aviso, como já acontece com a nota de corte.
- O aviso de default (`_aviso_de_default`) só aparece quando nem o edital nem a configuração têm o valor.

Ver `docs/spec-fase3.md`, história 33.

**Blocked by:** nenhum

**Status:** ready-for-agent

- [ ] Teste: sem total no edital, a distribuição usa o `total_itens` do config com fonte `config` e sem aviso de default.
- [ ] Teste: sem pesos no edital, os pesos vêm do config com fonte `config`.
- [ ] Teste: edital e config divergentes geram aviso, e o edital vence.
- [ ] Os nove `edital_estruturado.json` reais conferidos; mudança de valor vira proposta (regra 11).
- [ ] `docs/modelo.md` atualizado; `uv run pytest` e `ruff` verdes.
