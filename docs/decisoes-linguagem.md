# Decisões: linguagem leiga e o index.html como painel

Registro curto das escolhas, com o contexto e as alternativas descartadas. A spec está em `docs/spec-linguagem.md`.

## 1. O técnico muda de lugar, não some

- **Contexto:** o público é leigo, mas o usuário atual valoriza p-valores, slopes, z-scores e a origem de cada regra.
- **Decisão:** a parte principal de cada artefato fala a língua do usuário; o rigor vai para um `<details>` fechado (relatórios), para a linha `detalhe:` (mensagens) ou para `docs/detalhes-tecnicos.md` (README).
- **Descartado:** apagar os detalhes; dois relatórios separados (um leigo e um técnico).

## 2. Redesenho no index, reescrita no relatório por concurso

- **Decisão:** o `index.html` ganha estrutura nova (resumo, cards, selos, ações, apêndice). O `relatorio.md` e o `relatorio.html` por concurso só ganham texto leigo e uma seção final "Detalhes técnicos", que o HTML fecha num `<details>`.
- **Por quê:** o `index.html` responde "como estou saindo" no conjunto; o relatório do concurso é consulta pontual, e o layout dele já funciona.

## 3. Diferenças de paridade intencionais

- **Contexto:** `scripts/paridade.py` compara os hashes de `analises/`, menos o `index.html`.
- **Decisão:** mudam de propósito o `relatorio.md`, os PNGs do consolidado (título e eixos) e os markdowns `radar_editais.md`, `simulado_focado.md`, `recomendacoes_estudo.md` e `resumo_pratica.md`. Elas ficam declaradas em `scripts/paridade_esperadas.toml`, com padrão, motivo e versão, e o `comparar --esperadas` as aceita. Sem a flag, o `comparar` continua estrito.
- **Não mudam:** CSVs, parquet, `correcao.json`, `edital_estruturado.json` e `relatorio_evolucao.md`. Os avisos gravados ficam técnicos; a tradução acontece só na apresentação, por `linguagem.traduzir_aviso` (aviso sem padrão sai como "Observação técnica: <original>").
- **Descartado:** gravar avisos estruturados (`{codigo, parametros}`), que mudaria o `edital_estruturado.json`.

## 4. "No limite" a 2 p.p.

- **Decisão:** `FAIXA_NO_LIMITE = 2.0` p.p. em torno do corte, para cima ou para baixo. Fora da faixa, o "atingido" de todos os cortes decide Acima ou Abaixo.
- **Descartado:** 5 p.p. (larga demais para provas com corte apertado); sem faixa.

## 5. Tendência honesta

- **Decisão:** "Melhorando" ou "Piorando" só com p < 0,05. Sem significância e |ρ| ≥ `RHO_LEVE` (0,3): "Leve alta" ou "Leve queda", sempre com "ainda dentro da variação normal". Senão, "Estável". Com menos de 3 concursos com data, "Ainda não dá para afirmar".
- **Risco aceito:** "leve queda" sem significância pode soar como piora; o complemento "ainda dentro da variação normal" é obrigatório no texto.

## 6. Tópico fraco descrito por acertos

- **Contexto:** o percentual ajustado é `acerto − erro/(k−1)` por item (`analytics/correcao.py`), com o branco valendo 0. Chutar dá 0%, e o 60% é o `limiar_topico_baixo` escolhido pelo usuário. "−43%, 43% abaixo do esperado" e "o chute daria 60%" estariam errados.
- **Decisão:** na parte principal, "Acertou 2 de 7 questões, menos do que acertaria chutando" (ajustado < 0, o que implica acertos < n/k) ou "Acertou 5 de 9; descontado o chute, ficou em 30%, abaixo do mínimo de 60% que você definiu". O número ajustado e a fórmula ficam no apêndice.
- **Descartado:** mostrar o percentual do chute (exigiria o k de cada questão, que o consolidado não guarda).

## 7. Fortes e fracos com o mesmo limiar

- **Decisão:** pontos fortes são disciplinas (n ≥ 5, ajustado ≥ limiar, até 5); pontos fracos são tópicos (`topicos_fracos_persistentes`). A faixa neutra é intencional: nem tudo é forte ou fraco. Uma disciplina forte com um tópico fraco continua forte, e o grupo de fracos diz "mesmo indo bem no geral".
- **Prioridade:** concursos abaixo × (limiar − percentual); o n já é filtrado.
- **Descartado:** limiar próprio para forte; tópicos como pontos fortes (amostra pequena).

## 8. Mensagens em três linhas

- **Decisão:** `erro:` ou `aviso:` (leigo, primeira pessoa), `dica:` (ação) e, quando houver, `detalhe:` (o texto técnico). `ErroDoUsuario` e `ErroDoAmbiente` ganham `detalhe`; os avisos passam por `avisar(logger, texto, dica, detalhe)`. Mensagem INFO sai sem prefixo. `--quiet` não esconde o `detalhe:`. Na GUI, o detalhe fica num "Ver detalhes técnicos" fechado.
- **Pasta de provas:** o app nunca pergunta e nunca cria a pasta, nem com `--yes`; a dica aponta o cadastro e o `--provas`.
- **Descartado:** só `erro:` e `dica:` (perderia o detalhe na tela); o técnico só no log.

## 9. Acessibilidade do index

- **Decisão:** além do contraste AA, ícone com `aria-hidden` e texto visível no selo, `<caption>` e `th scope="col"`, títulos sem pular nível, `alt` e `<figcaption>`, um `<nav>` "Ir para" e o `<details>` nativo. Tudo testado.

## 10. Snapshots com syrupy

- **Decisão:** `syrupy` no grupo dev; cada seção do index como `.html` próprio, para o diff do PR ser legível.
- **Descartado:** golden files com helper próprio.
