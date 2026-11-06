# Decisões da fase 7

Registro curto das escolhas da fase 7 (estudar com o open-notebook, dicionário de temas e fluxos assistidos), com o contexto e as alternativas descartadas. A spec está em `docs/spec-fase7.md`; as fontes, em `docs/pesquisa-open-notebook-embarcado.md`.

## 1. open-notebook gerenciado pelo app, sem Docker

- **Contexto:** o usuário-alvo não sabe o que é Docker, terminal ou endereço local. O open-notebook exige o SurrealDB, a API, o worker e o frontend Next.js, e o caminho oficial é o Docker Compose.
- **Decisão:** usar o open-notebook sem copiar o código dele: só a API e o worker, com o SurrealDB 2.x, supervisionados pelo app em `127.0.0.1`. A nossa GUI é a interface.
- **Descartado:** motor nativo como principal (o dono do produto quer a solução do open-notebook); a interface do open-notebook (Node, porta 5055 fixa, `/api/config` consulta o GitHub); exigir o Docker ou o Ollama.

## 2. Pacote de estudo assinado, baixado com consentimento

- **Contexto:** o open-notebook precisa de um Python de verdade (o app congelado não hospeda `uvicorn api.main`), do código da release (migrations e prompts) e do SurrealDB. Embutir tudo levaria o instalador perto de 800 MB.
- **Decisão:** um pacote por sistema (Windows x64 e Linux x64), montado no CI e assinado com a mesma chave Ed25519 do atualizador: Python 3.12 standalone, o ambiente travado da tag sem Node e ffmpeg, o `surreal` 2.x, o servidor de embeddings com o modelo, o cache do tiktoken e as licenças. É baixado uma vez, com consentimento, ao abrir "Estudar".
- **Publicação:** release própria no mesmo repositório, tag `estudo-v<open-notebook>-<n>`, com `estudo.json`, `estudo.json.sig` e um arquivo por sistema: `.zip` no Windows e `.tar.xz` no Linux, que guarda as permissões de execução. O `.tar.zst` foi descartado porque o zstd só entra na biblioteca padrão no Python 3.14, e o app não ganha uma dependência só para isso. O `estudo.json` declara `app_minimo`; o pacote segue o canal do app.
- **Descartado:** tudo no instalador (tamanho, e toda atualização rebaixaria o modelo); instalar com um uv embutido resolvendo no PyPI (mais pontos de falha na máquina do usuário).

## 3. Acompanhar cada release do open-notebook

- **Decisão:** o workflow `estudo.yml` roda por dia. Uma release nova do upstream é montada, passa pelos testes de contrato do nosso cliente e pelo smoke nos dois sistemas e, se tudo passar, é publicada sozinha. Se algo falhar, o pacote anterior continua e uma issue é aberta com o relatório.
- **Na máquina do usuário:** o mesmo canal e as mesmas regras do atualizador (consulta só no clique, no `upgrade` ou com `verificar_ao_abrir`; instalação só depois de confirmar). Antes da primeira partida da versão nova, backup verificado da pasta do banco; se a partida falhar, volta ao pacote anterior. Ficam os 2 backups mais recentes.
- **Risco aceito:** a API do open-notebook muda em versões menores; o teste de contrato é a defesa.

## 4. Embeddings servidos por um processo nosso

- **Contexto:** a busca vetorial e o Ask do open-notebook exigem um provedor de embeddings; os locais são o Ollama ou um servidor compatível com OpenAI.
- **Decisão:** `servidor_embeddings.py`, dentro do pacote, serve `/v1/embeddings` em `127.0.0.1` com token, usando onnxruntime + tokenizers e o `paraphrase-multilingual-MiniLM-L12-v2` quantizado (Apache-2.0). O app o registra no open-notebook por `/api/credentials`, `/api/models` e `/api/models/defaults`. Embeddings servem só para buscar nos livros, nunca para classificar tópicos.
- **Descartado:** fastembed (traz o `huggingface-hub` e baixa modelos); torch (+0,5 a 0,8 GB); `multilingual-e5-small` qint8 (exige AVX-512 VNNI); sem embeddings (BM25 com stemmer inglês, fraco em português).
- **Modelo fixado:** trocá-lo exige uma decisão registrada aqui e reprocessa todos os livros.

## 5. O nosso app pré-processa os livros

