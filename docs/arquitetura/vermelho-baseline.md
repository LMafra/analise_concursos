# Baseline vermelho — complexidade e acoplamento

| Campo | Valor |
|---|---|
| Commit | `7016502` |
| Data | 2026-11-19 |
| Artefatos | [`metricas-7016502/`](metricas-7016502/) |
| Cobertura | **90.8867%** (17353 / 19093); 2 módulos &lt;60% |
| Funções CC &gt; 15 | **49** (48 blocos top-level + 1 closure `consulta`) |
| Classe E/F | 1 (`explicar_erros_tec` CC 45 F) |
| Ciclos AST mútuos (domínio) | 2 |
| `pipeline` eferente | 35 módulos `concursos.*` |

Fonte: `radon cc/mi/raw`, AST de imports (corpo de função incluso), `vulture --min-confidence 80`, `pytest --cov`. `pydeps --show-cycles` travou neste host; ver `metricas-7016502/pydeps-cycles.txt`.

O mapa [`docs/arquitetura-plataforma.md`](../arquitetura-plataforma.md) (commit `d082853`) listava 48 funções e omitia `consulta`. Não usar aquela lista.

## Top 30 por CC

| CC | Classe | Função | Arquivo:linha |
|---|---|---|---|
| 45 | F | `explicar_erros_tec` | `aplicacao/tec_estudo.py:124` |
| 26 | D | `importar_pratica` | `pratica_tec.py:705` |
| 26 | D | `fundir` | `pratica_tec.py:269` |
| 25 | D | `sugerir_termos` | `analytics/dicionario_topicos.py:506` |
| 25 | D | `_cortes_do_texto` | `analytics/regras_edital.py:1194` |
| 24 | D | `recomendar` | `biblioteca.py:348` |
| 24 | D | `perguntar` | `aplicacao/estudo.py:662` |
| 22 | D | `sincronizar_candidato` | `integracoes/sincronizacao_notebook.py:448` |
| 22 | D | `gerar_relatorio_html` | `relatorio_html.py:230` |
| 22 | D | `_sugerir` | `topicos.py:177` |
| 22 | D | `_secoes_do_cargo` | `edital.py:248` |
| 22 | D | `_montar` | `cadastro.py:181` |
| 21 | D | `ler_respostas_csv` | `respostas.py:44` |
| 21 | D | `avaliar` | `status.py:41` |
| 20 | C | `perguntar` | `onboarding.py:72` |
| 20 | C | `listar_erros` | `aplicacao/tec_repeticao.py:62` |
| 20 | C | `_questao` | `pratica_tec.py:976` |
| 19 | C | `resumir_pratica` | `analytics/tec_estatisticas.py:29` |
| 19 | C | `acoes_sugeridas` | `analytics/painel.py:402` |
| 19 | C | `_resolver_assuntos` | `pratica_tec.py:483` |
| 19 | C | `_perguntar_llm` | `onboarding.py:201` |
| 19 | C | `_classificar_topicos` | `pipeline.py:432` |
| 18 | C | `verificar_completude` | `pratica_tec.py:179` |
| 18 | C | `verificar` | `atualizacao.py:52` |
| 18 | C | `peculiaridades_do_edital` | `analytics/insights.py:283` |
| 18 | C | `converter` | `planilha_tec.py:254` |
| 18 | C | `consulta` | `aplicacao/tec_pci.py:115` (closure) |
| 17 | C | `importar_simulado` | `aplicacao/integracoes.py:661` |
| 17 | C | `gerar_catalogo` | `analytics/catalogo_edital.py:26` |
| 17 | C | `expansao_para` | `analytics/dicionario_topicos.py:238` |

## Lista completa CC &gt; 15 (por módulo)

Coluna «teste»: nome da função aparece em `tests/` (`sim` / `parcial` / `não`).

### `aplicacao/tec_estudo.py` — aplicacao

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 45 | F | `explicar_erros_tec` | 124 | sim |

