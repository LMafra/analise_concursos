# 11: Verificação com dados reais e documentação

**What to build:** a fase 3 conferida com os nove concursos reais e documentada.

- **Verificação, sem ampliar o escopo:** os nove concursos têm edital estruturado, discrepâncias e catálogo. Os cortes extraídos batem com as Further Notes da spec. Qualquer falha vira correção pontual ou ticket novo.
- **README:** seção "Fase 3 — Edital como fonte de verdade e descoberta", com:
  - as saídas novas;
  - os campos novos de configuração (`edital.retificacoes` e `concurso_alvo`);
  - como ler o catálogo e as discrepâncias.
- **AGENTS.md:** convenções de extração e de descoberta (regras 7–11 da spec) e um ponteiro para o template do catálogo no modelo de domínio.

Ver `docs/spec-fase3.md`, história 70 e a seção "Testing Decisions".

**Blocked by:** 03, 04, 05, 06, 10

**Status:** ready-for-agent

- [ ] Os nove concursos têm as três saídas novas.
- [ ] Os cortes batem com a tabela das Further Notes.
- [ ] Pelo menos três descobertas além da lista conhecida aparecem com trecho e uso.
- [ ] O arquivo de correção de cada concurso não muda.
- [ ] Todos os notebooks executam do zero.
- [ ] README e AGENTS.md atualizados.
- [ ] `uv run pytest` e `ruff` verdes.
