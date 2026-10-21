# 08: Evolução e fraquezas por tópico (notebook 03)

**What to build:** um notebook que mostra quais tópicos do edital foram cobrados e quais continuam fracos. Com a amostra pequena por prova (mediana de 2 questões por tópico), a análise principal usa contagens somadas entre concursos.

- **`cobertura_edital`:** por concurso, quantos tópicos do edital estruturado foram efetivamente cobrados na prova. Tópicos nunca cobrados ficam fora da análise de evolução.
- **`evolucao_por_topico`:**
  - slope sobre o percentual ajustado, via `scipy.stats.linregress`, com p-value e n;
  - só para tópicos com 3 pontos ou mais e n ≥ 5 (o mínimo é configurável);
  - nos outros, devolve "amostra insuficiente" em vez de um slope.
- **`topicos_fracos_persistentes`:**
  - limiar padrão de 0,6 sobre o percentual ajustado, em pelo menos 2 concursos;
  - acertos e erros somados entre concursos, com n agregado ≥ 5;
  - devolve a lista dos concursos abaixo do limiar.
- **Gráficos:**
  - heatmap de tópicos (linhas) por concursos (colunas), com o percentual anotado só onde n ≥ 5 e o resto em cinza com o rótulo "n<5";
  - barras empilhadas de acertos e erros dos tópicos fracos persistentes, com n anotado.
- O notebook abre com a pergunta e fecha com uma conclusão em prosa, e não contém lógica de negócio.

Ver `docs/spec-fase2.md` (histórias 37, 43, 44, 54 e 56).

**Blocked by:** 05 (Taxonomia de disciplinas e bloco geral/específico)

**Status:** done

- [x] Testes:
  - cobertura com tópico nunca cobrado;
  - evolução com n < 5, um concurso só e menos de 3 pontos (sem slope);
  - fracos persistentes com soma entre concursos e a regra de 2 concursos;
  - correção líquida comparada à bruta;
  - tópico sem gabarito.
- [x] Testes de que o heatmap anota só as células com n ≥ 5 e que as barras trazem n.
- [x] Com dados reais, a lista de fracos persistentes é coerente com o comparativo da fase 1, e as diferenças são explicadas na conclusão do notebook.
- [x] O notebook 03 executa do zero pelo script.
- [x] `uv run pytest` e `ruff` verdes.

## Decisões na implementação

- **Cobertura pelas palavras-chave do tópico:** o casamento com o edital ignora a disciplina, porque a da prova nem sempre repete a do edital (no agsus, as questões de TI estão como "Tecnologia da Informação"). Um tópico repetido em duas disciplinas do edital conta uma vez.
- **Bloco fora da identidade do tópico:** o tópico é disciplina canônica mais palavras-chave, como no spec. O mesmo tópico nas provas geral e específica de um concurso é uma linha só; antes, ele contava duas vezes para a regra dos 2 concursos.
- **Fracos persistentes como na fase 1:** o n de cada concurso não importa e o percentual agregado não precisa ficar abaixo do limiar; o que muda é o n agregado ≥ 5 e o percentual ajustado. O notebook passa o `limiar_topico_baixo` do `config.yaml`.
- **Séries com amostra insuficiente aparecem:** `evolucao_por_topico` lista todo tópico datado, com `pontos` e `n` só dos pontos com n ≥ `min_n` e `n_total` de todos. A mudança vale também para a tendência e a correlação por disciplina do ticket 07.
- **Heatmap só com tópicos em 2 concursos ou mais:** dos 345 tópicos, só 35 se repetem entre concursos.
