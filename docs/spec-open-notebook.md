# Spec: integração com o open-notebook, biblioteca, legislação e prática

Os fatos da API estão em `docs/pesquisa-open-notebook.md`; os campos de arquivo, em `docs/modelo.md`.

## Objetivo

Levar os artefatos da análise para uma instância local do [open-notebook](https://github.com/lfnovo/open-notebook), para consultá-los pelo chat dele, e trazer de volta fontes de estudo: livros (projeto `books`), legislação (clone do `ctresb/leis`) e erros do TEC Concursos (projeto `tec-erros`). Tudo opcional: sem configuração, nenhuma saída muda e nenhuma chamada de rede acontece.

## Fase 1: sincronização com o open-notebook

### Comandos

- `concurso-analise notebook enable [--url URL]`: mostra o que vai para a instância e o aviso sobre o provedor de IA dela, pede confirmação (sem terminal, só com `--yes`) e grava `[open_notebook]` na configuração global com `enabled = true` e `consentimento = true`.
- `concurso-analise notebook disable`: grava `enabled = false`.
- `concurso-analise notebook sync [--concurso X] [--candidate N | --all-candidates]`: sincroniza e imprime o resumo. Saída 0 sem falha, 1 com falha parcial, 2 com a instância fora do ar.
- No fim de cada análise, com `enabled` e `consentimento`, a sincronização roda sozinha. Uma falha vira aviso e não muda o código de saída da análise. `--offline` e `--dry-run` desligam a sincronização.

### Mapeamento

| Notebook | Sources (todas `type=text`) | Nota |
|---|---|---|
| `<concurso> — <rótulo>` | `relatorio.md`, `desempenho_por_disciplina.csv`, `desempenho_por_topico.csv`, `questoes.csv`, `edital_estruturado.json` (formatado), `catalogo_edital.md` | `concurso-analise: resumo executivo` |
| `Consolidado — <rótulo>` | `consolidado/desempenho_geral.csv`, `consolidado/comparativo_concursos.md`, `consolidado/relatorio_evolucao.md`; `index.html` só com `incluir_nome` | `concurso-analise: resumo executivo` |

O rótulo é um pseudônimo estável (`candidato 1`, `candidato 2`, na ordem da primeira sincronização) ou, com `incluir_nome = true`, o slug. O `relatorio.html` não vai (duplica o `relatorio.md`).

### Idempotência

- Título da source: `concurso-analise: <concurso>/<arquivo>`.
- Estado em `.concurso/open_notebook.json`, por `url` da instância: pseudônimos, e por `<candidato>/<concurso>` o id do notebook, as sources (`{id, sha256}`) e as notas (`{id, sha256}`). Gravado só quando muda.
- Notebook: id do estado que ainda existe; senão, nome exato entre os não arquivados (o mais antigo, com aviso, se houver vários); senão, cria.
- Source: hash igual e id presente no remoto, pula; hash diferente ou sem estado, apaga e cria; ausente no remoto, cria. Só apaga source com título começando por `concurso-analise:` no notebook do app.
- Nota: pelo título; hash diferente leva a `PUT`, ausente leva a `POST`.

### Decisões

- **Cliente síncrono em `urllib`**: o projeto já usa `urllib` no LLM; nada a ganhar com `httpx` num fluxo sequencial de dezenas de pedidos. O multipart é montado à mão.
- **Idempotência por estado local mais título**: a API não filtra por nome nem atualiza conteúdo; o estado guarda o hash e o título determinístico recupera um estado perdido.
- **Pseudônimo por padrão**: o nome do candidato é dado pessoal e não precisa sair para o chat funcionar.
- **Chave fora do TOML**: `variavel_chave = "OPEN_NOTEBOOK_PASSWORD"`, lida da variável, do keyring ou do `~/.concurso/.env`, como no LLM.
- **`embed = false` e notas `human`**: assim a integração não aciona o provedor de IA configurado no open-notebook.

### Seams de teste

- Transporte: um servidor `ThreadingHTTPServer` falso, com estado em memória (`tests/servidor_open_notebook.py`), recebe os pedidos reais do cliente.
- Mapeamento e estado: funções puras sobre a pasta do candidato.
- CLI: `main([...])` com a configuração global numa `CONCURSO_HOME` temporária.
- Integração real: `@pytest.mark.integration`, pulado sem `OPEN_NOTEBOOK_URL`.

## Fase 2: biblioteca (`books`)

- O `books` envia a estante (menos `Novos`, a lista curada de Rails e `Trash`) para notebooks `Biblioteca — <main> › <sub>`, com `scripts/sync_open_notebook.py` (dry-run por padrão, `--apply`).
- `.concurso/biblioteca.yaml` liga disciplina canônica a categorias da estante e aponta o catálogo `Bookshelf/README.md`.
- O app vincula ao notebook de cada concurso os livros das disciplinas presentes nele, e grava `consolidado/recomendacoes_estudo.md` para os tópicos fracos (n ≥ `N_MINIMO_TOPICO`): busca `type=text` nos notebooks da biblioteca, depois o catálogo local, depois "sem livro na estante". A busca não devolve trecho do texto, por isso a recomendação traz título, notebook e relevância.

## Fase 3: legislação (`ctresb/leis`)

- `[legislacao] repositorio` na configuração global aponta um clone parcial local; nada é baixado pelo app.
- `legislacao.py` extrai citações (Lei, LC, Decreto, Súmula Vinculante, Súmula do TCU, Constituição) dos tópicos do edital e as resolve para arquivos do clone, com aviso para texto não compilado, pequeno demais ou revogado.
- As normas citadas entram nas recomendações e, com o open-notebook ligado, num notebook `Legislação` (uma source por `urn`), vinculadas aos concursos que as citam.

## Fase 4: prática no TEC (`tec-erros`)

- O projeto `tec-erros` (extensão do Chrome, userscript para o Violentmonkey e `caderno.html` offline) exporta `{app: "tec-erros", v: 1, em, erros, cads}`.
- `[pratica] entrada_tec` no `config.toml` do projeto aponta a pasta onde os aparelhos deixam as exportações; `concurso-analise pratica import <arquivo>` copia para lá.
- O app mescla os aparelhos, liga matéria a disciplina canônica (pelos `nomes` da taxonomia) e assunto a tópico do edital (alias perguntado uma vez), e grava `analises/<candidato>/pratica/` e a seção "Prática no TEC" do `index.html`. Prática não entra no parquet nem no `correcao.json`.

## Limites

- Nada de chat, transformações ou embeddings pelo app.
- Nada de rede para o GitHub ou para o TEC.
- Interface interativa (caderno de erros) só no projeto `tec-erros`.
