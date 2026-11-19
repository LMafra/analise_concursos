# Pesquisa: PCI Concursos MCP

Sondagem feita em 2026-11-03 e 2026-11-05 contra o servidor público, com `curl` (JSON-RPC à mão), com o SDK `mcp` 2.3.0 e com um navegador real na página de uma prova. As respostas gravadas estão em `tests/fixtures/pci/` (regravadas por `scripts/gravar_fixtures_pci.py`).

## Servidor

- URL: `https://mcp.pciconcursos.com.br/mcp` (transporte Streamable HTTP).
- `initialize` devolve `serverInfo` `{"name": "Concursos Públicos Brasil", "version": "1.0.0"}`, `protocolVersion` `2025-06-18` e `capabilities.tools.listChanged = false`.
- Sem sessão: a resposta é `application/json` (não SSE) e não traz `Mcp-Session-Id`. Sem autenticação.
- As `instructions` do servidor dizem, entre outras coisas:
  - para saber se as inscrições estão abertas, use os campos calculados (`datas.aberto`, `datas.em_breve`, `datas.dias_ate_fim`, `datas.dias_ate_inicio`), com `meta.data_atual` como data de referência;
  - a busca por cargo não inclui sinônimos: chame uma vez por nome e junte pelo `id`;
  - use só URLs presentes no retorno; para provas, `link` é a página no site, "não há link direto para PDF";
  - com o campo `message`, não houve resultado; não repita a mesma chamada;
  - em `pesquisar_provas`, todas as palavras do termo precisam aparecer.
- Com o SDK 2.x, o servidor só fala o handshake antigo: o `Client` precisa de `mode='legacy'`.

## Ferramentas (`tools/list`)

São cinco, todas com `readOnlyHint: true`:

| Ferramenta | Argumentos | Observação |
|---|---|---|
| `listar_concursos` | `regiao?` (`norte`, `nordeste`, `centro-oeste`, `sudeste`, `sul`), `professores?` (bool) | até 30 concursos; `meta.total_encontrado` e `meta.link_lista` |
| `pesquisar_concursos` | `termo`, `uf?` (`^[a-zA-Z]{2}$`) | título, órgão ou cargo |
| `buscar_por_cargo` | `cargo`, `uf?` | cada palavra casa pelo começo; `cargos` traz só os que casam |
| `buscar_por_cidade` | `uf`, `cidade` | nome livre, normalizado no servidor |
| `pesquisar_provas` | `termo` | todas as palavras obrigatórias; um ano no termo filtra o ano |

`buscar_apostilas` não está no `tools/list`. Chamada direto, responde com `meta.endpoint = "apostilas"` e `total_apostilas: 0`. Fica fora da integração.

## Formato das respostas

`tools/call` devolve `result.content[0]` do tipo `text`, com um JSON:

```json
{"meta": {"total": 81, "timestamp": 1793757253, "data_atual": "2026-11-03", "endpoint": "cargo",
          "parametros": {"cargo": "analista", "cargo_search": "+analist*"},
          "link_lista": "https://www.pciconcursos.com.br/vagas/analista"},
 "data": [...], "errors": []}
```

Concurso (`buscar_por_cargo`, `buscar_por_cidade`, `listar_concursos`, `pesquisar_concursos`):

```json
{"id": 296055, "titulo": "Câmara de Caxambu", "cargos_resumo": "...", "cargos": ["ANALISTA CONTÁBIL"],
 "cargos_total": 3, "vagas_salario": "5 vagas até R$ 3.457,85", "formacao": "Médio / Superior",
 "regiao": "SUDESTE", "uf": "MG",
 "datas": {"inicio": "2026-12-28", "fim": "2027-01-28", "texto": "", "aberto": false, "em_breve": true,
           "dias_ate_inicio": 55, "dias_ate_fim": 86},
 "noticia": {"id": 296055, "titulo": "...", "link": "https://www.pciconcursos.com.br/noticias/...", "imagem": "..."}}
```

Prova anterior (`pesquisar_provas`):

```json
{"id": 20549582, "descricao": "Auditor Fiscal", "orgao": "Receita Federal", "ano": 2014,
 "organizadora": "ESAF", "link": "https://www.pciconcursos.com.br/provas/download/auditor-fiscal-receita-federal-esaf-2014"}
```

- Sem resultado: `data: []` e `message` com a explicação (ex.: "Nenhuma prova encontrada para ...").
- Argumento inválido: `isError: true` e texto livre em vez de JSON ("Erro ao executar a tool: UF inválida. Use 2 letras minúsculas, ex: sp.").
- O concurso não traz banca nem link de edital; a notícia linka, no máximo, a home da banca.

## Arquivos das provas

- A página `/provas/download/<slug>` lista os arquivos em `<a class="prova-pdf-link" data-code="..." data-arquivo="p1_....pdf" data-acao="ver|baixar|compartilhar">`, sem `href` real.
- Os links só aparecem depois do captcha Cloudflare Turnstile: o script da página faz `POST /provas/link` com `prova_code` e `cf-turnstile-response` e recebe uma URL por arquivo, no formato `/provas/<id>/<hash>/<arquivo>.pdf`. O `<id>` é o mesmo do `pesquisar_provas`.
- Num navegador real, o Turnstile passou sem interação.
- O `robots.txt` tem `Disallow: /*.pdf` e `Disallow: /pdf/`; páginas HTML (`/provas/`, `/noticias/`) são permitidas.

Consequência: o app lê a página HTML (lista de `data-arquivo`), mas nunca chama `/provas/link` nem monta URLs de PDF. O download é do usuário, no navegador dele; a CLI só importa o arquivo da pasta de downloads.

## SDK `mcp` 2.3

- `from mcp import Client`; `Client(url, mode='legacy', read_timeout_seconds=..., cache=None)` como gerenciador de contexto assíncrono.
- `await client.list_tools()` devolve `.tools` (cada uma com `.name`); `await client.call_tool(nome, argumentos)` devolve `CallToolResult` com `.is_error` e `.content` (`TextContent.text`).
- Em teste, `Client(MCPServer(...))` conecta em processo (`from mcp.server.mcpserver import MCPServer`), sem rede.
- O SDK traz `httpx`, `anyio`, `pydantic`, `starlette` e `uvicorn`: por isso fica no extra `concurso-analise[pci]`.
