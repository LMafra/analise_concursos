# Detalhes técnicos

O [README](../README.md) fala com quem usa a janela. Aqui fica o que ele deixou de fora: comandos de terminal, conferência de arquivos, nomes de protocolos e configurações que só interessam a quem quer saber como o app funciona por dentro.

## Instalação

### Conferir o download

A página de cada versão traz o `SHA256SUMS`, com a impressão digital (SHA-256) de cada arquivo.

- **Windows (PowerShell):** compare com a saída de `Get-FileHash .\concurso-analise-<versão>-windows-x64-setup.exe`.
- **Linux:** na pasta do download, `sha256sum -c SHA256SUMS --ignore-missing`.
- **macOS:** `shasum -a 256 -c SHA256SUMS --ignore-missing`.

### AppImage no Linux

- Tornar o arquivo executável pelo terminal: `chmod +x concurso-analise-*.AppImage`.
- Se ele não abrir por falta do FUSE, rode `APPIMAGE_EXTRACT_AND_RUN=1 ./concurso-analise-*.AppImage`.
- A janela é servida em `127.0.0.1`, numa porta escolhida na hora, e abre no navegador padrão.
- O AppImage traz o Python e o Tesseract com o modelo `por`; foi testado em Debian 12 e Ubuntu 22.04 sem Python nem Tesseract.

### Assinatura no Windows

O SmartScreen avisa sobre todo programa baixado por poucas pessoas, mesmo assinado. A assinatura é da SignPath Foundation e cobre só `concurso-analise.exe`, `concurso-analise-cli.exe` e o setup; as DLLs de terceiros mantêm a assinatura de origem. Se o editor não for SignPath Foundation, ou se a assinatura aparecer como inválida, baixe de novo e confira o `SHA256SUMS`.

## Atualização

- **Pela janela:** Sobre > Verificar atualizações > Baixar e instalar.
- **Pelo terminal:** `concurso-analise upgrade` procura a versão nova; `concurso-analise upgrade --run` baixa, confere e instala. Fora do executável, o comando mostra ou roda `uv tool upgrade concurso-analise`.
- **Como o app confere:** cada release traz `atualizacao.json` e `atualizacao.json.sig`, um manifesto assinado com Ed25519. O app só usa o arquivo baixado se a assinatura do manifesto conferir com a chave embutida e se o SHA-256 do arquivo for o do manifesto. Sem as duas coisas, ele avisa e não instala.
- **Canais:** `stable` (padrão) e `beta`, em `[atualizacao] canal` no `~/.concurso/config.toml`. Com `verificar_ao_abrir = true`, o app consulta o GitHub no máximo uma vez por dia.
- **Biblioteca de estudo:** é uma release própria (`estudo-v<versão>-<n>`), com `estudo.json` e `estudo.json.sig`, conferida pela mesma chave. Antes de trocar, o app guarda uma cópia e volta a ela se a nova não abrir.

## Terminal

### Instalar sem o instalador

