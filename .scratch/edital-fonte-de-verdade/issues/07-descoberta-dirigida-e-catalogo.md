# 07: Descoberta dirigida e catálogo de descobertas

**What to build:** um registro versionado de candidatos a metadado.

- Cada candidato declara o uso no projeto, o impacto e a severidade quando ausente.
- Entre os candidatos: alternativas, tipo de questão, marcação, tempo, consulta, fases, peso das fases, aprovação, desempate, legislação-base, bibliografia, vagas, validade, locais, anulação, discursiva e recurso.

Em cada concurso, cada candidato sai com status `encontrado`, `nao_encontrado` ou `ambiguo`, com trecho, e nenhum some da saída.

Um markdown de catálogo por concurso, cujo cabeçalho mostra o nome oficial e o cargo, tem três partes:

- **Tabela:** informação, valor, trecho de origem, uso, impacto e status (aplicado, proposto ou descartado).
- **Propostas de evolução:** as descobertas de alto impacto fora desta fase. A que afeta uma fase anterior (por exemplo, alternativas no OCR da folha) vira só proposta, com diff estimado.
- **Descartados:** cada item com o motivo.

O CSV de discrepâncias ganha um `error` quando o edital diz 5 alternativas e o gabarito só usa letras até D.

Ver `docs/spec-fase3.md`, histórias 35–43 e 47.

**Blocked by:** 01 (Identificação do concurso e escopo por cargo)

**Status:** done

- [x] Teste puro: um candidato não encontrado sai com status explícito.
- [x] Teste puro: um candidato encontrado traz trecho, documento e página.
- [x] Teste de CLI: o catálogo tem a tabela, as propostas e os descartados.
- [x] Teste de CLI: 5 alternativas no edital e gabarito até D geram `error`.
- [x] O template do catálogo está em `docs/modelo.md`.
- [x] `uv run pytest` e `ruff` verdes.
