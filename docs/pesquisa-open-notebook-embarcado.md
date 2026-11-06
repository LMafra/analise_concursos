# Pesquisa: open-notebook sem Docker e busca nos livros do usuário

As fontes foram consultadas em 06/11/2026: o código e a documentação do open-notebook na tag `v1.15.1` (commit `5e285b7`), os pacotes do PyPI (content-core 2.2.1, esperanto 2.28.0, surreal-commands 1.3.1, surrealdb 1.0.8 e 3.0.0, fastembed 0.9.1, onnxruntime 1.31.1, sqlite-vec 0.1.9), as releases do SurrealDB e o Docker Hub. Os números marcados como **medido** vêm de uma execução em Linux x86_64 (WSL2): o wheel do open-notebook construído localmente, o ambiente travado instalado com `uv sync --frozen --no-dev`, o SurrealDB 2.7.0, a API e o worker em portas aleatórias. O que está marcado como **inferência** é raciocínio, não fonte.

Link curto: `ON = https://github.com/lfnovo/open-notebook/blob/v1.15.1`.

## 1. Opções avaliadas

- **(a) open-notebook gerenciado pelo app, sem Docker:** só a API e o worker, com o SurrealDB 2.x; a nossa GUI é a interface. Escolhida pelo dono do produto: usar a solução do open-notebook sem copiar o código dele.
- **(b) motor nativo:** SQLite FTS5 com radicais em português e, opcionalmente, vetores com ONNX. Fica como fallback e como localizador de trechos.
- **(c) interface do próprio open-notebook:** descartada (seção 5).

## 2. Como o open-notebook roda fora do Docker

