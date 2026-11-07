# AGENTS.md

Ferramenta local de correção e análise de provas de concurso, com um comando só: `concurso-analise` (`src/concursos/cli/`), que gera `analises/<candidato>/<concurso>/`. Fase 1: correção por concurso. Fase 2: a análise evolutiva entre concursos (`src/concursos/analytics/` e `notebooks/`). Fase 3: o edital como fonte de verdade (regras, validação e catálogo de descobertas). Fase 4: um comando, multi-candidato, perfis de banca e de OCR, fallbacks, onboarding, `doctor`, LLM opcional e distribuição. Fase 5: a GUI em NiceGUI (`concurso-analise gui`, `src/concursos/gui/`) sobre a camada de aplicação (`src/concursos/aplicacao/`), o executável por sistema (`empacotamento/`) e o `tec-erros/` no mesmo repositório. Fase 6 (Windows e Linux): assinatura pela SignPath, WebView2 no instalador, AppImage verificado, atualizador por manifesto assinado e tokens de design com onboarding na GUI. Fase 7: estudar com o open-notebook gerenciado pelo app (pacote de estudo, biblioteca de livros com página), dicionário de temas, telas de conferência, nome do concurso pelo edital e fluxos assistidos do PCI e do TEC.

- Specs: `docs/spec.md` (fase 1), `docs/spec-fase2.md` (fase 2), `docs/spec-fase3.md` (fase 3), `docs/spec-fase4.md` (fase 4), `docs/spec-pci-mcp.md` (PCI Concursos), `docs/spec-fase5.md` (fase 5, com as decisões em `docs/decisoes-fase5.md`) e `docs/spec-fase6.md` (fase 6, com as decisões em `docs/decisoes-fase6.md`) e `docs/spec-fase7.md` (fase 7, com as decisões em `docs/decisoes-fase7.md`). Leia a da fase antes de mudar comportamento.
- Paridade: antes de um refactor que toca código das fases 1 a 3, rode `concurso-analise --force` e `scripts/paridade.py retrato analises/<candidato> <arquivo>`; depois, `comparar` não pode mostrar diferença.
- Ponta a ponta: `scripts/smoke.py` roda onboarding, análise e idempotência num projeto temporário; rode-o pelo `uvx --from "$PWD"` ao mexer em dependências, CLI ou empacotamento.
- Modelo de domínio, contratos de arquivo e fórmulas: `docs/modelo.md`. É a fonte única dos campos do `concurso.yaml`, do `candidato.yaml`, do `config.toml`, dos perfis, do `correcao.json`, do `edital_estruturado.json`, do template do `catalogo_edital.md` e do schema do parquet; atualize-o na mesma mudança que o código.

## Dados pessoais

`provas/`, `analises/` e `.concurso/` têm CPF, nome e notas e ficam fora do git e da imagem Docker, assim como os `notebooks/*.ipynb` gerados. `test_sem_dado_pessoal_no_pacote` procura no pacote nomes, slugs, inscrições, CPF e caminhos de usuário; fixtures usam nomes fictícios.

Nenhuma chamada de rede sem opt-in: o LLM exige provedor e consentimento na configuração global e só recebe texto do edital; o open-notebook exige `enabled` e `consentimento` em `[open_notebook]` e recebe o candidato como pseudônimo, salvo `incluir_nome`; o PCI Concursos exige `enabled` em `[pci_mcp]` e só recebe termos de busca (cargo, UF, cidade, região, termo); o atualizador só consulta o GitHub no clique de "Verificar atualizações", no `upgrade` ou com `[atualizacao] verificar_ao_abrir` (no máximo uma vez por dia), e não envia dado nenhum. `--offline` e `--dry-run` desligam os quatro (no PCI, `--offline` fica no cache). O PDF de prova do PCI nunca é baixado pelo app (captcha e `robots.txt`): ele lê só a página HTML e nunca chama `/provas/link`; o download é do usuário, no navegador. A chave de API e a senha do open-notebook nunca vão para TOML.

A instância gerenciada do open-notebook (fase 7) roda no próprio computador e não pede consentimento: livros e análises vão para ela sem tela, com o candidato como pseudônimo. Os processos dela (SurrealDB, API, worker, embeddings) escutam só em `127.0.0.1`, em portas aleatórias, com senha e token por sessão, e o app nunca chama `/api/config`. A IA só recebe trechos de livros com `[llm] consentimento_livros`, separado do consentimento do edital, e a chave vai por variável de ambiente, nunca para o banco do open-notebook. O pacote de estudo segue as regras do atualizador: baixado só com consentimento, conferido pela assinatura Ed25519 e atualizado só depois de uma confirmação. Embeddings servem só para buscar nos livros, nunca para classificar tópicos.

