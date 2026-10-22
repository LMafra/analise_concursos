# 09: `--reuse-csv` e CSV manual

**What to build:** o candidato corrige o `respostas_extraidas.csv` no Excel ou no LibreOffice e roda `analyze <id> --reuse-csv`.

O CSV corrigido é copiado para `candidatos/<slug>/respostas_revisadas.csv`. A partir daí, ele vence a folha e entra no manifesto.

Quem não tem folha informa as respostas num CSV com as colunas `questao,alternativa`.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Um `respostas_extraidas.csv` com `revisar=true`, corrigido à mão e aplicado com `--reuse-csv`, muda a nota conforme a correção.
- [ ] A execução seguinte não reprocessa nada. Trocar a folha depois gera um aviso de revisão antiga.
- [ ] Um CSV `questao,alternativa` sem folha roda o pipeline inteiro.
- [ ] `--reuse-csv` sem CSV de leitura gera mensagem com `dica:`.
