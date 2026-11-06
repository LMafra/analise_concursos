# Pendências

O que ainda está aberto, conferido contra o código. Três itens da fase 3 não foram desenvolvidos (o código confirma que o comportamento pedido não existe), e algumas conferências cabem ao usuário ou dependem de ambiente que o CI não reproduz.

| Item | Fase | Tipo | Prioridade |
| --- | --- | --- | --- |
| [Nome oficial e cargo nas discrepâncias e no notebook 05](#issue-12) | 3 | Não feito | Baixa |
| [Escopo de cargo nos pesos e nas demais buscas](#issue-13) | 3 | Não feito | Alta |
| [Precedência completa com a configuração](#issue-14) | 3 | Não feito | Média |
| [Trecho de origem conferido à mão contra o PDF](#verificacao-fase2) | 2 | Conferência à mão | Baixa |
| [Checklist de máquina limpa e primeira release com atualizador](#verificacao-fase6) | 5 e 6 | Conferência à mão | Alta |

A prioridade dos itens da fase 3 segue o risco de número errado na análise: a 13 pode ler o peso de outro cargo num edital com vários cargos; a 14 deixa de usar um valor que o usuário declarou e cai no padrão; a 12 é só de apresentação.

## Ordem sugerida

1. **12** primeiro: é isolada, mexe só no `discrepancias_edital.csv` (novo na fase 3) e numa função de `insights`.
2. **13** depois: muda a assinatura de `_extrair_pesos`.
3. **14** por último: acrescenta a reserva da configuração no fim de `_extrair_pesos` e de `_extrair_distribuicao`. Fazer a 13 e a 14 em paralelo gera conflito na mesma função.

Para a 13 e a 14, valem as regras de [AGENTS.md](../AGENTS.md):

- antes, `concurso-analise --force` e `scripts/paridade.py retrato analises/<candidato> <arquivo>`; depois, `comparar`;
- se um valor já validado nos nove `edital_estruturado.json` reais mudar, a mudança vira proposta (status `proposto`, com o diff estimado) e não é aplicada em silêncio (regra 11 da spec da fase 3);
- `correcao.py` não importa `regras_edital`, e o `correcao.json`, os CSVs das fases 1 e 2 e o parquet mantêm schema e valores;
- `docs/modelo.md` muda na mesma entrega.

---

<a id="issue-12"></a>

## 12: Nome oficial e cargo nas discrepâncias e no notebook 05

### O que falta

A decisão "Rótulos" de `docs/spec-fase3.md` pede nome oficial e cargo no catálogo, nas discrepâncias, no notebook novo e no cabeçalho do relatório. Hoje só o catálogo e o relatório os mostram.

- `COLUNAS_DISCREPANCIAS`, em `src/concursos/analytics/validacao_edital.py`, tem só `item`, `esperado_edital`, `observado_prova`, `diferenca`, `severidade` e `acao_sugerida`.
- `src/concursos/analytics/insights.py` não tem função que monte o rótulo do concurso.
- `notebooks/05_corte_e_peso.py` identifica os concursos só pelo slug.

### Comportamento esperado

- `discrepancias_edital.csv` ganha as colunas `nome_oficial` e `cargo` (com a especialidade, quando houver), vindas da `identificacao` do edital estruturado, em todas as linhas, inclusive no arquivo só com cabeçalho.
- Uma função testada em `insights` recebe `regras_por_concurso` e devolve o rótulo `slug: nome oficial — cargo` de cada concurso. Sem nome oficial ou cargo, o rótulo é o slug, sem texto inventado.
- O notebook 05 exibe os rótulos na célula de carregamento (só o alvo, quando há `concurso_alvo`). A coluna de concurso das tabelas continua sendo o slug.

### Critérios de aceite

- [ ] Teste: o CSV de discrepâncias sai com `nome_oficial` e `cargo` em todas as linhas, inclusive no arquivo só com cabeçalho.
- [ ] Teste: o rótulo junta slug, nome oficial e cargo, e cai no slug quando falta a identificação.
- [ ] Notebook 05 exibe os rótulos e roda do zero (`scripts/rodar_notebooks.sh notebooks/05_corte_e_peso.py`).
- [ ] `docs/modelo.md` atualizado; `uv run pytest` e `ruff` verdes.

### Riscos

Baixo. O CSV é da fase 3, então a regra de schema estável não se aplica a ele. A paridade deve mostrar diferença só em `discrepancias_edital.csv`.

---

<a id="issue-13"></a>

## 13: Escopo de cargo nos pesos e nas demais buscas

### O que falta

A história 6 da spec da fase 3 (extração no escopo do cargo) vale para distribuição, cortes e prova, mas não para os pesos nem para algumas buscas. Em `src/concursos/analytics/regras_edital.py`:

- `_extrair_pesos(config, docs)` não recebe o `_Escopo`; `extrair_regras` o chama sem ele, enquanto `_extrair_distribuicao(config, docs, escopo)` já recebe.
- `docs.primeiro(_SOMA_DOS_PESOS)` procura a soma dos eixos no documento inteiro.
- `extrair_fator_correcao(docs.paginas[doc.nome], config.total_itens)` lê a regra de pontuação da página inteira, sem filtro de cargo. O mesmo vale para `_quadro_de_eixos` e `_pesos_por_prova`.
- Em `_identificar`, `docs.primeiro(_CADASTRO_DE_RESERVA)` roda sem escopo, ao contrário do `_TETO` logo acima.
- Em `_por_tipo`, as buscas de `_CERTO_OU_ERRADO` e `_MULTIPLA_ESCOLHA` rodam sem escopo; só `_DISCURSIVAS` usa o escopo.
- `_extrair_cronograma(config, docs)` não tem escopo, e a decisão (cargo ou concurso inteiro) não está registrada em `docs/modelo.md`.

### Comportamento esperado

- `_extrair_pesos` recebe o escopo; a soma dos eixos e a regra de pontuação só valem quando `escopo.aplica` aceita o achado.
- `extrair_fator_correcao` continua em `analytics/correcao.py`, sem importar `regras_edital`. O filtro fica em `regras_edital`, sobre a posição do trecho que a função devolve.
- O cadastro de reserva e o tipo de questão respeitam o escopo do cargo.
- Para o cronograma, a decisão fica registrada em `docs/modelo.md`. O cronograma costuma ser comum a todos os cargos, então a opção provável é o concurso inteiro.

### Critérios de aceite

- [ ] Teste: num edital sintético com dois cargos e pesos diferentes, cada cargo lê só o seu.
- [ ] Teste: o cadastro de reserva e o tipo de questão de outro cargo não vazam.
- [ ] Os nove `edital_estruturado.json` reais ficam iguais (ou a diferença é apresentada como proposta).
- [ ] `docs/modelo.md` atualizado; `uv run pytest` e `ruff` verdes.

### Riscos

- Alto impacto nos dados reais: filtrar por escopo pode fazer um peso hoje encontrado deixar de ser encontrado e cair no padrão, com aviso. Comparar os nove `edital_estruturado.json` antes e depois.
- Paridade: a nota usa o peso do `correcao.json` (peso realizado vence), então a nota não deve mudar; o que pode mudar é o CSV de discrepâncias (o `warn` de peso do edital × realizado) e o catálogo.

---

<a id="issue-14"></a>

## 14: Precedência completa com a configuração

### O que falta

A história 33 da spec da fase 3 pede a precedência retificação, edital, configuração e padrão em todos os campos que o `concurso.yaml` declara. Hoje a configuração entra só no corte do conjunto (`nota_corte`), no formato, nas alternativas e na penalidade. Em `src/concursos/analytics/regras_edital.py`:

- `_extrair_distribuicao`: sem `_TOTAL_DE_QUESTOES` no edital e sem os dois blocos declarados, `campo_total` fica vazio e vai direto para `_aviso_de_default(..., 'número de questões não encontrado no edital')`, sem tentar `config.total_itens`.
- `_extrair_pesos`: sem quadro de eixos, regra de pontuação ou pesos por prova, devolve `Pesos(soma_dos_eixos=...)` com `_aviso_de_default(..., 'pesos não encontrados no edital')`, sem tentar os `pesos` do `correcao` (ou das variantes) do `concurso.yaml`.
- Não há aviso quando edital e configuração declaram total ou pesos diferentes. Esse aviso já existe para a nota de corte.

### Comportamento esperado

- **Distribuição:** sem o total no edital, usar `total_itens` do `concurso.yaml` com `FonteRegra.CONFIG` e `CONFIANCA_CONFIG`, antes do aviso de padrão.
- **Pesos:** sem pesos no edital, usar os `pesos` do `correcao` (ou das variantes) com `FonteRegra.CONFIG`. O tipo é `UNIFORME` quando todos os pesos são iguais e `POR_FAIXA_DE_ITENS` quando não são.
- **Divergência:** quando edital e configuração diferem, o edital vence e sai um aviso, como na nota de corte.
- `_aviso_de_default` só aparece quando nem o edital nem a configuração têm o valor.
- A camada `config` entra depois do edital e da retificação, e o que ela decidiu aparece em "O que o app decidiu sozinho" no `index.html` (seção "Fallbacks" do `AGENTS.md`).

### Critérios de aceite

- [ ] Teste: sem total no edital, a distribuição usa o `total_itens` do config com fonte `config` e sem aviso de default.
- [ ] Teste: sem pesos no edital, os pesos vêm do config com fonte `config`.
- [ ] Teste: edital e config divergentes geram aviso, e o edital vence.
- [ ] Os nove `edital_estruturado.json` reais conferidos; mudança de valor vira proposta (regra 11).
- [ ] `docs/modelo.md` atualizado; `uv run pytest` e `ruff` verdes.

### Riscos

- Interação com o `edital_a_confirmar.yaml` (fase 4), que também grava valores com fonte `config`: conferir que um campo preenchido pelo `concurso.yaml` não é mais listado como "a confirmar" e que a ordem das camadas continua a de `docs/modelo.md`.
- Interação com a camada LLM: ela só preenche campos que cairiam no perfil ou no padrão. Um campo que passa a vir do `concurso.yaml` deixa de ir para o LLM.
- Depende da 13, que muda a assinatura de `_extrair_pesos`.

---

## Conferências à mão

Nada a programar nestes itens.

<a id="verificacao-fase2"></a>

### Fase 2: trecho de origem conferido à mão contra o PDF

"Sempre que a fonte é o edital, o trecho de origem está preenchido e confere com o PDF" foi verificado automaticamente: em três concursos reais, o trecho foi encontrado na página citada pelo texto extraído com pypdfium2. Falta a conferência visual: abrir cada edital na página do `pagina_origem` do `correcao.json` e ver o trecho.

<a id="verificacao-fase6"></a>

### Fases 5 e 6: checklist de máquina limpa e primeira release com atualizador

O `release.yml` passa nos três sistemas: em cada um, o executável roda o `--smoke` (Tesseract embutido com `por`, OCR numa imagem gerada, partida medida, GUI em `127.0.0.1`), o `doctor` e a análise do projeto sintético sem Python nem Tesseract no `PATH`. O AppImage da fase 6 também passou, num build local, em `debian:12` e `ubuntu:22.04` limpos, e a GUI congelada foi percorrida com `HOME` vazio (onboarding, exemplo, modo escuro, Sobre).

Falta o que o runner não reproduz, com o roteiro em [release.md](release.md):

- **Windows:** o checklist no Windows Sandbox (SmartScreen, menu Iniciar, janela nativa, partida abaixo de 3 s, onboarding com o exemplo) e, na VM Win10 sem WebView2, o bootstrapper e o aviso de navegador.
- **Linux:** abrir pelo menu de um desktop real depois de integrar o AppImage.
- **Atualizador:** a primeira release com o manifesto assinado (a v0.6.0b1) precisa do environment `release` com o secret `CHAVE_ATUALIZACAO`; o teste de atualização de ponta a ponta (workflow `atualizacao`) só roda a partir da release seguinte.
- **macOS arm64:** abrir o DMG baixado num Mac, com o "Abrir Mesmo Assim" do Gatekeeper, e ver a janela nativa. O macOS ficou fora da fase 6, mas o `release.yml` ainda gera o DMG.
