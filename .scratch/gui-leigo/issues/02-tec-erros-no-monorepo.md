# 02: tec-erros no monorepo

**What to build:** o código do `tec-erros` (sem `dist/`) em `tec-erros/`, fixtures do contrato v1 em `tests/contrato_tec/` lidas por `tec-erros/test/contrato.test.js` e por `tests/test_contrato_tec.py`, e um job com Node no CI.

**Blocked by:** —

**Status:** todo

- [ ] `node --test` (em `tec-erros/`) e `uv run pytest tests/test_contrato_tec.py` verdes sobre as mesmas fixtures.
- [ ] A mesclagem de duas exportações dá o mesmo resultado nos dois lados (ids, `ds`, `v`, `com` mais longo, cadernos por maior `res`).
- [ ] `node scripts/build.mjs` gera `tec-erros/dist/`, fora do git.
- [ ] `.dockerignore` exclui `tec-erros/`.
