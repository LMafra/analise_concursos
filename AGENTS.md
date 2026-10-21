# AGENTS.md

Pipeline local de correção e análise de provas de concurso. Fase 1: a CLI `concursos` (`src/concursos/`), que gera `analises/<concurso>/`. Fase 2: a análise evolutiva entre concursos (`src/concursos/analytics/` e `notebooks/`).

- Specs: `docs/spec.md` (fase 1) e `docs/spec-fase2.md` (fase 2). Leia a da fase antes de mudar comportamento.
- Modelo de domínio, contratos de arquivo e fórmulas: `docs/modelo.md`. É a fonte única dos campos do `concurso.yaml`, do `correcao.json` e do schema do parquet; atualize-o na mesma mudança que o código.

## Dados pessoais

`provas/` e `analises/` têm CPF, nome e notas e ficam fora do git, assim como os `notebooks/*.ipynb` gerados.

## Onde mora cada lógica

| Assunto | Módulo |
|---|---|
| Regra de correção: extração do edital, precedência, pontuação por item, nota | `analytics/correcao.py` |
| Parquet por questão, cache, `validar_schema`, ordem cronológica | `analytics/consolidado.py` |
| Disciplina canônica e bloco | `analytics/taxonomia.py` e `taxonomia.yaml` |
| Métricas de evolução: ranking, z-score, tendência, correlação, tópicos, meta | `analytics/evolucao.py` |
| Respostas em texto e `relatorio_evolucao.md` | `analytics/insights.py` |
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

## Código

- Nomes, docstrings, comentários e docs em português. O ruff não quebra strings nem comentários longos, e o E501 está desligado: quebre à mão o que passar do `line-length`.
- Comentários e docstrings só registram restrições que o código não mostra.
- Preserve o final de linha de cada arquivo: boa parte da fase 1 (e `docs/modelo.md`) usa CRLF.
- TDD: o teste que falha vem primeiro, em `tests/` (os da fase 2 são `test_analytics_<módulo>.py`), com dados sintéticos; `tests/consolidado_sintetico.py` monta consolidados mínimos.
