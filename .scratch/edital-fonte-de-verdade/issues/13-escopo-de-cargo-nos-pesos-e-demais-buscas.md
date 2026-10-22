# 13: Escopo de cargo nos pesos e nas demais buscas

**What to build:** a história 6 vale também para os pesos. Hoje `_extrair_pesos` não recebe o `_Escopo`, e a soma dos eixos (`_SOMA_DOS_PESOS`) e a regra de pontuação (`extrair_fator_correcao`) são lidas do documento inteiro. Num edital com vários cargos, isso pode pegar o peso de outro cargo.

- **Pesos:** `_extrair_pesos` passa a receber o escopo; a soma dos eixos e a regra de pontuação só valem quando `escopo.aplica` aceita o achado. `extrair_fator_correcao` mora em `correcao` e não deve importar `regras_edital`: o filtro fica do lado de `regras_edital`, sobre a posição do trecho que ela devolve.
- **Demais buscas sem escopo:** o cadastro de reserva (`_CADASTRO_DE_RESERVA`), o tipo de questão em `_por_tipo` e o cronograma. Para cada uma, decidir se o trecho é do cargo (escopo) ou do concurso inteiro (cronograma costuma ser comum a todos); registrar a decisão em `docs/modelo.md`.
- A regra 11 vale: se a mudança alterar um valor já validado nos nove concursos, a mudança vira proposta, não é aplicada em silêncio. Conferir `edital_estruturado.json` dos nove antes e depois.

Ver `docs/spec-fase3.md`, história 6.

**Blocked by:** nenhum

**Status:** ready-for-agent

- [ ] Teste: num edital sintético com dois cargos e pesos diferentes, cada cargo lê só o seu.
- [ ] Teste: o cadastro de reserva e o tipo de questão de outro cargo não vazam.
- [ ] Os nove `edital_estruturado.json` reais ficam iguais (ou a diferença é apresentada como proposta).
- [ ] `docs/modelo.md` atualizado; `uv run pytest` e `ruff` verdes.