## Onde mora cada lógica

| Assunto | Módulo |
|---|---|
| CLI: comando padrão, subcomandos, flags globais, códigos de saída e erro em duas linhas | `cli/comandos.py`, `cli/erros.py` |
| `ErroDoUsuario` e `ErroDoAmbiente` (causa, dica, código) | `erros.py` |
| Orquestração usada pela CLI e pela GUI: `Opcoes` (saída, interação, progresso), escolha de candidato, cadeia da análise, cadastro, onboarding, prática, recomendações, radar, open-notebook, PCI e preferências | `aplicacao/` |
| GUI: `ui.run` em `127.0.0.1`, estado do projeto, `InteracaoGui`, progresso e log, páginas e componentes | `gui/` |
| Tokens de design (cor, tipografia, espaço, elevação) e `aplicar_tema` | `gui/tema.py` |
| Janela nativa ou navegador (WebView2, `--browser`, Linux) | `janela.py` |
| Atualizador: manifesto, assinatura Ed25519, download verificado, aplicação por sistema | `atualizador.py`, `aplicacao/atualizador.py` |
| Concurso de exemplo do onboarding (`~/.concurso/exemplo/`) | `exemplo.py`, `aplicacao/exemplo.py` |
| Executável: launcher, spec do PyInstaller, hook, Tesseract embutido, instaladores | `empacotamento/` (fora do pacote) |
| Captura do TEC (extensão, userscript, `caderno.html`) e contrato v1 | `tec-erros/` (JavaScript, fora do pacote), fixtures em `tests/contrato_tec/` |
| Comando obsoleto `concursos` | `cli/legado.py` |
| Pastas de uma execução (global, projeto, provas, análises) e `config.toml` | `config/contexto.py`, `configuracao.py` |
| `concurso.yaml`: leitura, validação, gravação e `arquivos_referenciados` | `concurso_config.py` |
| Texto: extração do PDF, `normalizar`, `abreviar`, `juntar_linhas` | `texto.py` |
| Papel e banca de cada arquivo, e cadastro (`add`, txt de papel ambíguo) | `deteccao.py`, `cadastro.py` |
| Onboarding (wizard de 6 perguntas e `init`) | `onboarding.py` |
| Diagnóstico do ambiente com o comando de correção por sistema | `doctor.py` |
| Migração das fases 1 a 3, com backup verificado | `migracao.py` |
| Candidatos: subpasta, `candidato.yaml`, perfil global, revisão da leitura (`--reuse-csv`) | `candidatos.py` |
| Perfis de banca e de OCR, entry points `concurso.banca` e `concurso.ocr` | `perfis/` (YAML em `perfis/bancas/` e `perfis/folhas/`) |
| Leitura da folha: perfil, detecção automática, amostra para calibração | `folha.py` |
| Calibração da folha pelas 5 respostas digitadas | `calibracao.py` |
| Campos que nenhuma camada do edital preencheu (`edital_a_confirmar.yaml`) | `edital_a_confirmar.py` |
| Cliente LLM (OpenAI-compatível e Anthropic), chave e consentimento | `llm.py` |
| Camada LLM das regras do edital, com citação literal | `edital_llm.py` |
| Cliente do open-notebook (urllib, multipart, Bearer) e a seção `[open_notebook]` | `integracoes/open_notebook.py` |
| O que vai para o open-notebook, nota de resumo, pseudônimos, vínculos de livros e normas, notebooks `Legislação` e `Caderno de erros`, e estado `.concurso/open_notebook.json` | `integracoes/sincronizacao_notebook.py` |
| Cliente do PCI Concursos (`[pci_mcp]`, transporte MCP, erros, `ConcursoPci`, `ProvaAnteriorPci`, limite por execução) | `integracoes/pci_mcp.py` |
| Cache das respostas do PCI (`.concurso/cache/pci_mcp.json`, TTL) | `integracoes/cache_pci.py` |
| Sessão de consultas ao PCI, tabela do `discover` e interesses (`.concurso/interesses_pci.yaml`) | `integracoes/sincronizacao_pci.py` |
| Radar de prazos (`radar_editais.md` e `.json`) | `integracoes/radar_pci.py` |
| Página da prova anterior no PCI (nomes dos arquivos, só HTML) e download assistido pela pasta de downloads | `integracoes/pagina_pci.py`, `integracoes/download_assistido.py` |
| Prova anterior como simulado (bloco `simulado:`, banca pela organizadora, edital emprestado, `provas_anteriores.md`) | `integracoes/simulado_pci.py` |
| Prática no TEC (`[pratica]`): exportações do tec-erros, mesclagem, matéria e assunto → disciplina e tópico, `.concurso/pratica_tec.yaml` e `analises/<candidato>/pratica/` | `pratica_tec.py` |
| Fontes de estudo: `biblioteca.yaml`, catálogo do `books`, busca nos notebooks de biblioteca e `recomendacoes_estudo.md` | `biblioteca.py` |
| Citações de normas nos tópicos e leitura do clone do `ctresb/leis` (`[legislacao]`) | `legislacao.py` |
| Relatório HTML por candidato e abertura no navegador | `relatorio_html.py` |
| Exportação do consolidado (`export`) | `exportacao.py` |
| Gravação que preserva o `mtime` quando o conteúdo não muda; leitura de PDF/txt guardada em memória pelo hash do conteúdo (`lido_uma_vez`) | `arquivos.py` |
| Regra de correção: extração do edital, precedência, pontuação por item, nota | `analytics/correcao.py` |
| Parquet por questão, cache, `validar_schema`, ordem cronológica, regras gravadas por concurso | `analytics/consolidado.py` |
| Disciplina canônica e bloco | `analytics/taxonomia.py` e `.concurso/taxonomia.yaml` |
| Regras do edital: identificação, cargo, pesos, distribuição, cortes, cronograma, desempate, metadados, fonte e confiança | `analytics/regras_edital.py` |
| Registro versionado de pistas do edital (`VERSAO_CANDIDATOS`) | `analytics/pistas_edital.py` |
| Nome mostrado do concurso (título, subtítulo, fonte, "a confirmar"), rótulo dos notebooks e pasta automática do cadastro | `analytics/nome_concurso.py`, `aplicacao/nomes.py`, `aplicacao/cadastro.py` |
| Discrepâncias edital × prova × gabarito (`discrepancias_edital.csv`) | `analytics/validacao_edital.py` |
| Catálogo de descobertas (`catalogo_edital.md`) | `analytics/catalogo_edital.py` |
| Métricas de evolução: ranking, z-score, tendência, correlação, tópicos, meta, nota ponderada, gap para o corte, simulação | `analytics/evolucao.py` |
| Respostas em texto, `relatorio_evolucao.md`, desempate e peculiaridades do edital | `analytics/insights.py` |
| Gráficos (plotly no notebook, PNG com matplotlib) e resumo de tabelas | `analytics/visualizacao.py` |
| Pacote de estudo: manifesto `estudo.json` (formato, assinatura, compatibilidade) | `estudo/manifesto.py` |
| Pacote de estudo: escolha da release, download verificado, espaço em disco, instalação, backup e volta ao anterior | `estudo/instalacao.py` |
| Processos do open-notebook gerenciado (SurrealDB, API, worker, embeddings): portas, senha, trava, saúde, parada por ociosidade | `estudo/supervisor.py` |
| Montagem do pacote de estudo e servidor de embeddings (fora do pacote) | `empacotamento/estudo/` |
| Livros: validação do arquivo, leitura por página (com OCR), índice FTS5 com radicais, fila em segundo plano e envio ao open-notebook | `livros/` |
| Orquestração de Estudar (preparar, enviar, listar, remover, perguntar) | `aplicacao/estudo.py` |
| Dicionário de temas (`.concurso/taxonomia_topicos.yaml`), expansão e métrica de ganho | `analytics/dicionario_topicos.py`, `aplicacao/dicionario.py` |
| Telas de conferência (tópicos, edital a confirmar, taxonomia) e reanálise dos afetados | `aplicacao/conferencia.py` |
| Nome do concurso (sigla, ano, cargo) pela cadeia de fontes | `analytics/regras_edital.py`, `nomes.py` |
| Municípios do IBGE embutidos (regenerados por `scripts/atualizar_municipios.py`), região de cada UF e datas DD/MM/AAAA | `municipios.py`, `dados/municipios_ibge.json`, `datas.py` |
| Planilha do TEC (CSV/XLSX) para o contrato v1 | `planilha_tec.py` |

