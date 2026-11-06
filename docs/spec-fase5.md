# Spec da fase 5: interface gráfica e executável para usuário leigo

As decisões, com as alternativas descartadas, estão em `docs/decisoes-fase5.md`; os campos de arquivo, em `docs/modelo.md`.

## Objetivo

Qualquer pessoa usa o `concurso-analise` sem terminal, sem instalar Python, `uv` ou Tesseract e sem editar `config.toml`. Duas frentes:

1. Uma GUI em NiceGUI que cobre o fluxo essencial (onboarding, cadastro de arquivos, análise, resultados, configurações) e expõe as integrações que já existem (open-notebook, PCI Concursos, recomendações de estudo, prática no TEC).
2. Um executável por sistema, que embute Python, dependências e Tesseract, com instalador no Windows.

A CLI continua como está. A GUI é uma casca sobre a mesma lógica: nenhuma regra de negócio mora em `gui/`.

## Termos

| Termo | Significado |
|---|---|
| projeto | a pasta com `provas/`, `analises/` e `.concurso/`; na CLI, a pasta atual; na GUI, a escolhida e lembrada em `[gui] ultimo_projeto` |
| camada de aplicação | `concursos.aplicacao`: a orquestração que estava nos helpers de `cli/comandos.py`, usada pela CLI e pela GUI |
| janela nativa | a janela do pywebview aberta pelo NiceGUI (`native=True`), no Windows e no macOS |
| modo navegador | a GUI no navegador padrão, em `127.0.0.1`, no Linux |
| executável | a pasta onedir do PyInstaller, com o launcher `concurso-analise` |
| instalador | o `setup.exe` do Inno Setup (Windows), o `.dmg` (macOS) ou o `.AppImage` (Linux) |
| máquina limpa | sistema sem Python, sem `uv` e sem Tesseract no `PATH` |
| captura do TEC | a extensão do Chrome e o userscript do `tec-erros/`, que geram as exportações lidas pela prática |

## Histórias

### Começo

1. Como candidato leigo, quero instalar com um instalador e abrir pelo menu Iniciar, sem terminal.
2. Como candidato, quero que a primeira abertura sugira `Documentos/Concursos` como pasta do projeto, e que eu possa trocá-la por um diálogo de pastas, sem digitar caminho.
3. Como candidato, quero responder às mesmas perguntas do `init` num formulário (nome, pastas, calibração da folha, IA, conferir ambiente), com as respostas atuais como padrão.
4. Como candidato, quero que a GUI lembre o projeto e o candidato da última vez.

### Concursos e arquivos

5. Como candidato, quero ver a lista de concursos com a situação (`completo`, `incompleto`, `desatualizado`) e o status do gabarito, como no `status`, e os motivos de um incompleto.
6. Como candidato, quero criar um concurso e arrastar para ele o edital, o gabarito e a prova, e ver o papel que o app detectou para cada arquivo ("Detectamos que este arquivo é o edital. Confirma?"), trocando antes de cadastrar.
7. Como candidato, quero que as perguntas de ambiguidade do cadastro (dois gabaritos, banca, caderno) apareçam como diálogos com as mesmas opções da CLI.
8. Como candidato, quero acrescentar a minha folha de respostas, o `respostas.txt` ou o `respostas.csv`, que vão para `provas/<concurso>/candidatos/<nome>/`.
9. Como candidato sem Tesseract, quero um aviso claro e um formulário para digitar as respostas, que vira o `respostas.csv` (`questao,alternativa`).
10. Como candidato com mais de um perfil no projeto, quero escolher o candidato ou analisar todos.

### Análise e resultados

11. Como candidato, quero um botão "Analisar" com barra de progresso por concurso e um painel de log que abro quando quero.
12. Como candidato, quero ver o relatório dentro da janela, com os gráficos, e abri-lo no navegador com um clique.
13. Como candidato, quero ver as recomendações de estudo e a prática no TEC na tela de resultados, e uma explicação quando ainda não existem.
14. Como candidato, quero exportar o consolidado em CSV, parquet ou markdown.

### Configurações

15. Como candidato, quero ajustar o limiar de confiança da leitura, o limiar de tópico fraco e o concurso-alvo por controles, sem ver o `config.toml`.
16. Como candidato, quero a opção "Usar IA para ler editais (requer chave)" desmarcada por padrão; ao marcar, escolho o provedor e a chave vai para o cofre do sistema (ou `~/.concurso/.env`), nunca para TOML.