### `pratica_tec.py` — raiz

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 26 | D | `importar_pratica` | 705 | sim |
| 26 | D | `fundir` | 269 | não |
| 20 | C | `_questao` | 976 | parcial |
| 19 | C | `_resolver_assuntos` | 483 | não |
| 18 | C | `verificar_completude` | 179 | sim |
| 16 | C | `ler_entrada` | 341 | sim |
| 16 | C | `_resolver_cadernos` | 551 | não |

### `analytics/dicionario_topicos.py` — analytics

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 25 | D | `sugerir_termos` | 506 | sim |
| 17 | C | `expansao_para` | 238 | sim |

### `analytics/regras_edital.py` — analytics

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 25 | D | `_cortes_do_texto` | 1194 | não |
| 17 | C | `_extrair_cortes` | 1240 | não |
| 16 | C | `_casar_cargo` | 548 | não |

### `biblioteca.py` — raiz

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 24 | D | `recomendar` | 348 | sim |
| 16 | C | `ler_mapa` | 68 | sim |

### `aplicacao/estudo.py` — aplicacao

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 24 | D | `perguntar` | 662 | sim |

### `integracoes/sincronizacao_notebook.py` — integracoes

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 22 | D | `sincronizar_candidato` | 448 | sim |

### `relatorio_html.py` — raiz

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 22 | D | `gerar_relatorio_html` | 230 | sim |
| 17 | C | `_provas` | 382 | sim |
| 16 | C | `_decisoes` | 864 | não |

### `topicos.py` — raiz

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 22 | D | `_sugerir` | 177 | parcial |

### `edital.py` — raiz

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 22 | D | `_secoes_do_cargo` | 248 | não |
| 16 | C | `_topicos` | 401 | parcial |

### `cadastro.py` — raiz

| CC | Classe | Função | Linha | Teste |
|---|---|---|---|---|
| 22 | D | `_montar` | 181 | parcial |
| 17 | C | `_edital` | 311 | sim |
| 16 | C | `_escolher_caderno` | 283 | não |

### Demais (CC 16–21)

| CC | Classe | Função | Arquivo:linha | Camada | Teste |
|---|---|---|---|---|---|
| 21 | D | `ler_respostas_csv` | `respostas.py:44` | raiz | sim |
| 21 | D | `avaliar` | `status.py:41` | raiz | sim |
| 20 | C | `perguntar` | `onboarding.py:72` | raiz | sim |
| 20 | C | `listar_erros` | `aplicacao/tec_repeticao.py:62` | aplicacao | sim |
| 19 | C | `resumir_pratica` | `analytics/tec_estatisticas.py:29` | analytics | não |
| 19 | C | `acoes_sugeridas` | `analytics/painel.py:402` | analytics | sim |
| 19 | C | `_perguntar_llm` | `onboarding.py:201` | raiz | não |
| 19 | C | `_classificar_topicos` | `pipeline.py:432` | pipeline | não |
| 18 | C | `verificar` | `atualizacao.py:52` | raiz | sim |
| 18 | C | `peculiaridades_do_edital` | `analytics/insights.py:283` | analytics | sim |
| 18 | C | `converter` | `planilha_tec.py:254` | raiz | sim |
| 18 | C | `consulta` | `aplicacao/tec_pci.py:115` | aplicacao | (closure) |
| 17 | C | `importar_simulado` | `aplicacao/integracoes.py:661` | aplicacao | sim |
| 17 | C | `gerar_catalogo` | `analytics/catalogo_edital.py:26` | analytics | sim |
| 17 | C | `aplicar_candidato` | `candidatos.py:60` | raiz | não |
| 17 | C | `analisar_candidato` | `aplicacao/analise.py:83` | aplicacao | não |
| 17 | C | `_montar` | `concurso_config.py:345` | raiz | parcial |
| 16 | C | `sincronizar` | `aplicacao/integracoes.py:143` | aplicacao | sim |
| 16 | C | `nome_do_concurso` | `analytics/nome_concurso.py:95` | analytics | sim |
| 16 | C | `ler_configuracao` | `integracoes/pci_mcp.py:73` | integracoes | sim |
| 16 | C | `filtros_pci` | `aplicacao/integracoes.py:354` | aplicacao | sim |
| 16 | C | `cadastrar_envio` | `aplicacao/cadastro.py:156` | aplicacao | sim |
| 16 | C | `_do_interesse` | `integracoes/radar_pci.py:107` | integracoes | não |