## Perfis

- O que muda de uma banca para outra mora num perfil YAML, não em `if banca == ...`. Um ramo por banca no código é um campo de perfil que falta.
- Perfil de banca: `id`, `marcas` (palavras inteiras no texto normalizado), `formato`, `alternativas`, `penalidade`, leitores (`cebraspe`, `fgv`, `lista` ou `modulo:funcao`), `segmentacao`, `chaves_prova`, `templates_folha`. Perfil de OCR: `id`, `alternativas`, `itens_por_coluna`, `vazio`, `cheio`, `limiar_marcada`, `largura`. Os campos e a validação estão em `docs/modelo.md`.
- O perfil preenche só o que o edital e o `concurso.yaml` não trazem, com fonte `perfil` e confiança menor. Quem decide o corte é sempre o edital; os cortes típicos da banca ficam como comentário no YAML.
- Outro pacote acrescenta ou substitui um perfil (pelo mesmo `id`) nos entry points `concurso.banca` e `concurso.ocr`.

### Banca nova

1. Copie `perfis/bancas/generic.yaml` para `perfis/bancas/<id>.yaml`; troque `id`, `nome` e `marcas`, e preencha `formato`, `alternativas` e `penalidade` pelo edital da banca.
2. Escreva primeiro o teste: um trecho curto de edital real da banca em `tests/editais_bancas.py` e o caso em `tests/test_perfis_novos.py`, com as regras esperadas.
3. Se o gabarito ou a folha da banca têm um formato próprio, acrescente o leitor ou o perfil de OCR com fixture sintética (`tests/folha_sintetica.py`).
4. Rode a paridade: um perfil novo não pode mudar a saída dos concursos já analisados.