### Integrações

17. Como candidato, quero ligar o open-notebook vendo antes o que é enviado, sincronizar com um botão e ver o estado (ligado ou desligado, última sincronização).
18. Como candidato, quero descobrir concursos no PCI com filtros de cargo, cidade, UF e região, ver o prazo e o link, e acompanhar um concurso no radar.
19. Como candidato, quero listar as provas anteriores de um concurso cadastrado e importar uma como simulado: o app abre a página no navegador, eu baixo os PDFs e ele os importa da pasta de downloads.
20. Como candidato, quero soltar as exportações do tec-erros e o `caderno-estado.json` na tela da prática, e ver como instalar a captura no Chrome e no Android.

### Sobre e suporte

21. Como candidato, quero ver a versão, o caminho do log (com botão para abrir a pasta), o Tesseract usado e as licenças.
22. Como candidato, quero que todo erro apareça com `erro:` e `dica:` em português claro, sem traceback; o traceback vai para o log.

### Executável

23. Como mantenedor, quero o instalador de cada sistema gerado pelo CI numa tag `v*` e publicado na release, com `SHA256SUMS`.
24. Como mantenedor, quero que o executável passe pelo smoke numa máquina limpa antes de ser publicado.

## Entregas

Cada fatia é um PR com TDD e fecha com `uv run pytest`, `ruff` e `scripts/smoke.py`.

0. Spec, decisões e emendas no `AGENTS.md` e no `docs/modelo.md`.
1. Camada de aplicação (refactor com paridade).
2. `tec-erros/` no monorepo, com fixtures de contrato.
3. GUI mínima: projeto, status, análise com progresso, sobre.
4. Onboarding, cadastro com detecção, multi-candidato, respostas manuais.
5. Resultados.
6. Configurações.
7. Integrações.
8. Executável e instalador do Windows, workflow de release, smoke congelado.
9. AppImage e DMG arm64.
10. README, release e retro.

## Decisões de implementação

### Camada de aplicação

- `src/concursos/aplicacao/` recebe, quase sem mudança, os helpers privados de `cli/comandos.py`: a cadeia da análise, a escolha de candidato, o onboarding, o cadastro de arquivo, a prática, as recomendações, o radar, a sincronização com o open-notebook e as consultas ao PCI.
- `Opcoes` (frozen) ganha três campos: `saida` (onde vão as mensagens que a CLI imprimia; na CLI, `typer.echo`), `interacao` (a `Interacao` das perguntas, ou `None` quando não há a quem perguntar) e `ao_progresso` (repassado ao `analisar_todos`). Assim a CLI imprime exatamente o mesmo texto de antes.
- `ErroDoUsuario` e `ErroDoAmbiente` passam para `src/concursos/erros.py`; `cli/erros.py` os re-exporta. A GUI mostra `causa` e `dica`.
- `typer` e `cli/` não são importados por `aplicacao/` nem por `gui/` (teste por AST). `aplicacao/` não chama `print` nem `input`.
- A confirmação de `pci enable` e `notebook enable` continua na CLI (`typer.confirm`); a camada de aplicação dá o texto do aviso e a gravação.
- `pipeline.analisar_todos(..., ao_progresso=None)` chama `ao_progresso(concurso, indice, total)` antes de cada concurso que vai analisar. Com `None`, nada muda.
- `aplicacao.preferencias` lê e grava `[analise]` (`limiar_confianca`, `limiar_topico_baixo`, `concurso_alvo`) no `config.toml` do projeto, validando como o `configuracao_do_projeto`, e `[gui] ultimo_projeto` no global.

### GUI

