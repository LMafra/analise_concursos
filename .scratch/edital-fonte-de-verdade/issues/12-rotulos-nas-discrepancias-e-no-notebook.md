# 12: Nome oficial e cargo nas discrepâncias e no notebook 05

**What to build:** os rótulos que faltam da decisão "Rótulos" da spec. Hoje só o catálogo e o relatório mostram nome oficial e cargo.

- **`discrepancias_edital.csv`:** colunas `nome_oficial` e `cargo` (com a especialidade, quando houver), vindas da `identificacao` do edital estruturado, em todas as linhas. O CSV é novo na fase 3, então mudar o schema não fere a regra de "sem mudança de schema", que vale para `correcao.json`, os CSVs das fases 1 e 2 e o parquet. Atualizar `COLUNAS_DISCREPANCIAS` e `docs/modelo.md`.
- **Notebook 05:** uma função testada em `insights` que, a partir de `regras_por_concurso`, dá o rótulo `slug: nome oficial — cargo` de cada concurso; o notebook a exibe na célula de carregamento (só o alvo, quando há `concurso_alvo`). A coluna de concurso das tabelas continua sendo o slug.
- Sem nome oficial ou cargo encontrado, o rótulo cai no slug, sem inventar texto.

Ver `docs/spec-fase3.md`, Implementation Decisions, "Rótulos".

**Blocked by:** nenhum

**Status:** ready-for-agent

- [ ] Teste: o CSV de discrepâncias sai com `nome_oficial` e `cargo` em todas as linhas, inclusive no arquivo só com cabeçalho.
- [ ] Teste: o rótulo junta slug, nome oficial e cargo, e cai no slug quando falta a identificação.
- [ ] Notebook 05 exibe os rótulos e roda do zero.
- [ ] `docs/modelo.md` atualizado; `uv run pytest` e `ruff` verdes.
