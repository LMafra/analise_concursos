# 01: Identificação do concurso e escopo por cargo, ponta a ponta

**What to build:** ao rodar `concursos analisar`, o edital estruturado de cada concurso ganha um bloco de identificação, extraído do próprio edital:

- nome oficial, como na capa;
- cargo e especialidade;
- vagas (ampla concorrência e reservas), cadastro de reserva e teto de classificados.

O cargo segue duas regras:

- **Edital de um só cargo:** o cargo vem do edital, mesmo que a configuração não declare nenhum.
- **Edital de vários cargos:** o cargo da configuração é casado com a lista do edital por texto normalizado, e o trecho do cargo casado passa a ser o escopo das extrações seguintes.

Se nada casar, o CSV de discrepâncias recebe um `warn`, e a extração usa o concurso inteiro, com confiança reduzida.

Este ticket também prepara o terreno para os demais:

- a gravação do conteúdo programático passa a preservar as chaves do edital estruturado que não são dela;
- o CSV de discrepâncias nasce, com o contrato completo e esta primeira regra;
- o cabeçalho do relatório por concurso mostra o nome oficial e o cargo;
- a versão da análise no manifesto sobe, para regenerar os concursos já analisados.

Nada disso muda os CSVs das fases 1 e 2, e a coluna de concurso continua sendo o slug da pasta.

Ver `docs/spec-fase3.md`, histórias 1–9, 65 e 67–69.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Teste de CLI: o edital estruturado tem a identificação com trecho, documento e página.
- [ ] Teste de CLI: o conteúdo programático continua no edital estruturado depois de regravado.
- [ ] Teste puro: num edital de um só cargo, o cargo vem do edital.
- [ ] Teste puro: num edital de dois cargos, o escopo é o trecho do cargo da configuração.
- [ ] Teste de CLI: um cargo sem casamento gera `warn` no CSV de discrepâncias.
- [ ] Os CSVs existentes mantêm exatamente as mesmas colunas.
- [ ] A mudança de versão no manifesto regenera as saídas.
- [ ] O cabeçalho do relatório mostra o nome oficial e o cargo.
- [ ] `docs/modelo.md` documenta o bloco de identificação e o contrato do CSV de discrepâncias.
- [ ] `uv run pytest` e `ruff` verdes.
