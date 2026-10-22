# 10: Relatório HTML por candidato

**What to build:** cada execução gera `analises/<slug>/index.html`, um HTML estático que reaproveita o markdown e os PNGs das fases 1 a 3. O relatório traz:

- os concursos;
- o desempenho por disciplina e por tópico;
- a evolução;
- o gap para o corte;
- o que o app decidiu sozinho;
- os avisos;
- a origem e a data da geração.

O relatório abre no navegador, e no WSL no navegador do Windows, só na primeira execução ou quando algo foi reprocessado. Os comandos `report` e `export --format csv|parquet|md` vêm junto.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] O `index.html` contém, por concurso, o link para o relatório do concurso e os números do desempenho geral.
- [ ] Sem mudanças, a execução não abre o navegador e só imprime o caminho. `--no-open` impede a abertura.
- [ ] `report` reabre o último relatório.
- [ ] `export --format csv|parquet|md` grava o consolidado do candidato no formato pedido.
- [ ] O HTML funciona sem rede: CSS embutido e imagens por caminho relativo.
