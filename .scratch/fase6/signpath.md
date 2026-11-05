# Candidatura à SignPath Foundation

**Status:** a enviar pelo mantenedor em https://signpath.org/apply.html (exige login e MFA; o agente não envia).

## Pré-requisitos

- [x] Licença OSI no repositório (`LICENSE`, MIT) e em `pyproject.toml`.
- [x] Repositório público: https://github.com/LMafra/analise_concursos
- [x] Release já publicada no formato a assinar (`v0.5.0`: setup do Inno, onedir do PyInstaller).
- [x] Build automatizado em runner hospedado pelo GitHub (`.github/workflows/release.yml`).
- [x] Funcionalidade descrita na página de download (README, "Instalação para usuários leigos").
- [x] Política de assinatura publicada no README ("Política de assinatura de código").
- [ ] MFA ligado no GitHub e na conta SignPath de cada pessoa da equipe.
- [x] `ProductName` e `ProductVersion` nos binários (`empacotamento/windows/versao.py`, `VersionInfo*` no Inno).

## Respostas do formulário

- **Project name:** concurso-analise
- **Repository:** https://github.com/LMafra/analise_concursos
- **Homepage / download page:** https://github.com/LMafra/analise_concursos#instalação-para-usuários-leigos
- **License:** MIT
- **Description:** Desktop tool (Windows/Linux) that grades Brazilian civil-service exams from the candidate's answer sheet, reads the official notice (edital) and shows performance by subject over time. Local-only GUI (NiceGUI on 127.0.0.1), bundled Python and Tesseract.
- **Artifacts to sign:** `concurso-analise.exe` and `concurso-analise-cli.exe` (PyInstaller bootloaders built in CI from this repository), and the Inno Setup installer `concurso-analise-<version>-windows-x64-setup.exe`. Third-party DLLs (Python, Tesseract/MSYS2) stay unsigned.
- **Build system:** GitHub Actions (`windows-latest`), workflow `release.yml`, triggered by `v*` tags.
- **Team:** LMafra (author, reviewer, approver).

## Configuração depois da aprovação

1. Na SignPath: projeto `concurso-analise`, Trusted Build System "GitHub.com" ligado ao projeto, GitHub App instalado no repositório.
2. Artifact configurations:
   - `executaveis`: zip com `concurso-analise.exe` e `concurso-analise-cli.exe` na raiz; assinar ambos com Authenticode; restrição de metadados `ProductName=concurso-analise`.
   - `instalador`: o `setup.exe` solto; Authenticode; mesma restrição.
3. Signing policies: `release-signing` (aprovação manual) e `test-signing`.
4. No GitHub: secret `SIGNPATH_API_TOKEN` (usuário com papel de submitter) e as variáveis de repositório `SIGNPATH_ORGANIZATION_ID` e `SIGNPATH_PROJECT_SLUG`.
5. Rodar o `release.yml` à mão (política `test-signing`) e conferir o gate de assinatura antes da primeira tag.
