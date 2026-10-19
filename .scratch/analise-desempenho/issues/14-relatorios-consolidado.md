# 14: Relatórios completos e consolidado

**What to build:** cada concurso ganha um relatório completo:
- resumo;
- gráficos PNG por disciplina e tópico;
- lista de questões para revisar (leitura e tópico);
- alertas de validação oficial;
- status do gabarito.

O consolidado traz o desempenho geral de todos os concursos e um comparativo que responde "em quais tópicos meu desempenho é consistentemente baixo entre concursos?" (abaixo do limiar configurável em pelo menos 2 concursos). Também lista os concursos incompletos com o motivo e os que ainda usam gabarito preliminar.

**Blocked by:** 05, 12

**Status:** ready-for-agent

- [ ] Teste ponta a ponta com três concursos sintéticos, um tópico fraco em dois deles: o comparativo lista esse tópico.
- [ ] O consolidado inclui os concursos incompletos e o status do gabarito.
- [ ] O relatório referencia os gráficos gerados, e todos os arquivos referenciados existem.
- [ ] O desempenho geral consolidado soma exatamente os desempenhos por concurso.