## Fallbacks

Cada informação tem uma cadeia de camadas, e o valor registra de qual veio (`fonte`, `camada`, `confianca`):

- **Regras do edital:** texto do edital (heurística), retificação, LLM (só os campos que cairiam no perfil ou no padrão), perfil da banca, padrão, `edital_a_confirmar.yaml` (fonte `config`).
- **Folha:** `respostas_revisadas.csv` (`--reuse-csv`), perfil de OCR do `template`, detecção automática (com os limiares calibrados, se houver), CSV manual.

Para acrescentar uma camada:

1. Um teste que mostra a camada anterior falhando e a nova preenchendo, com dados sintéticos.
2. A camada só entra depois das fontes que vêm do usuário ou do documento: ela nunca troca um valor de `edital`, `retificacao` ou `config`.
3. Um valor novo leva fonte, confiança e, quando vem de documento, trecho, documento e página. Uma camada nova é um valor novo de `FonteRegra` e de `CAMADA_DA_FONTE`.
4. O que a camada decidiu aparece em "O que o app decidiu sozinho" no `index.html` e como aviso no log.
5. Falha da camada vira aviso e a análise segue com a próxima; nunca aborta os outros concursos.

## Notebooks

- Cada notebook é um script jupytext no formato percent, `notebooks/NN_*.py`; rode com `scripts/rodar_notebooks.sh [arquivos]`.
- Uma célula só chama funções do pacote (`concursos.analytics` e `carregar_configuracao_global`) e exibe o resultado. Parsing, OCR, regra de negócio e cálculo de correção moram nos módulos acima, com teste; um número novo que o notebook precise vira antes uma função testada. Nenhum módulo do pacote importa de `notebooks/`.
- Tabelas longas passam por `resumir` (em `visualizacao`). A conclusão em prosa cita os números que as células imprimem; rode o notebook de novo ao mudar uma função da qual ele depende.

## Convenções de análise

- Métrica padrão: `ajustada` (ao acaso; erro vale −1/(k−1)). A evolução se lê pelo z-score por disciplina, porque a média dos z de um concurso fica perto de 0 por construção.
- Todo percentual vem com o n. n < `N_MINIMO_TOPICO` (5) é amostra insuficiente, e uma tendência exige `MINIMO_PONTOS_TENDENCIA` (3) ordens distintas. Use as constantes nos limiares e nos textos.
- Gerais e específicos ficam separados (`bloco`) nas séries por disciplina.
- O limiar de tópico fraco vem do `config.toml` (`[analise] limiar_topico_baixo`).
- O dado guarda o texto inteiro (CSV, parquet, `chave_topico`); só a apresentação abrevia, com `abreviar`.

## Edital como fonte de verdade

