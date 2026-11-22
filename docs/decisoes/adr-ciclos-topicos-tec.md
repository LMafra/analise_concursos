# ADR: quebra dos ciclos `topicos`↔`dicionario_topicos` e `pratica_tec`↔`tec_estatisticas`

## Status

Aceito (2026-11-19).

## Contexto

Dois ciclos mútuos de import (detectados por AST, inclusive imports dentro de função) fragilizavam refactors. `pydeps --show-cycles` não os listava de forma confiável neste host.

## Decisão

1. **Tópicos:** constantes e funções puras em `analytics/tipos_topicos.py`. `sugerir_topicos` recebe expansão opcional. `sugerir_com_dicionario` / `avaliar_ganho` recebem o sugeridor como callable; quem junta é `pipeline` / `aplicacao` / `pratica`. Nenhum dos dois módulos importa o outro.
2. **TEC:** constantes de arquivo/resultado em `pratica/constantes.py`. `tec_estatisticas` importa só a folha; `pratica_tec` importa `markdown_resumo`.

## Consequências

Gate AST + `import-linter` (dois sentidos em tópicos; `tec_estatisticas` ↛ `pratica_tec`) proíbem o retorno do ciclo. Sem mudança de schema nem de saída observável.
