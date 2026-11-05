# 01: Camada de aplicação extraída da CLI

**What to build:** `src/concursos/aplicacao/` com a orquestração que estava nos helpers de `cli/comandos.py`. `Opcoes` ganha `saida`, `interacao` e `ao_progresso`; `ErroDoUsuario` e `ErroDoAmbiente` passam para `concursos/erros.py`; `analisar_todos` aceita `ao_progresso`; `aplicacao.preferencias` lê e grava `[analise]` e `[gui]`.

**Blocked by:** —

**Status:** todo

- [ ] Paridade: `concurso-analise --force` e `scripts/paridade.py retrato` antes e `comparar` depois, sem diferença.
- [ ] Nenhum `tests/test_cli_*.py` muda; `scripts/smoke.py` verde.
- [ ] `aplicacao/` não importa `typer` nem `concursos.cli`, e não chama `print` nem `input` (teste por AST).
- [ ] `ao_progresso` recebe `(concurso, indice, total)` na ordem; com `None`, a saída é a mesma.
- [ ] `preferencias.gravar_analise` recusa limiar fora de 0 a 1 e preserva as outras seções.
