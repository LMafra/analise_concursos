# Pesquisa: API do open-notebook

Fonte consultada em 03/11/2026: o código do [open-notebook](https://github.com/lfnovo/open-notebook) na versão 1.15.0 (commit `a0f6f30`, de 04/10/2026). Cada fato cita o arquivo do repositório de onde saiu; não há documentação oficial da API além do `/docs` (OpenAPI) que a própria instância serve.

## Conexão e autenticação

- A API é FastAPI, na porta `5055`, com os routers montados em `/api` (`api/main.py`, `app.include_router(..., prefix="/api")`).
- `GET /health` fica fora de `/api` e devolve `{"status": "healthy"}` (`api/main.py`).
- A autenticação é opcional (`api/auth.py`, `PasswordAuthMiddleware`): sem `OPEN_NOTEBOOK_PASSWORD` no servidor, tudo passa. Com ela, cada pedido precisa de `Authorization: Bearer <senha>`; sem o header, a resposta é 401 `{"detail": "Missing authorization header"}`, e com a senha errada, 401 `{"detail": "Invalid password"}`. `/`, `/health`, `/docs`, `/openapi.json` e `/redoc` não pedem senha.
- O corpo de um pedido tem limite de 100 MB por padrão (`api/middleware.py`, `DEFAULT_MAX_UPLOAD_SIZE_MB = 100`), mudado no servidor por `OPEN_NOTEBOOK_MAX_UPLOAD_SIZE_MB`; acima disso, 413.
- Os erros seguem o FastAPI: `{"detail": "<mensagem>"}` com 400, 404, 422 ou 500.

## Notebooks (`api/routers/notebooks.py`, `api/models.py`)

- `GET /api/notebooks?archived=<bool>&order_by=<campo direção>` lista todos. `order_by` aceita só `name`, `created` ou `updated` com `asc`/`desc`. Não há filtro por nome.
- `GET /api/notebooks/{id}` devolve um notebook ou 404.
- `POST /api/notebooks` recebe `{"name", "description"}` (JSON) e devolve `NotebookResponse`: `{id, name, description, archived, created, updated, source_count, note_count}`. O servidor não impede dois notebooks com o mesmo nome.
- `POST /api/notebooks/{nb}/sources/{src}` vincula uma source existente a um notebook; é idempotente (confere o vínculo antes de criar) e devolve `{"message"}`. `DELETE` no mesmo caminho remove só o vínculo.

## Sources (`api/routers/sources.py`, `api/models.py`)

- `POST /api/sources` é multipart/form (`parse_source_form_data`). Campos: `type` (obrigatório: `text`, `link` ou `upload`), `notebooks` (JSON de ids), `url`, `content`, `title`, `transformations` (JSON), `embed`, `delete_source`, `async_processing` (os três como texto `"true"`/`"false"`) e `file`. `POST /api/sources/json` aceita o mesmo em JSON, sem arquivo.
- Com `async_processing=false`, o servidor processa na hora, com limite de 300 s (`_create_source_sync_path`, `timeout=300`), e devolve `SourceResponse`: `{id, title, topics, asset, full_text, embedded, embedded_chunks, file_available, created, updated, command_id, status, processing_info, notebooks}`. Com `true`, devolve logo e o progresso sai em `GET /api/sources/{id}/status`: `{status, message, processing_info, command_id}`, com `status` em `queued`, `running`, `completed`, `failed` ou `unknown` (e `null` para source antiga, já concluída).
- `embed=false` não gera embeddings; nada vai ao modelo de embedding do servidor. Sem `transformations`, nenhum LLM processa a source.
- `GET /api/sources?notebook_id=&limit=&offset=&sort_by=&sort_order=` pagina com `limit` de 1 a 100 (padrão 50). A lista (`SourceListResponse`) não traz o `full_text`.
- `GET /api/sources/{id}` devolve o `SourceResponse` com o `full_text`.
- `PUT /api/sources/{id}` muda só `title` e `topics` (`SourceUpdate`). Não há como trocar o conteúdo: para atualizar, apaga e cria de novo.
- `DELETE /api/sources/{id}` apaga a source.

## Notas (`api/routers/notes.py`)

- `GET /api/notes?notebook_id=` lista as notas do notebook (`NoteResponse`: `{id, title, content, note_type, created, updated}`).
- `POST /api/notes` recebe `{"title", "content", "note_type", "notebook_id"}`. `note_type` é `human` ou `ai`; uma nota `ai` sem título faz o servidor chamar o LLM para gerar um, por isso o app usa `human` com título.
- `PUT /api/notes/{id}` muda `title`, `content` ou `note_type`. `DELETE /api/notes/{id}` apaga.

## Busca (`api/routers/search.py`, migração `25.surrealql`)

- `POST /api/search` recebe `{"query", "type": "text"|"vector", "limit" (1 a 1000), "search_sources", "search_notes", "minimum_score", "notebook_id", "notebook_ids" (até 50)}` e devolve `{"results": [...], "total_count", "search_type"}`.
- `type=text` usa o índice de texto completo do SurrealDB (`fn::text_search`) e não exige modelo de embedding nem LLM. `type=vector` exige um modelo de embedding configurado (400 sem ele).
- Cada resultado de `fn::text_search` tem só `id`, `parent_id`, `title` e `relevance`. O `id` pode ser da source, de um chunk ou de um insight; `parent_id` é sempre a source (ou a nota). Não há trecho do texto encontrado no resultado: para mostrar um trecho, seria preciso ler o `full_text` da source.
- Em textos grandes com caracteres multibyte, o realce do SurrealDB pode falhar ("position overflow"); o servidor então tenta a busca vetorial e, sem modelo de embedding, devolve 500.

## Chat (`api/routers/chat.py`)

- `POST /api/chat/sessions` recebe `{"notebook_id", "title", "model_override"}`; `POST /api/chat/execute` recebe `{"session_id", "message", "context", "model_override"}`. Os dois exigem um modelo de linguagem configurado no open-notebook. Ficam fora da integração: o chat é usado pela interface do open-notebook.

## Privacidade

- O open-notebook roda na máquina do usuário, mas repassa conteúdo ao provedor de IA configurado nele: embeddings (quando `embed=true`), transformações, títulos de notas `ai`, chat e busca vetorial. Com `embed=false`, `note_type=human` e busca `text`, a integração não aciona nenhum provedor.
