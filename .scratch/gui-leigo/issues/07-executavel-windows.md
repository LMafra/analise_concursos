# 07: Executável e instalador do Windows

**What to build:** `empacotamento/` (launcher, spec, hook de `concursos`, obtenção do Tesseract pelo MSYS2, Inno Setup), `.github/workflows/release.yml` (job Windows), `scripts/smoke.py congelado` e `scripts/smoke_maquina_limpa.ps1`.

**Blocked by:** 03

**Status:** todo

- [ ] O bundle carrega os perfis YAML e resolve os entry points `concurso.banca` e `concurso.ocr`.
- [ ] `concurso-analise --smoke` (congelado) passa com o `PATH` sem Python e sem Tesseract.
- [ ] O instalador instala, cria o atalho, abre e desinstala no Windows Sandbox.
- [ ] O nome do artefato traz a versão; o tamanho fica na faixa de `docs/pesquisa-gui.md`.
