# 09: Documentação e release

**What to build:** README com "Instalação para usuários leigos" (com screenshots) e "Desenvolvimento: build local do executável"; `AGENTS.md` e `docs/modelo.md` atualizados; release `v0.5.0` com os três artefatos e o `SHA256SUMS`; retro.

**Blocked by:** 04, 05, 06, 07, 08

**Status:** documentação pronta e `release.yml` verde nos três sistemas (`v0.5.0-rc2`, release em rascunho com os três artefatos e o `SHA256SUMS`); a tag `v0.5.0` espera o checklist do Windows Sandbox

- [x] Um leitor sem terminal instala seguindo só o README: "Instalação para usuários leigos" (download, SmartScreen, Gatekeeper, AppImage, SHA256SUMS) e "Usar pela janela", com sete telas em `docs/img/gui-*.png`, capturadas de um projeto sintético.
- [x] A seção de desenvolvimento reproduz o build local: o do Linux foi refeito no `manylinux_2_28` e conferido no `debian:12`; os de Windows e macOS repetem os passos do `release.yml`.
- [ ] O gate de máquina limpa foi feito e registrado antes da publicação: o automático passou nos três sistemas (tickets 07 e 08); falta o checklist manual do Windows Sandbox (ticket 07) e abrir o DMG num Mac.

Notas:

- Versão 0.5.0 no `pyproject.toml` e no `uv.lock`; notas da versão em `docs/release-v0.5.0.md`, usadas pelo job `publicar` quando a tag é `v0.5.0`.
- Ao montar os screenshots, apareceram dois problemas da GUI, corrigidos com teste: a lista de concursos com um único candidato e a falta de um jeito de encerrar o app no modo navegador.
- Retro em `.scratch/gui-leigo/retro.md`.