- **Edital obrigatório:** sem `edital` no `concurso.yaml`, o concurso fica incompleto. O modo mínimo segue com tópicos `nao_mapeado` e revisão em `revisao/questoes_revisado.csv`.
- **Rastreável:** todo valor com fonte `edital`, `retificacao`, `descoberta` ou `llm` traz trecho, documento e página, para conferir no PDF. A busca respeita o escopo do cargo (`_Escopo`), e a retificação mais recente vence campo a campo. Uma resposta do LLM sem trecho literal conferível é descartada.
- **Peso realizado vence:** a nota usa o peso do `correcao.json`. O peso do edital é expectativa, e a divergência vira `warn` no CSV de discrepâncias. `correcao.py` não importa `regras_edital`; o `correcao.json`, os CSVs das fases 1 e 2 e o parquet mantêm schema e valores.
- **Corte é múltiplo:** o gap é calculado contra cada corte aplicável, na unidade dele (pontos ou acertos), e "atingido" exige todos. O corte da discursiva fica fora do "atingido", e escore padronizado e corte por classificação saem como não calculáveis.
- **Data só do edital ou da configuração:** sem data em nenhuma das duas fontes (nem no LLM, se ligado), o concurso fica sem data, com aviso.
- **Descoberta tem uso:** cada candidato do registro declara o uso no projeto, o impacto e o status. Sem uso que mude análise, decisão ou gráfico, ele vai para os descartados com o motivo. Mudar um candidato sobe `VERSAO_CANDIDATOS`.
- **Descoberta propõe:** quando ela afeta código de fase anterior (OCR da folha, `correcao.py`), registre-a como `proposto`, com o diff estimado em `proposta`, e peça confirmação. O catálogo lista essas propostas.
- **Simulação é estimativa:** os textos de cenário se apresentam como estimativa e não estimam colocação.

## CLI

- A CLI só lê flags, monta `Opcoes` (com `saida=typer.echo`) e chama `aplicacao/`; a orquestração não mora em `cli/comandos.py`.
- Erro do usuário: `ErroDoUsuario(causa, dica)`, código 1; do ambiente: `ErroDoAmbiente`, código 2 (ambos em `erros.py`). Na tela, no máximo `erro:` e `dica:`; o traceback vai só para o log em `~/.concurso/logs/`.
- Toda pergunta tem padrão e é pulada sem TTY, com `CI` ou com `--yes`. `--dry-run` não grava nada, nem configuração.
- Reexecutar sem mudança não altera nenhum `mtime` em `analises/`; grave saídas regeneradas a cada execução com `gravar_se_mudou`.

## GUI

- Casca sobre `aplicacao/`: nenhuma regra de negócio, parsing ou cálculo em `gui/`. Uma ação nova da GUI é antes uma função testada de `aplicacao/`. `gui/` e `aplicacao/` não importam `typer` nem `concursos.cli` (teste por AST).
- Só `127.0.0.1`, nunca `0.0.0.0`. Janela nativa no Windows e no macOS; modo navegador no Linux.
- Perguntas passam pelo protocolo `Interacao` (`InteracaoGui`); o trabalho pesado roda em thread (`run.io_bound`) e nunca no loop da interface.
- Ao escolher o projeto, a GUI faz `chdir` para ele: os relatórios gravam caminhos relativos à pasta atual.
- Integração desligada mostra o texto de consentimento de `aplicacao.integracoes` antes de ligar. A IA começa desmarcada.
- Cor, espaço e elevação só por `gui/tema.py`: nenhum hex, classe de cor do Quasar (`bg-red-1`, `text-grey-8`) ou `gap-*` fora dele (teste). O espaçamento vai por `style='gap: ...'`. Status sempre com ícone e texto, nunca só cor; o contraste dos tokens é testado (AA).
- Abrir no navegador quando a janela nativa foi esperada nunca é silencioso: a `DecisaoJanela` decide o aviso.
- Testes em `tests/gui/` com a fixture `user` do NiceGUI e a camada de aplicação falsa; pulados sem o extra `[gui]`.
- Nenhum arquivo do usuário exige edição à mão: revisão de tópicos, edital a confirmar, taxonomia e dicionário têm tela, e salvar reanalisa os concursos afetados.
- Vocabulário leigo: as telas e as mensagens ao usuário de `aplicacao/estudo.py`, `aplicacao/integracoes.py` e `planilha_tec.py` não dizem localhost, porta, servidor, Docker, API, source, notebook (sozinho), sincronizar, embedding nem terminal (teste). "open-notebook", "livros", "biblioteca" e "perguntar" podem. A exceção é a seção Avançado das Configurações.
- O `biblioteca.yaml` é legado e opcional: a biblioteca de livros mora em `~/.concurso/biblioteca/`, e as disciplinas dos livros vêm da tela.

