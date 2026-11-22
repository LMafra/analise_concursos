# ADR: fachada do `pipeline` (opção A)

## Status

Aceito (2026-11-19).

## Contexto

`pipeline` concentrava ~35 imports internos `concursos.*` (SPOF da análise). Opção B (portas/`Protocol` injetados) mudaria assinaturas de `analisar_*` e aumentava risco de regressão.

## Decisão

Opção A: pacote `concursos.pipeline` com `__init__.py` fino (reexporta API pública) e implementação em `pipeline/nucleo.py`. `ARQUIVO_RESPOSTAS` da folha vive em `artefatos.py`. Callers fora de `aplicacao/` e testes não importam `pipeline` (`cli/legado` passa por `aplicacao.analise`).

Métrica do gate: eferência **direta** de `pipeline/__init__.py` para módulos `concursos.*` externos ≤ 12.

## Consequências

Eferência pública cai sem reescrever o fluxo de correção. As etapas privadas moram em `pipeline/etapas/` (`leitura`, `classificacao`, `regras`, `constantes`); `nucleo` só orquestra. Tempo de `analyze` no exemplo: `docs/arquitetura/tempo-analyze-exemplo.json` (regressão > 15% bloqueia).
