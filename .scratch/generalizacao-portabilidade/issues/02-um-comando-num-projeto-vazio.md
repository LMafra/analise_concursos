# 02: Um comando num projeto vazio

**What to build:** `uvx --from . concurso-analise` roda o pipeline atual sem subcomando, a partir de qualquer pasta, sem depender de um `pyproject.toml` por perto.

- **Caminhos:** um resolvedor de contexto decide a pasta global (`~/.concurso/`, ou `CONCURSO_HOME`) e o projeto (`./.concurso/`, ou `--data-dir`).
- **Flags:** `--yes`, `--dry-run`, `--quiet`, `--verbose` e `--force`.
- **Erros:** saem em português, com uma linha `dica:` e sem traceback. O traceback vai para o log técnico.
- **Executável antigo:** `concursos` continua funcionando como alias, com aviso de obsoleto.

**Blocked by:** 01

**Status:** done

- [x] A distribuição se chama `concurso-analise`, tem os executáveis `concurso-analise` e `concursos`, e declara `requires-python >=3.11,<3.13`, com lock resolvido para 3.11 e 3.12.
- [x] Sem subcomando, o comando analisa as provas da pasta configurada (padrão `./provas`), escreve em `./analises` e, numa segunda execução, registra "sem mudanças".
- [x] Sem a pasta de provas, sai com código 1 e mostra até duas linhas: onde a pasta era esperada e uma `dica:` com o comando. Não aparece `Traceback`.
- [x] Uma exceção inesperada mostra uma mensagem genérica com o caminho do log. O log fica em `<pasta global>/logs/`.
- [x] `--dry-run` não grava nada e lista os concursos que seriam processados.
- [x] `concursos analisar` e `concursos status` continuam funcionando e avisam que estão obsoletos.
- [x] A suíte atual continua verde, e a paridade com os dados reais não mostra diferença.