## Executável

- `empacotamento/concurso-analise.spec`, onedir, a partir de `uv sync --no-dev --extra gui --extra llm --extra pci`; o grupo dev quebra o plotly congelado. Dado novo de pacote (YAML, template) precisa entrar pelo `hook-concursos.py`.
- O Tesseract embutido entra no `PATH` pelo launcher, com `TESSDATA_PREFIX`; a lógica continua usando `shutil.which`.
- A árvore do Tesseract é copiada depois do `COLLECT` (`copiar_tesseract` no `.spec`), nunca por `datas`: o PyInstaller trata as bibliotecas de `datas` como binários e põe as dependências delas na raiz do pacote, onde vencem as do sistema.
- No Linux, o bootloader troca o `LD_LIBRARY_PATH`; o launcher devolve o original antes de abrir processos do sistema (navegador, `xdg-open`).
- Assinatura pela SignPath, só dos binários próprios (`concurso-analise.exe`, `concurso-analise-cli.exe`, o setup); DLLs de terceiros e o desinstalador ficam sem assinatura. Sem o secret `SIGNPATH_API_TOKEN`, o build segue sem assinar.
- O AppImage passa por `empacotamento/linux/verificar_bibliotecas.sh`: nada resolve fora do bundle além de `bibliotecas_do_sistema.txt`, e o Tesseract só usa o próprio carregador.
- A release traz `atualizacao.json` e `atualizacao.json.sig` (Ed25519, `scripts/assinar_manifesto.py`); mudar o formato do manifesto exige manter o app antigo lendo a release nova.
- O pacote de estudo (`empacotamento/estudo/`, workflow `estudo.yml`) é uma release própria, tag `estudo-v<open-notebook>-<n>`, com `estudo.json` e `estudo.json.sig` (mesma chave Ed25519). Uma versão nova do open-notebook só vira pacote com os testes de contrato (`tests/contrato_open_notebook/`) e o smoke verdes nos dois sistemas; se algo falhar, abre uma issue.
- Antes de publicar uma release: o `release.yml` verde (`--smoke` e `scripts/smoke.py congelado` em máquina limpa em cada sistema, juntados no `RELATORIO-SMOKE.md` da release) e o checklist manual de `docs/release.md` (Windows Sandbox, VM Win10 sem WebView2 e Linux), registrado na descrição da release. A release nasce como rascunho.

## Código

- Nomes, docstrings, comentários e docs em português. O ruff não quebra strings nem comentários longos, e o E501 está desligado: quebre à mão o que passar do `line-length`.
- Comentários e docstrings só registram restrições que o código não mostra.
- Preserve o final de linha de cada arquivo: boa parte da fase 1 (e `docs/modelo.md`) usa CRLF.
- Valor fechado (status do gabarito, formato, pontuação) é enum de `modelo.py`. O yaml grava `.value`, porque o `yaml.safe_dump` recusa `StrEnum`.
- TDD: o teste que falha vem primeiro, em `tests/` (os das fases 2 e 3 são `test_analytics_<módulo>.py`), com dados sintéticos; `tests/consolidado_sintetico.py` monta consolidados mínimos. Concurso de teste usa `criar_concurso` (ou `com_edital_minimo`) do `conftest.py`, que grava um edital manual mínimo. Para regras do edital, use trechos curtos de texto real como fixture.
- Python 3.11 e 3.12; o `uv.lock` é commitado. O que o comando principal importa é dependência do projeto, não de grupo: o `uvx` não instala grupos.

## Fora de escopo

- Servidor web acessível pela rede, app mobile, servidor multiusuário e sincronização em nuvem. A GUI local, só em `127.0.0.1`, é da fase 5.
- OCR treinado próprio, idiomas além do português, e LLM ou embeddings para classificar tópicos, ler a folha ou ler a prova.
- A interface web do open-notebook, o Ollama, o docling e o pacote de estudo no macOS.
- Telemetria, mesmo opt-in, e atualização automática silenciosa (a atualização só começa depois de uma confirmação do usuário).
- Calcular corte por escore padronizado ou por quantidade de classificados, e estimar colocação.
- Marketplace de perfis, pacotes Homebrew, Chocolatey ou winget, `.msi`, Microsoft Store, publicar no PyPI, assinatura e notarização no macOS, WebView2 fixo e a extensão do TEC na Chrome Web Store.
