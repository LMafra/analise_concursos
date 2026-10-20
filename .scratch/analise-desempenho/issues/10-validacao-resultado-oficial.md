# 10: Validação contra o resultado oficial

**What to build:** quando o `concurso.yaml` aponta um resultado oficial (com o identificador do candidato, quando necessário), a análise extrai os acertos ou a nota oficiais e compara com os calculados. Se divergir, há alerta destacado no relatório e no log. Formatos cobertos: o resultado individual da CPNU (acertos de conhecimentos gerais e dos eixos 1–5), a lista geral da Dataprev (por inscrição) e o resultado final da SENAPPEN. Para a CRECI, a nota final só é usada se o edital confirmar que ela é apenas da objetiva.

**Blocked by:** 04, 09

**Status:** done

- [x] Testes de texto para estrutura com trechos anonimizados de cada formato de resultado.
- [x] Teste ponta a ponta: um concurso sintético com resultado divergente gera alerta no relatório.
- [x] Na `cpnu` real, os acertos calculados (Tipo 2) batem com o oficial. Isso confirma o tipo e a leitura da folha; registrar no ticket.

## Verificação

`concurso.yaml` aceita `resultado_oficial: {arquivo, identificador, pesos: [{itens: [a, b], peso: x}]}` (peso padrão 1). Acertos são comparados diretamente; pontos somam peso × acerto (Cebraspe: peso × (acerto − erro)). Divergência gera `WARNING` no log e alerta `> **Atenção:**` na seção "Validação com o resultado oficial" do `relatorio.md`; erro de leitura não bloqueia a análise e é relatado da mesma forma. Resultado final do concurso (cabeçalho "RESULTADO FINAL DO CONCURSO" na primeira página) é só informativo.

| Arquivo real | Extraído | Observação |
|---|---|---|
| cpnu `RESULTADO-FASE-OBJETIVA.PDF` | 52 acertos (16, 8, 3, 11, 9, 5) | pipeline calcula 52 com o Tipo 2: confere |
| dataprev resultado objetiva | 72,5 pontos (página 142) | exige `pesos` (específicas 2,5); validar no ticket 16 |
| senappen resultado | 57 pontos (página 32) | validar no ticket 16 |
| creci resultado final | 44 pontos (página 5) | inclui discursiva: apenas informativo |
