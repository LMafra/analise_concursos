# 12: Tópicos por similaridade e revisão manual

**What to build:** cada questão recebe tópico (e disciplina, quando o caderno não tem cabeçalhos, como na Cebraspe) sugerido por similaridade TF-IDF entre o texto do bloco de comando ou enunciado e os tópicos do edital estruturado, com score. É gerado um arquivo de revisão que o usuário edita. Quando existe, ele tem prioridade sobre a sugestão, e editá-lo dispara o reprocessamento. `desempenho_por_topico.csv` passa a ter tópicos reais.

**Blocked by:** 11

**Status:** ready-for-agent

- [ ] Teste de texto para estrutura: a segmentação de prova Cebraspe agrupa os itens por bloco de comando.
- [ ] Teste: um bloco sobre "NoSQL" recebe o tópico correspondente de um edital de fixture.
- [ ] Teste ponta a ponta: a revisão manual sobrescreve a sugestão e aparece no desempenho por tópico.
- [ ] O score fica visível na tabela de questões e no arquivo de revisão.
