# 12: Tópicos por similaridade e revisão manual

**What to build:** cada questão recebe tópico (e disciplina, quando o caderno não tem cabeçalhos, como na Cebraspe) sugerido por similaridade TF-IDF entre o texto do bloco de comando ou enunciado e os tópicos do edital estruturado, com score. É gerado um arquivo de revisão que o usuário edita. Quando existe, ele tem prioridade sobre a sugestão, e editá-lo dispara o reprocessamento. `desempenho_por_topico.csv` passa a ter tópicos reais.

**Blocked by:** 11

**Status:** done

- [x] Teste de texto para estrutura: a segmentação de prova Cebraspe agrupa os itens por bloco de comando.
- [x] Teste: um bloco sobre "NoSQL" recebe o tópico correspondente de um edital de fixture.
- [x] Teste ponta a ponta: a revisão manual sobrescreve a sugestão e aparece no desempenho por tópico.
- [x] O score fica visível na tabela de questões e no arquivo de revisão.

## Verificação com concursos reais

- Texto por questão (caderno lido em duas colunas): cobertura de 89-100% (cpnu 89/90, pf_perito 69/70, demais 100%).
- Cebraspe (tcu_25, cd_25): itens agrupados pelo bloco "julgue"; cabeçalhos de página ("CEBRASPE – ... – Edital") descartados.
- Score mediano: tcu_25 0,14; cd_25 0,12; agsus 0,05. Itens de interpretação de texto/inglês têm score baixo (< 0,03) e sugestão fraca; ficam visíveis pelo score para revisão (sem corte automático, conforme a spec).
- Editar `revisao/questoes_revisado.csv` dispara o reprocessamento; o tópico revisado aparece em `desempenho_por_topico.csv`.
