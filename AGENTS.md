# AGENTS.md

Pipeline local de correção e análise de provas de concurso. Fase 1: a CLI `concursos` (`src/concursos/`), que gera `analises/<concurso>/`. Fase 2: a análise evolutiva entre concursos (`src/concursos/analytics/` e `notebooks/`). Fase 3: o edital como fonte de verdade (regras, validação e catálogo de descobertas) e a aplicação delas em corte e peso.

- Specs: `docs/spec.md` (fase 1), `docs/spec-fase2.md` (fase 2), `docs/spec-fase3.md` (fase 3) e `docs/spec-fase4.md` (fase 4: um comando, multi-candidato, perfis e fallbacks). Leia a da fase antes de mudar comportamento.
- Paridade: antes de um refactor que toca código das fases 1 a 3, rode `concursos analisar --forcar` e `scripts/paridade.py retrato`; depois, `comparar` não pode mostrar diferença.
- Modelo de domínio, contratos de arquivo e fórmulas: `docs/modelo.md`. É a fonte única dos campos do `concurso.yaml`, do `correcao.json`, do `edital_estruturado.json`, do template do `catalogo_edital.md` e do schema do parquet; atualize-o na mesma mudança que o código.

## Dados pessoais

`provas/` e `analises/` têm CPF, nome e notas e ficam fora do git, assim como os `notebooks/*.ipynb` gerados.

## Onde mora cada lógica

| Assunto | Módulo |
|---|---|
| Regra de correção: extração do edital, precedência, pontuação por item, nota | `analytics/correcao.py` |
| Parquet por questão, cache, `validar_schema`, ordem cronológica, regras gravadas por concurso | `analytics/consolidado.py` |
| Disciplina canônica e bloco | `analytics/taxonomia.py` e `taxonomia.yaml` |
| Regras do edital: identificação, cargo, pesos, distribuição, cortes, cronograma, desempate, metadados | `analytics/regras_edital.py` |
| Registro versionado de candidatos à descoberta (`VERSAO_CANDIDATOS`) | `analytics/candidatos_edital.py` |
| Discrepâncias edital × prova × gabarito (`discrepancias_edital.csv`) | `analytics/validacao_edital.py` |
| Catálogo de descobertas (`catalogo_edital.md`) | `analytics/catalogo_edital.py` |
| Métricas de evolução: ranking, z-score, tendência, correlação, tópicos, meta, nota ponderada, gap para o corte, simulação | `analytics/evolucao.py` |
| Respostas em texto, `relatorio_evolucao.md`, desempate e peculiaridades do edital | `analytics/insights.py` |
| Gráficos (plotly no notebook, PNG com matplotlib) e resumo de tabelas | `analytics/visualizacao.py` |

## Notebooks

- Cada notebook é um script jupytext no formato percent, `notebooks/NN_*.py`; rode com `scripts/rodar_notebooks.sh [arquivos]`.
- Uma célula só chama funções do pacote (`concursos.analytics` e `carregar_configuracao_global`) e exibe o resultado. Parsing, OCR, regra de negócio e cálculo de correção moram nos módulos acima, com teste; um número novo que o notebook precise vira antes uma função testada.
- Tabelas longas passam por `resumir` (em `visualizacao`). A conclusão em prosa cita os números que as células imprimem; rode o notebook de novo ao mudar uma função da qual ele depende.

## Convenções de análise

- Métrica padrão: `ajustada` (ao acaso; erro vale −1/(k−1)). A evolução se lê pelo z-score por disciplina, porque a média dos z de um concurso fica perto de 0 por construção.
- Todo percentual vem com o n. n < `N_MINIMO_TOPICO` (5) é amostra insuficiente, e uma tendência exige `MINIMO_PONTOS_TENDENCIA` (3) ordens distintas. Use as constantes nos limiares e nos textos.
- Gerais e específicos ficam separados (`bloco`) nas séries por disciplina.
- O limiar de tópico fraco vem do `config.yaml` (`limiar_topico_baixo`).

## Edital como fonte de verdade

- **Rastreável:** todo valor com fonte `edital`, `retificacao` ou `descoberta` traz trecho, documento e página, para conferir no PDF. A busca respeita o escopo do cargo (`_Escopo`), e a retificação mais recente vence campo a campo.
- **Peso realizado vence:** a nota usa o peso do `correcao.json`. O peso do edital é expectativa, e a divergência vira `warn` no CSV de discrepâncias. `correcao.py` não importa `regras_edital`; o `correcao.json`, os CSVs das fases 1 e 2 e o parquet mantêm schema e valores.
- **Corte é múltiplo:** o gap é calculado contra cada corte aplicável, na unidade dele (pontos ou acertos), e "atingido" exige todos. O corte da discursiva fica fora do "atingido".
- **Data só do edital ou da configuração:** sem data em nenhuma das duas fontes, o concurso fica sem data, com aviso.
- **Descoberta tem uso:** cada candidato do registro declara o uso no projeto, o impacto e o status. Sem uso que mude análise, decisão ou gráfico, ele vai para os descartados com o motivo. Mudar um candidato sobe `VERSAO_CANDIDATOS`.
- **Descoberta propõe:** quando ela afeta código de fase anterior (OCR da folha, `correcao.py`), registre-a como `proposto`, com o diff estimado em `proposta`, e peça confirmação. O catálogo lista essas propostas.
- **Simulação é estimativa:** os textos de cenário se apresentam como estimativa e não estimam colocação.

## Código

- Nomes, docstrings, comentários e docs em português. O ruff não quebra strings nem comentários longos, e o E501 está desligado: quebre à mão o que passar do `line-length`.
- Comentários e docstrings só registram restrições que o código não mostra.
- Preserve o final de linha de cada arquivo: boa parte da fase 1 (e `docs/modelo.md`) usa CRLF.
- TDD: o teste que falha vem primeiro, em `tests/` (os das fases 2 e 3 são `test_analytics_<módulo>.py`), com dados sintéticos; `tests/consolidado_sintetico.py` monta consolidados mínimos. Para regras do edital, use trechos curtos de texto real como fixture.
