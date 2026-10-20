# 03: Data da prova e metadados do concurso

**What to build:** cada concurso passa a ter a data da prova e os metadados necessários para o eixo temporal e para estratificar as análises.

- **Data da prova:**
  - É extraída do edital em dois formatos: cronograma ("Aplicação das provas objetivas … d/m/aaaa", Cebraspe e IBEST) e texto corrido ("dia dd de mês de aaaa", FGV).
  - O `concurso.yaml` aceita `data_prova` em ISO 8601. Ela tem prioridade sobre o edital, porque no edital a data é sempre "provável" e pode ser retificada.
  - Sem data em nenhuma fonte, o concurso recebe aviso e fica sem data. Nada é imputado: nem data de modificação de arquivo, nem data de publicação do edital.
- **Metadados:** o `concurso.yaml` aceita `nivel` (federal, estadual ou municipal) e `escolaridade` (superior ou médio), ambos opcionais. Sem valor, ficam como `nao_informado`.
- O arquivo de correção passa a registrar a data da prova e a fonte da data.
- Os 9 `concurso.yaml` analisados são preenchidos com nível e escolaridade. O `cd_25` fica com escolaridade `medio`. `data_prova` só é preenchida onde a data do edital estiver errada.

Ver `docs/spec-fase2.md` (histórias 19, 20, 22, 23 e 24) e a tabela de datas esperadas.

**Blocked by:** 01 (Correção do edital ponta a ponta)

**Status:** ready-for-agent

- [ ] Testes de extração da data nos dois formatos, com trechos reais.
- [ ] Testes da precedência configuração, depois edital, depois ausente com aviso.
- [ ] Teste de CLI: os campos novos opcionais do `concurso.yaml` são aceitos e validados, e valores inválidos geram erro claro com o campo.
- [ ] Com dados reais, as datas resolvidas batem com a tabela da spec. Do mais antigo para o mais recente: pf_perito 27/07/2025, cpnu 05/10/2025, agsus 12/10/2025, cprm 30/11/2025, telebras 08/02/2026, tcu_25 22/02/2026, cd_25 08/03/2026, infrasa 15/03/2026 e funpresp_jud 05/07/2026.
- [ ] `docs/modelo.md` atualizado com `data_prova`, `nivel` e `escolaridade`.
- [ ] `uv run pytest` e `ruff` verdes.