- **Contexto:** o open-notebook falha em PDF escaneado (sem docling) e não guarda o número da página.
- **Decisão:** o app extrai o texto por página (pdfplumber; Tesseract embutido nas páginas sem texto), em segundo plano e retomável, e envia um source de texto com marcas `[p. N]`. O original é copiado para `~/.concurso/biblioteca/`, para o botão "Abrir arquivo".
- **FTS5 local:** o mesmo texto vai para um índice SQLite FTS5 com radicais em português, que localiza o trecho com a página e serve de busca quando o open-notebook está fora.

## 6. Ciclo de vida sob demanda

- **Decisão:** os processos sobem ao abrir "Estudar", ao enviar um livro ou ao sincronizar depois de uma análise, e param depois de 10 min sem uso ou quando o app fecha. Portas livres de `127.0.0.1`, senha e token aleatórios por sessão, trava de instância única (lock do RocksDB), `/retry` nos jobs presos na partida, nunca `/api/config`.
- **Descartado:** sempre ligados (cerca de 650 MB de RAM com o app aberto).

## 7. Consentimento e IA

- **Instância gerenciada sem IA:** nada sai do computador; a sincronização dos livros e das análises é automática, sem tela de consentimento, com o candidato como pseudônimo.
- **IA nos livros:** consentimento próprio (`[llm] consentimento_livros`), separado do edital e desligado por padrão. A chave vai por variável de ambiente na partida do processo e nunca é gravada no banco do open-notebook. O Ask responde como "Resposta da IA — confira nos trechos", seguido dos trechos com página de cada livro citado.
- **URL externa:** quem já usava uma instância própria continua; a opção fica em Configurações > Avançado e na CLI, com o consentimento de antes.

## 8. Instância compartilhada entre projetos

- **Decisão:** a biblioteca é global por usuário do computador; os livros (`Biblioteca — <disciplina>`) são compartilhados. Os notebooks de análise levam o nome da pasta do projeto e, na instância gerenciada, são achados só pelo ID guardado no estado, nunca pelo nome.
- **Biblioteca legada:** o `biblioteca.yaml` vira opcional; uma migração única, com backup, leva as categorias dele para as disciplinas dos livros; os notebooks `Biblioteca — <categoria>` do projeto `books` continuam sendo lidos.

## 9. Dicionário de temas

- **Contexto:** o TF-IDF depende de coincidência de palavras; o risco é inflar o texto e piorar a classificação.
- **Decisão:** marca sintética `tema_<disciplina>_<topico>` na questão (no máximo 3) e termos no documento do tópico. Com o dicionário, a versão expandida decide; `score_tfidf` e `topico_tfidf` ficam ao lado. Sem o arquivo, a saída é idêntica. A métrica de ganho usa as revisões como verdade, sem vazamento entre concursos. O dicionário inicial só sai com Δ ≥ 0.
- **Descartado:** acrescentar os termos ao texto da questão (inflação); manter o TF-IDF como decisor (o dicionário não mudaria nada).

## 10. Nome do concurso vem do edital

- **Decisão:** a pasta ganha um identificador automático e estável (`tcu_2025`, `concurso_AAAAMMDD`), nunca renomeado. O nome mostrado ("TCU 2025 — Cargo", com o nome oficial como subtítulo) vem de uma cadeia: correção do usuário (`titulo`, fonte `config`), retificação, edital, título do PCI (fonte `pci`), IA, nome do arquivo, identificador. Abaixo do edital, "a confirmar".
- **Descartado:** renomear a pasta quando o edital chega (quebra saídas, manifestos e paridade); edital obrigatório para cadastrar.

## 11. Nenhum arquivo editado à mão

- **Decisão:** revisão de tópicos, campos do edital a confirmar, taxonomia e dicionário ganham telas; salvar reanalisa só os concursos afetados, e o manifesto inclui esses arquivos quando existem.

## 12. GUI

- **Menu:** cinco itens (Concursos, Estudar, Analisar, Resultados, Importar do TEC) e um menu utilitário (Configurações, Sobre).
- **Vocabulário:** pode aparecer "open-notebook", "livros", "biblioteca" e "perguntar"; nunca localhost, porta, servidor, Docker, API, source, notebook sozinho, sincronizar, embedding ou terminal (teste).
- **PCI:** UF e cidade em select (municípios do IBGE embutidos, sem rede), região no card, datas DD/MM/AAAA em toda exibição, termo das provas anteriores explicado.

## 13. Entrega

- Branch `fase-7`, PR único no fim, um commit verde por fatia. Primeiro `0.7.0b1` no canal beta, com o checklist manual completo.