Precisa do [uv](https://docs.astral.sh/uv/getting-started/installation/) e, para PDF escaneado, do Tesseract com o português (`concurso-analise doctor` mostra o comando do seu sistema). O passo a passo está em [Desenvolvimento](../README.md#desenvolvimento), no README.

### Docker

A imagem já traz o Tesseract em português, e a pasta montada em `/dados` é o projeto:

```sh
docker build -t concurso-analise .
docker run --rm -it --user "$(id -u):$(id -g)" -v "$PWD:/dados" concurso-analise
```

### Mensagens de erro e aviso

Um erro aparece em até três linhas: `erro:` (o que aconteceu), `dica:` (o que fazer) e, quando houver, `detalhe:` (o texto técnico, como o nome do arquivo ou a mensagem da biblioteca). Um aviso segue o mesmo formato, com `aviso:` na primeira linha. Na janela, o detalhe fica em "Ver detalhes técnicos", fechado. O traceback vai só para `~/.concurso/logs/concurso-analise.log`.

Códigos de saída: 0 sucesso, 1 problema nos seus dados ou na configuração, 2 problema no ambiente.

## Leitura da prova e do edital

- **Leitura de imagem (OCR):** edital, prova e folha escaneados passam pelo Tesseract. Sem ele, o edital escaneado não é lido e o concurso segue sem o conteúdo do edital (o "modo mínimo"): as questões ficam com o tópico `nao_mapeado` e a revisão vai para `provas/<concurso>/revisao/questoes_revisado.csv`.
- **Leitura da folha:** a ordem é `respostas_revisadas.csv` (`--reuse-csv`), o perfil de OCR do modelo da folha, a detecção automática (com os limiares calibrados, se houver) e o CSV manual. A confiança de cada leitura vai na coluna `confianca_ocr` de `respostas_extraidas.csv`; abaixo de `[analise] limiar_confianca`, a questão fica com `revisar = True`.
- **Tema de cada questão:** sugerido por similaridade TF-IDF entre o enunciado e os tópicos do edital, com um `score`. O dicionário de temas (`.concurso/taxonomia_topicos.yaml`) acrescenta sinônimos antes da comparação.
- **Regras do edital:** a cadeia é edital (heurística), retificação, IA (só nos campos que cairiam no perfil ou no padrão), perfil da banca, padrão e `edital_a_confirmar.yaml` (fonte `config`). Cada valor guarda `fonte`, `camada`, `confianca` e, quando vem de documento, trecho, documento e página.
- **Regra padrão da banca:** é o perfil YAML em `src/concursos/perfis/bancas/`. "Fator" é o número de acertos que um erro anula (Cebraspe: 1; FGV: 0).

## Métricas

- **Aproveitamento descontado o chute (percentual ajustado):** um erro vale −1/(k−1), em que k é o número de alternativas; assim, chutar tudo dá 0 em média.
- **Evolução:** a posição de cada disciplina dentro do concurso, em desvios em relação à média (z-score). A tendência usa a correlação de Spearman entre a ordem dos concursos e o desempenho; "melhorando" e "piorando" exigem p < 0,05, e "leve alta" ou "leve queda" é |ρ| ≥ 0,3 sem significância.
- **Amostra:** n < 5 questões é amostra insuficiente; uma tendência exige 3 concursos com data distinta.
- **No limite:** a nota fica a até 2 pontos percentuais do corte, para cima ou para baixo.

As fórmulas completas estão em [modelo.md](modelo.md).

## Inteligência artificial para ler editais

Provedores: OpenAI, OpenRouter, Gemini, Ollama (local, sem chave) e Anthropic. Só o texto do edital e dos anexos é enviado, depois do consentimento; cada valor precisa citar um trecho literal do edital, ou é descartado. A chave vem de variável de ambiente ou do cofre do sistema (keyring, com o extra `llm`) e nunca vai para o `config.toml`. `--offline` e `--no-llm` desligam a IA.

## open-notebook

A tela Estudar usa uma instância do [open-notebook](https://github.com/lfnovo/open-notebook) que o próprio app prepara e gerencia: SurrealDB, a API, o worker e o servidor de embeddings escutam só em `127.0.0.1`, em portas aleatórias, com senha e token por sessão. Os embeddings servem só para buscar nos livros.

Para usar um open-notebook seu (Configurações > Avançado > Usar meu próprio programa de estudo), com a instância de pé (por exemplo, `docker compose up -d` na pasta dele):

```sh
concurso-analise notebook enable                       # mostra o que vai e pede confirmação
concurso-analise notebook sync                         # envia agora; depois, toda análise envia sozinha
concurso-analise notebook sync --concurso meu_concurso --all-candidates
concurso-analise notebook disable
```

- O app cria um notebook por concurso e um consolidado, envia os relatórios e as planilhas como fontes e grava uma nota de resumo montada localmente.
- O candidato vai como pseudônimo (`candidato 1`), salvo `incluir_nome = true` em `[open_notebook]`. CPF e inscrição não são enviados.
- Se a instância tem senha, defina `OPEN_NOTEBOOK_PASSWORD` no ambiente; ela nunca vai para o TOML.
- O estado fica em `.concurso/open_notebook.json`; sem mudança, nada é enviado. `notebook sync` sai com 0, 1 (falha parcial ou senha recusada) ou 2 (instância fora do ar).

Testado com a versão 1.15. Os campos estão em [modelo.md](modelo.md), e as decisões, em [spec-open-notebook.md](spec-open-notebook.md).

## PCI Concursos

O app consulta o servidor MCP público do PCI Concursos (`https://mcp.pciconcursos.com.br/mcp`, em beta) com o extra `pci` (`uv tool install 'concurso-analise[pci]'`).

```sh
concurso-analise pci enable                     # mostra o que é enviado e pede confirmação
concurso-analise discover --cargo analista --cargo auditor --uf mg
concurso-analise discover --cidade campinas --uf sp --json
concurso-analise discover --cargo analista --register 296237   # acompanha o concurso
concurso-analise add provas/camara_x --pci 296237              # vincula a pasta do concurso
concurso-analise pci provas meu_concurso                       # provas anteriores do mesmo cargo e banca
concurso-analise pci provas meu_concurso --download 20549582   # abre a página e importa o que você baixar
```

- **O que sai do computador:** só termos de busca (cargos, UF, cidade, região, termos de prova).
- **Cargos de interesse:** `[pci] cargos` e `uf` em `~/.concurso/candidatos/<slug>.toml`; sem eles, `[pci_mcp] cargos` e `uf` no `~/.concurso/config.toml`.
- **Resultado guardado (cache):** `.concurso/cache/pci_mcp.json`, por `ttl_horas` (24). `--refresh` consulta de novo, e `--offline` usa o guardado, mesmo vencido, com aviso. No máximo 20 consultas por execução.
- **Prazos dos editais:** depois de cada análise, `analises/<candidato>/radar_editais.md` lista os concursos que fecham em até `dias_alerta` (15) dias ou que vão abrir, mais os que você acompanha (`.concurso/interesses_pci.yaml`).
- **Provas anteriores:** o PDF fica atrás de um captcha e o `robots.txt` do PCI proíbe o download por robô; o app lê só a página HTML, nunca chama `/provas/link`, e importa o que você baixou da pasta de downloads (`pasta_downloads`). O simulado vira `provas/<orgao>_<ano>_pci<id>/` e fica fora das tendências, salvo `incluir_simulados = true` em `[analise]`.
- **Falhas:** num comando explícito, saem com código 2 (o site fora do ar) ou 1 (um filtro recusado); depois da análise, só geram aviso.
- **No Cursor:** crie `.cursor/mcp.json` com `{"mcpServers": {"pci-concursos": {"url": "https://mcp.pciconcursos.com.br/mcp"}}}`.

As decisões estão em [spec-pci-mcp.md](spec-pci-mcp.md), e o que o servidor responde, em [pesquisa-pci-mcp.md](pesquisa-pci-mcp.md).

## Problemas comuns pelo terminal

- **"Não encontrei a pasta onde ficam suas provas".** Rode o comando na pasta que contém `provas/`, indique outra com `--provas <pasta>`, ou cadastre um concurso com `concurso-analise add`. O app nunca cria a pasta sozinho.
- **Folha lida errado.** Corrija a coluna `alternativa_marcada` de `analises/<candidato>/<concurso>/respostas_extraidas.csv` e rode `concurso-analise analyze <concurso> --reuse-csv`. Para um modelo de folha desconhecido: `concurso-analise init --calibrate-sheet folha.png --calibrate-answers ABCD-`, com as 5 primeiras respostas (`-` para branco).
- **Dados do edital a confirmar.** O `edital_a_confirmar.yaml` da pasta do concurso guarda os campos que o edital não trouxe; a tela Concursos > Conferir > Dados do edital o edita, e os valores passam a valer com fonte `config`.
- **Mudei uma configuração e nada mudou.** A análise só reprocessa o que mudou nos arquivos: rode `concurso-analise --force`.
- **O relatório não abriu.** `concurso-analise report` o reabre. No WSL, o app usa o `wslview` (pacote `wslu`) ou o `explorer.exe`.
- **A IA não foi usada.** O `doctor` diz qual variável de ambiente definir com a chave.
