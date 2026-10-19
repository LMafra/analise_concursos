# 04: Gabaritos FGV e lista "01: A" em PDF

**What to build:** o usuário aponta gabaritos com várias seções e informa cargo e tipo (ou prova A/B) no `concurso.yaml`. A análise seleciona a seção certa. Há dois formatos:
- **FGV:** cabeçalhos "cargo - tipo - turno" ou "cargo - TIPO n", inclusive o gabarito do CPNU por bloco temático e tipo; "*" marca anulada.
- **Lista "NN: R":** SELECON e Quadrix, com seções por código/cargo e "PROVA A/B"; "X" ou "*" marca anulada.

O parser também expõe a listagem das seções disponíveis, que o assistente de cadastro vai usar.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Trechos reais anonimizados de cada formato são interpretados nos testes de texto para estrutura.
- [ ] Cargo/tipo inexistente gera erro listando as seções disponíveis.
- [ ] A listagem de seções retorna cargo, tipo e quantidade de questões de cada seção.
- [ ] O status preliminar ou definitivo é detectado (por exemplo, nos dois gabaritos da CRECI).
- [ ] A verificação manual nos gabaritos reais de `agsus`, `cprm`, `cpnu`, `dataprev_2024`, `senappen` e `creci` extrai a seção esperada.
