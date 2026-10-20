# 14: Relatórios completos e consolidado

**What to build:** cada concurso ganha um relatório completo:
- resumo;
- gráficos PNG por disciplina e tópico;
- lista de questões para revisar (leitura e tópico);
- alertas de validação oficial;
- status do gabarito.

O consolidado traz o desempenho geral de todos os concursos e um comparativo que responde "em quais tópicos meu desempenho é consistentemente baixo entre concursos?" (abaixo do limiar configurável em pelo menos 2 concursos). Também lista os concursos incompletos com o motivo e os que ainda usam gabarito preliminar.

**Blocked by:** 05, 12

**Status:** done

- [x] Teste ponta a ponta com três concursos sintéticos, um tópico fraco em dois deles: o comparativo lista esse tópico.
- [x] O consolidado inclui os concursos incompletos e o status do gabarito.
- [x] O relatório referencia os gráficos gerados, e todos os arquivos referenciados existem.
- [x] O desempenho geral consolidado soma exatamente os desempenhos por concurso.

## Verificação com dados reais

- 9 concursos analisados e consolidados; creci aparece como incompleto (sem respostas).
- Disciplinas consistentemente baixas: Língua Portuguesa (4 concursos), Legislação, Língua Inglesa, Bancos de Dados. Tópicos: coesão textual (cd_25, pf_perito), compreensão de textos em inglês (cd_25, tcu_25), desenvolvimento de sistemas (funpresp_jud, infrasa).
- Nomes de tópicos/disciplinas de editais diferentes são comparados pelas palavras-chave (sem acento, caixa e palavras vazias).
- Gráficos PNG (matplotlib, backend Agg) conferidos visualmente (tcu_25 tópicos, cpnu disciplinas).
- Validação oficial persistida em `validacao_oficial.json` por concurso para o consolidado.
