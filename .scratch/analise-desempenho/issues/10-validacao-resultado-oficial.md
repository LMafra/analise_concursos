# 10: Validação contra o resultado oficial

**What to build:** quando o `concurso.yaml` aponta um resultado oficial (com o identificador do candidato, quando necessário), a análise extrai os acertos ou a nota oficiais e compara com os calculados. Se divergir, há alerta destacado no relatório e no log. Formatos cobertos: o resultado individual da CPNU (acertos de conhecimentos gerais e dos eixos 1–5), a lista geral da Dataprev (por inscrição) e o resultado final da SENAPPEN. Para a CRECI, a nota final só é usada se o edital confirmar que ela é apenas da objetiva.

**Blocked by:** 04, 09

**Status:** ready-for-agent

- [ ] Testes de texto para estrutura com trechos anonimizados de cada formato de resultado.
- [ ] Teste ponta a ponta: um concurso sintético com resultado divergente gera alerta no relatório.
- [ ] Na `cpnu` real, os acertos calculados (Tipo 2) batem com o oficial. Isso confirma o tipo e a leitura da folha; registrar no ticket.