## MI &lt; 20 — os 4 com 0.00

| MI | Arquivo |
|---|---|
| 0.00 | `analytics/regras_edital.py` |
| 0.00 | `concurso_config.py` |
| 0.00 | `pratica_tec.py` |
| 0.00 | `relatorio_html.py` |

Meta do programa: MI ≥ 30 nestes quatro. Demais MI &lt; 20 fora do escopo deste programa (17 arquivos &lt; 20 no total).

## Ciclos confirmados (AST)

### `topicos` ↔ `dicionario_topicos`

- `dicionario_topicos` → `topicos`: `ARQUIVO_REVISAO`, `NAO_MAPEADO`, `SCORE_BAIXO`, `chave_de_palavras`, `palavras_chave`, `sugerir_topicos` (linha 22).
- `topicos` → `dicionario_topicos`: `Dicionario`, `Expansao` (`TYPE_CHECKING`, linha 16); `expansao_para` (dentro de `sugerir_topicos`, linha 167).

### `pratica_tec` ↔ `tec_estatisticas`

- `tec_estatisticas` → `pratica_tec`: `ARQUIVO_RESPOSTAS`, `ARQUIVO_TENTATIVAS`, `PASTA_PRATICA`, `RESULTADO_ERRO` (linha 10).
- `pratica_tec` → `tec_estatisticas`: `markdown_resumo` (dentro de `importar_pratica`, linha 775).

Outros 2-ciclos AST de pacote (`cli.comandos` ↔ `cli`, `perfis.ocr` ↔ `perfis`) são import de package/`__init__`; fora do escopo.

## Mapa de eferência do `pipeline` (35)

Imports `concursos.*` em `pipeline.py` (topo + `TYPE_CHECKING`).

### Essencial (18)

`folha`, `gabarito`, `correcao`, `analytics.correcao`, `edital`, `topicos`, `prova`, `respostas`, `candidatos`, `concurso_config`, `caderno`, `perfis`, `texto`, `modelo`, `configuracao`, `config.contexto`, `erros`, `manifesto`

### Conveniência (17)

`agregacao`, `consolidado`, `status`, `analytics.regras_edital`, `analytics.taxonomia`, `analytics.validacao_edital`, `analytics.catalogo_edital`, `analytics.dicionario_topicos` (`TYPE_CHECKING`), `edital_llm`, `edital_a_confirmar`, `llm`, `atualizacao`, `resultado_oficial`, `graficos`, `relatorio`, `doctor`, `linguagem`

Quem importa `pipeline` fora de teste: `aplicacao/analise.py`, `aplicacao/simulados.py`, `cli/legado.py`, `relatorio_html.py` (`ARQUIVO_RESPOSTAS`).

## Cobertura

| Métrica | Valor |
|---|---|
| Global | 90.8867% (17353 / 19093) |
| Módulos &lt; 60% | 2 — `gui/componentes/seletor_pasta.py` (20.9%), `gui/componentes/toasts.py` (38.9%) |
| Piso do gate | **90.8867%** (max com o 90.88% do mapa) |

## Vulture @80

Um candidato: `rastro` em `integracoes/pci_mcp.py:190` (100%).

## Ordem de ataque (aprovada no plano)

1. Ciclo `topicos` / `dicionario_topicos`
2. Ciclo `pratica_tec` / `tec_estatisticas`
3. CC por arquivo (lista acima)
4. Fachada `pipeline`
5. Gate CI + `limiares.toml`
6. Mapa + ADRs