- **Rotas oficiais:** "From source" ([from-source.md](https://github.com/lfnovo/open-notebook/blob/v1.15.1/docs/1-INSTALLATION/from-source.md)) e um guia comunitário para Windows ([windows-native.md](https://github.com/lfnovo/open-notebook/blob/v1.15.1/docs/1-INSTALLATION/windows-native.md)). Ambas pedem o checkout, `uv sync`, um `.env` e quatro processos em terminais separados; o projeto não traz launcher ("Open Notebook does not ship a launcher script").
- **Processos** ([supervisord.conf](https://github.com/lfnovo/open-notebook/blob/v1.15.1/supervisord.conf), [Dockerfile](https://github.com/lfnovo/open-notebook/blob/v1.15.1/Dockerfile)):
  - SurrealDB: `surreal start --user U --pass P --bind 127.0.0.1:PORTA rocksdb:<pasta>`;
  - API: `uvicorn api.main:app --host 127.0.0.1 --port PORTA` (o `run_api.py` liga o reload por padrão, então chamamos o uvicorn direto);
  - worker: `python -m surreal_commands.cli.worker --import-modules commands` (o `.exe` do worker falha no Windows com "Failed to canonicalize script path");
  - frontend Next.js: não usado.
- **Variáveis** ([environment-reference.md](https://github.com/lfnovo/open-notebook/blob/v1.15.1/docs/5-CONFIGURATION/environment-reference.md), [repository.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/database/repository.py#L41-L97)): `SURREAL_URL`, `SURREAL_USER`, `SURREAL_PASSWORD`, `SURREAL_NAMESPACE`, `SURREAL_DATABASE` (o worker tem padrões próprios, `test`, então todas vão explícitas), `OPEN_NOTEBOOK_ENCRYPTION_KEY`, `OPEN_NOTEBOOK_PASSWORD` (liga o Bearer; sem ela não há autenticação, [api/auth.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/api/auth.py)), `TIKTOKEN_CACHE_DIR`.
- **CORS `*`** por padrão ([api/main.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/api/main.py#L73-L80)): sem senha, qualquer página aberta no navegador do usuário chamaria a API. Por isso a senha aleatória por sessão é obrigatória.
- **Pasta de dados:** `DATA_FOLDER = "./data"`, relativa à pasta atual ([config.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/config.py#L4-L29)). As migrations também são lidas por caminho relativo: `open_notebook/database/migrations/1.surrealql` ([async_migrate.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/database/async_migrate.py#L98-L116)).
  - **Medido:** com a pasta atual fora do checkout, a partida falhou com `No such file or directory: 'open_notebook/database/migrations/1.surrealql'`; com `PYTHONPATH=<código>`, `PROMPTS_PATH=<código>/prompts` e a pasta de migrations exposta na pasta atual, subiu, e os uploads foram para `<pasta atual>/data/uploads`.
- **Pacote Python:** o `pyproject.toml` não tem `[project.scripts]`; o wheel só leva `open_notebook/**` (**medido**: sem `api/`, `commands/`, migrations nem `prompts/`). O que roda é o código-fonte da release com `uv sync --frozen --no-dev`, como no Dockerfile.
- **Migrations:** 25 de subida; a API roda as pendentes a cada partida e para se uma falhar ([api/main.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/api/main.py#L164-L208)). Só sobem: atualizar exige backup antes.

## 3. SurrealDB

- **Versão:** 2.x ("pinned to v2" no Dockerfile; o guia do Windows foi testado com a 2.6.5). A última 2.x é a v2.7.0 (28/09/2026, [release](https://github.com/surrealdb/surrealdb/releases/tag/v2.7.0)): `linux-amd64.tgz` com 26,2 MB (68,7 MB descompactado, **medido**) e `windows-amd64.exe` com 62,9 MB.
- **Licença:** BSL 1.1, data de mudança 17/09/2029 (vira Apache-2.0). Permite copiar e redistribuir; o uso em produção é livre, exceto como "Database Service", um serviço comercial que deixa terceiros criarem tabelas com esquema próprio ([LICENSE@v2.7.0](https://github.com/surrealdb/surrealdb/blob/v2.7.0/LICENSE)). **Inferência, não parecer jurídico:** um app gratuito de desktop que roda só o esquema fixo do open-notebook não é um Database Service. O texto da BSL vai junto do pacote.
- **Modo embarcado do SDK:** existe (`mem://`, `file://`, `surrealkv://` no SDK 1.0.8), mas o open-notebook sempre faz `AsyncSurreal(SURREAL_URL)` + `signin`, e o worker é outro processo esperando `LIVE` queries. **Inferência:** dois processos não dividem um arquivo RocksDB/SurrealKV embarcado; o servidor é necessário.

## 4. Processamento de documentos

- **Motores** do content-core: `auto`, `docling` ou `simple`; o docling é opcional e pesado ("several hundred MB to a few GB", [ADR-007](https://github.com/lfnovo/open-notebook/blob/v1.15.1/docs/7-DEVELOPMENT/decisions/ADR-007-optin-runtimes.md)). PDF com `pdfplumber` página a página, juntado num texto só; EPUB com `fast-ebook`; DOCX com python-docx.
- **PDF escaneado falha:** texto vazio vira "Could not extract any text content from this source" ([graphs/source.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/graphs/source.py#L270-L279)). **Medido:** um PDF só de imagem terminou com `status: "failed"`.
- **Sem número de página:** `source_embedding` guarda só `source`, `order`, `content` e `embedding` ([migration 1](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/database/migrations/1.surrealql#L16-L20)); o CHANGELOG da 1.15.1 tirou "page-number citations" da documentação, como recurso que não existia.
- **Status** de um source: `new`/`queued`, `running`, `completed`, `failed`. Com `async_processing=true`, o worker processa; sem, a API processa na hora com limite de 300 s. **Medido:** um txt pequeno ficou pronto em 0,19 s.
- **Consequência:** o nosso app extrai o texto por página (pdfplumber e o Tesseract embutido) e envia um source de texto com marcas `[p. N]`.

## 5. Interface do open-notebook

- Não é necessária: tudo está na API (notebooks, sources, `full_text`, status, retry, notes, search, ask, models, credentials). **Medido:** notebook, upload, status e busca sem a interface.
- Mostrá-la exigiria o Node ≥ 20.9 com o build `standalone`; o navegador chamaria a API no endereço que `/config` devolve, com a porta **5055 fixa** no código quando falta `API_URL` ([route.ts](https://github.com/lfnovo/open-notebook/blob/v1.15.1/frontend/src/app/config/route.ts#L63-L100)), e a interface consulta `/api/config`, que busca o `pyproject.toml` no GitHub ([version_utils.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/utils/version_utils.py)). Descartado.

## 6. Embeddings, busca e Ask

- **Busca de texto** (`type: "text"`): não precisa de modelo; BM25 do SurrealDB com stemmer inglês ([ai-context-rag.md](https://github.com/lfnovo/open-notebook/blob/v1.15.1/docs/2-CORE-CONCEPTS/ai-context-rag.md)); devolve `id`, `parent_id`, `title` e `relevance`, sem trecho ([migration 24](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/database/migrations/24.surrealql)).
- **Busca vetorial:** exige o modelo de embedding padrão, ou responde 400 ([search.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/api/routers/search.py#L31-L37)). É uma varredura de cosseno, sem índice vetorial.
- **Ask:** exige três modelos de linguagem (`strategy_model`, `answer_model`, `final_answer_model`) e o de embedding ([api/models.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/api/models.py#L84-L93)). `/api/search/ask/simple` devolve `{"answer", "question"}`; as citações são `[source:id]` no texto, apontando para o source inteiro ([ask.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/graphs/ask.py#L131-L160)).
- **Provedores** aceitos por `/api/credentials`: openai, anthropic, google, groq, mistral, deepseek, xai, openrouter, ollama, `openai_compatible` e outros ([api/models.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/api/models.py#L591-L616)).
- **Configuração por REST:** `POST /api/credentials` (`provider: openai_compatible`, `modalities: ["embedding"]`, `base_url`), `POST /api/models` (`type: embedding`, `credential`) e `PUT /api/models/defaults` (`default_embedding_model`). Endereços locais são aceitos; só link-local e metadados são bloqueados ([url_validation.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/utils/url_validation.py)). Modelos sem credencial usam as variáveis de ambiente do provedor ([ai/models.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/ai/models.py#L223-L266)).
- **Consequência:** um processo nosso, dentro do pacote de estudo, serve `/v1/embeddings` compatível com OpenAI em `127.0.0.1`; a chave da IA do usuário vai por variável de ambiente e nunca é gravada no banco.

## 7. Modelo de embeddings

- **fastembed 0.9.1** (Apache-2.0) depende de onnxruntime, tokenizers e `huggingface-hub`, e baixa modelos por padrão ([utils.py](https://github.com/qdrant/fastembed/blob/main/fastembed/common/utils.py)). Preferimos onnxruntime + tokenizers diretos: sem `huggingface-hub` e sem caminho de rede no código; o mean pooling é trivial.
- **onnxruntime 1.31.1:** 43,6 MB instalado no Windows, 64,5 MB no Linux ([PyPI](https://pypi.org/pypi/onnxruntime/json)); no Windows exige o runtime do VC++ ([ORT install](https://github.com/microsoft/onnxruntime/blob/gh-pages/docs/install/index.md)).
- **Modelo:** `paraphrase-multilingual-MiniLM-L12-v2` quantizado (Apache-2.0, 384 dimensões; 235 MB de ONNX e 17 MB de tokenizer, [HF](https://huggingface.co/Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q)). O `multilingual-e5-small` qint8 (118 MB) exige AVX-512 VNNI e foi descartado.
- **torch + sentence-transformers:** +484 MB (Windows) a +753 MB (Linux) instalados ([download.pytorch.org](https://download.pytorch.org/whl/cpu/torch/)). Descartado.
- **ChromaDB:** telemetria ligada por padrão ([config.py](https://github.com/chroma-core/chroma/blob/main/chromadb/config.py)), contra a regra do projeto. Descartado.

## 8. Motor nativo (fallback)

- **SQLite FTS5** com `unicode61 remove_diacritics 2` vem no Python do uv (python-build-standalone) e no CPython do Windows ([build-sqlite.sh](https://github.com/astral-sh/python-build-standalone/blob/main/cpython-unix/build-sqlite.sh), [sqlite3.vcxproj](https://github.com/python/cpython/blob/3.12/PCbuild/sqlite3.vcxproj)). O stemmer `porter` é só inglês ([fts5](https://www.sqlite.org/fts5.html)): os radicais em português vão numa coluna à parte, calculados pelo `snowballstemmer` (BSD-3, 0,8 MB, [PyPI](https://pypi.org/pypi/snowballstemmer/json)).
- **EPUB:** o ebooklib é AGPL-3.0 ([PyPI](https://pypi.org/pypi/ebooklib/json)); lemos o EPUB com `zipfile` e `html.parser` da biblioteca padrão. **DOCX:** python-docx, MIT. **XLSX** (planilhas do TEC): openpyxl, MIT.

## 9. Custos e riscos medidos

- **Disco:** ambiente travado com 693 MB (**medido**), dos quais 204 MB do `nodejs-wheel-binaries` (via pytubefix) e 77 MB do `imageio-ffmpeg` (via podcast-creator), sem torch. Sem os dois, cerca de 0,4 GB (**inferência**: `--no-install-package` não foi testado).
- **RAM em repouso** (**medido**): SurrealDB 109 MB, API 184 MB, worker 156 MB; cerca de 450 MB.
- **Partida** (**medido**): API pronta em 4,2 s num banco novo (com as 25 migrations) e 1,7 s depois; worker escutando em 1,2 a 2,2 s.
- **Rede a evitar:** `GET /api/config` consulta o GitHub; o tiktoken baixa `o200k_base` na primeira contagem se `TIKTOKEN_CACHE_DIR` não estiver pronto ([token_utils.py](https://github.com/lfnovo/open-notebook/blob/v1.15.1/open_notebook/utils/token_utils.py)).
- **Jobs presos:** um worker morto no meio deixa o job em `running`; `POST /api/sources/{id}/retry` reenvia.
- **Estabilidade da API:** cerca de 25 releases de 14/01/2026 a 03/11/2026; endpoints removidos em versões menores (1.12.0 tirou `POST /api/notebooks/{id}/context`; 1.15.1 tirou `POST /api/commands/jobs`), e a 1.15.0 mudou a cifra das credenciais ([CHANGELOG](https://github.com/lfnovo/open-notebook/blob/v1.15.1/CHANGELOG.md)). Por isso cada versão nova passa pelos testes de contrato antes de virar pacote.
- **Windows:** o suporte nativo é comunitário ("the officially supported route is Docker Compose"); usar `127.0.0.1`, nunca `localhost`.

## 10. Recomendação

Pacote de estudo por sistema (Windows x64 e Linux x64), montado no CI e assinado com Ed25519: Python 3.12 standalone, o código da tag com o ambiente travado sem Node e ffmpeg, o `surreal` 2.x, o servidor de embeddings com o MiniLM, o cache do tiktoken e as licenças. O app baixa uma vez com consentimento, sobe só a API e o worker sob demanda em portas aleatórias de `127.0.0.1` com senha aleatória, pré-processa os livros (texto por página, OCR) e mantém o FTS5 local para os trechos e para quando o open-notebook está fora. As decisões estão em `docs/decisoes-fase7.md`.
