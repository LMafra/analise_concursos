# 04: Distribuição de questões e validação das contagens

**What to build:** o edital estruturado ganha a distribuição declarada:

- número de questões gerais e específicas (ou por prova, no Cebraspe);
- número por disciplina, quando o edital declara (FGV);
- número por tipo (certo/errado, múltipla escolha, discursiva).

Quando o edital não declara a distribuição por disciplina, o campo fica vazio com fonte default, sem aviso.

O CSV de discrepâncias compara a distribuição com as questões e o gabarito do concurso:

- `error` quando o total ou o total de um bloco diverge;
- `warn` quando a contagem por disciplina diverge, só onde o edital declara, casando pela disciplina canônica.

Ver `docs/spec-fase3.md`, histórias 15–18 e 44–46.

**Blocked by:** 01 (Identificação do concurso e escopo por cargo)

**Status:** done

- [x] Teste puro: distribuição FGV por disciplina com trecho real (AgSUS TI ou CPRM ADS).
- [x] Teste puro: no Cebraspe, a distribuição sai só por prova, e o campo por disciplina fica vazio sem aviso.
- [x] Teste de CLI: um total divergente gera `error`.
- [x] Teste de CLI: uma contagem por disciplina divergente gera `warn`.
- [x] `docs/modelo.md` documenta o bloco de distribuição.
- [x] `uv run pytest` e `ruff` verdes.
