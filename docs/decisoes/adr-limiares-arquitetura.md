# ADR: limiares e dívida congelada do gate de arquitetura

## Status

Aceito (2026-11-19).

## Contexto

Metas: 0 funções com CC > 15, 0 ciclos, eferência do `pipeline` ≤ 12, MI ≥ 30 nos 4 módulos que estavam em 0.00, cobertura ≥ baseline. Sem lista de dívida, o CI quebra no primeiro dia.

## Decisão

- `docs/arquitetura/limiares.toml` lista dívida CC/MI com `issue` e `prazo`.
- `scripts/verificar_arquitetura.py` falha se: CC > 15 fora da dívida; CC da dívida sobe; ciclo AST; eferência do `pipeline` > 12; MI abaixo do piso de falha sem dívida; cobertura global abaixo do piso.
- Aviso (não falha) se MI < 30 ou dívida órfã (função já ≤ 15).
- Job CI Ubuntu / Python 3.12 separado da matriz multi-SO.

## Consequências

A lista só encolhe. PRs que baixam CC removem a linha correspondente no mesmo commit.