- `ui.run(host='127.0.0.1', reload=False, native=<não Linux>, port=<livre>)`. O host nunca é `0.0.0.0`.
- `NICEGUI_STORAGE_PATH` aponta para `~/.concurso/gui`; o `app.storage` não guarda dado pessoal além do caminho do projeto.
- Ao escolher o projeto, a GUI faz `os.chdir(projeto)`: a análise grava caminhos relativos à pasta atual nos relatórios, e a taxonomia é resolvida por ela.
- A análise, o cadastro e as consultas rodam numa thread (`run.io_bound`). `InteracaoGui` é chamada dessa thread e abre o diálogo no loop da interface com `asyncio.run_coroutine_threadsafe`, esperando a resposta.
- O log da GUI é o mesmo da CLI (`~/.concurso/logs/concurso-analise.log`); um `logging.Handler` próprio alimenta o painel.
- O relatório é servido por `app.add_static_files` da pasta `analises/<candidato>/`, num `iframe`.
- Seletor de pasta: `create_file_dialog(FileDialog.FOLDER)` na janela nativa; no modo navegador, um seletor do lado do servidor. Arquivos: o evento `drop` da janela nativa entrega caminhos; no modo navegador, `ui.upload` grava numa pasta temporária. (Implementado: `ui.upload` nos dois modos; o `drop` nativo ficou de fora.)
- No modo navegador, fechar a aba não encerra o servidor: o menu tem "Fechar o app" (`app.shutdown`), recusado enquanto uma análise roda. Na janela nativa, fechar a janela encerra o app.
- Dependência num extra `[gui]` (`nicegui[native]>=4,<5`); script `concurso-analise-gui` e subcomando `concurso-analise gui`. Sem o extra, o subcomando sai com `ErroDoUsuario` e a dica de instalação.

### Executável

- PyInstaller onedir, a partir de `uv sync --no-dev --extra gui --extra llm --extra pci`. Hook próprio coleta os dados de `concursos` (perfis YAML) e o `dist-info` (entry points).
- O launcher (`empacotamento/launcher.py`) chama `freeze_support()`, põe o Tesseract embutido no início do `PATH`, define `TESSDATA_PREFIX` e abre a GUI. Com `--smoke`, roda o doctor e uma análise sintética sem janela e sai.
- Tesseract com `por.traineddata` do `tessdata_fast`, sem as ferramentas de treino. O `doctor` mostra "embutido" quando o binário vem do bundle.
- Windows: Inno Setup. Linux: AppImage montado em `manylinux_2_28`. macOS: `.app` num DMG, só arm64.
- Sem assinatura de código; o README mostra como passar pelo SmartScreen e pelo Gatekeeper.
- O instalador embute o `dist/` do `tec-erros/` (`caderno.html`, zip da extensão, userscript).

## Seams de teste

- **Camada de aplicação:** dados sintéticos com `criar_concurso`; `saida` coleta as mensagens numa lista; `interacao` é uma `Interacao` falsa com respostas roteirizadas. Os `tests/test_cli_*.py` continuam passando sem mudança.
- **GUI:** `nicegui.testing.user_plugin` (fixture `user`, sem navegador), em `tests/gui/`, com a camada de aplicação trocada por falsos via `monkeypatch`. Nenhum teste da GUI exercita OCR ou correção.
- **Contrato TEC:** as mesmas fixtures em `tests/contrato_tec/` passam pelo `node --test` e pelo `pytest`.
- **Executável:** `scripts/smoke.py congelado <executavel>` (doctor, análise de dois concursos sintéticos num caminho com espaço e acento, idempotência de `mtime`) e `launcher --smoke`.
- Os marcadores `integration` e `pci_mcp` ficam como estão.

## Fora do escopo

- Assinatura e notarização, auto-update e publicação na Chrome Web Store.
- Ponte ao vivo do tec-erros com a GUI.
- Tauri e Flet.
- macOS Intel e builds ARM do Windows e do Linux.
- `.msi`, winget, Homebrew e Chocolatey.
- Redução agressiva do bundle (pyarrow, codecs do OpenCV) além de um ticket de medição.
- Servidor acessível pela rede, multiusuário, nuvem e telemetria.

## Critérios de aceitação

- A paridade não mostra diferença depois da fatia 1, e nenhum `test_cli_*` muda.
- `concurso-analise gui` abre a janela (Windows, macOS) ou o navegador (Linux) só em `127.0.0.1`.
- Do zero, um usuário escolhe a pasta, responde ao onboarding, cria um concurso, solta os arquivos, confirma a detecção, analisa e vê o relatório com os gráficos, sem digitar caminho.
- Sem Tesseract, conclui pelo formulário manual.
- Mudar um limiar na GUI grava `[analise]` e vale na análise seguinte; a IA começa desmarcada e a chave nunca vai para TOML.
- Cada integração mostra o que é enviado antes de ligar; desligada, nada é chamado.
- O instalador do Windows instala, abre, analisa a fixture e desinstala numa máquina limpa; o tamanho fica na faixa documentada.
- A release `v0.5.0` tem os três artefatos e o `SHA256SUMS`.
