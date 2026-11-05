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

## Checklist do Windows Sandbox (antes de publicar a release)

O Windows Sandbox (Windows 10 ou 11 Pro, "Recursos do Windows") começa limpo a cada abertura: sem Python, sem Tesseract e sem nada do usuário.

1. Baixe o `concurso-analise-<versão>-windows-x64-setup.exe` da release em rascunho e copie-o para o Sandbox.
2. Abra o instalador: o SmartScreen aparece; "Mais informações" > "Executar assim mesmo" segue.
3. Instale com os padrões. Confira o atalho no menu Iniciar e que nenhuma senha de administrador foi pedida.
4. Abra pelo menu Iniciar: a janela nativa (WebView2) abre, não o navegador. Se o Sandbox não tiver o WebView2, o instalador oferece a página dele, e o app abre no navegador.
5. Aceite a pasta `Documentos\Concursos`, responda às perguntas e crie um concurso soltando o `gabarito.txt` e o `respostas.txt` de `scripts/smoke.py` (dez questões).
6. Analise: a barra avança, e Resultados mostra o relatório com as imagens; "Abrir no navegador" abre o Edge.
7. Sobre: versão certa e "Tesseract: embutido".
8. Feche a janela e confira no Gerenciador de Tarefas que nenhum `concurso-analise.exe` ficou rodando.
9. Desinstale por Configurações > Aplicativos e confira que `%LOCALAPPDATA%\Programs\concurso-analise` sumiu (a pasta do projeto fica).
10. Registre a data, a versão e o resultado aqui, e só então publique a release.
