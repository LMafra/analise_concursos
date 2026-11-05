# 07: Executável e instalador do Windows

**What to build:** `empacotamento/` (launcher, spec, hook de `concursos`, obtenção do Tesseract pelo MSYS2, Inno Setup), `.github/workflows/release.yml` (job Windows), `scripts/smoke.py congelado` e `scripts/smoke_maquina_limpa.ps1`.

**Blocked by:** 03

**Status:** feito no código; falta a primeira execução do `release.yml` no Windows e o checklist no Windows Sandbox

- [x] O bundle carrega os perfis YAML e resolve os entry points `concurso.banca` e `concurso.ocr` (conferido num build Linux local: `--smoke` lista os 9 perfis, e a análise de `scripts/smoke.py` passa com o executável).
- [ ] `concurso-analise --smoke` (congelado) passa com o `PATH` sem Python e sem Tesseract: `scripts/smoke_maquina_limpa.ps1` faz isso no runner do Windows.
- [ ] O instalador instala, cria o atalho, abre e desinstala no Windows Sandbox.
- [x] O nome do artefato traz a versão (`OutputBaseFilename` do Inno); o job imprime o tamanho no resumo para conferir com a faixa.

Notas:

- Dois executáveis no mesmo onedir: `concurso-analise.exe` (janela) e `concurso-analise-cli.exe` (console), porque o executável sem console não escreve a saída da CLI.
- O smoke da janela usa o modo navegador sem abrir navegador; a janela nativa (WebView2) fica para o checklist manual.
- O build Linux local deu 694 MB no onedir (com o grupo `dev` no ambiente, que o CI não instala).
