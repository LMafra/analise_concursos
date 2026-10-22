# 05: Pesos do edital comparados com o peso realizado

**What to build:** o edital estruturado registra o tipo de peso declarado, que pode ser:

- uniforme;
- por disciplina;
- por tipo de questão;
- por bloco;
- por faixa de itens;
- fórmula.

O quadro de eixos do CPNU vira "por faixa de itens", por variante, no mesmo formato de faixas do arquivo de correção.

O peso do edital é a expectativa, e o do arquivo de correção é o realizado; a nota não muda. O CSV de discrepâncias ganha duas regras:

- `warn` quando o peso realizado diverge do peso do edital;
- `error` quando os pesos dos eixos do CPNU não somam os 10 que o edital declara.

Ver `docs/spec-fase3.md`, histórias 10–14 e 49–50.

**Blocked by:** 01 (Identificação do concurso e escopo por cargo)

**Status:** ready-for-agent

- [ ] Teste puro: o quadro de eixos do CPNU por variante sai com tipo por faixa de itens.
- [ ] Teste puro: um edital Cebraspe sai com peso uniforme.
- [ ] Teste de validação: uma soma diferente de 10 gera `error`.
- [ ] Teste de validação: um peso realizado diferente do edital gera `warn`.
- [ ] O arquivo de correção não muda.
- [ ] `docs/modelo.md` documenta o bloco de pesos.
- [ ] `uv run pytest` e `ruff` verdes.
