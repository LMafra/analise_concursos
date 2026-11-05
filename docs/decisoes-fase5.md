# Decisões da fase 5

Registro curto das escolhas da fase 5, com o contexto e as alternativas descartadas. Os fatos citados estão em `docs/pesquisa-gui.md`.

## 1. NiceGUI como framework da interface

- **Contexto:** o app já gera HTML e PNG; o público é leigo; os testes rodam em `pytest`.
- **Decisão:** NiceGUI 4.x, com janela nativa (pywebview) no Windows e no macOS.
- **Por quê:** serve o relatório existente sem reescrita; tem guia e hook oficiais para o PyInstaller; a fixture `user` testa a interface em processo, sem navegador.
- **Descartado:**
  - Flet: `flet build` exige Flutter (e Visual Studio no Windows), o `flet-webview` não roda no Windows nem no Linux (o relatório abriria fora do app) e os testes só rodam contra o app construído.
  - Tauri com Python como sidecar: três toolchains (Rust, Node, Python), interface reescrita em JS, e o sidecar tem o mesmo tamanho do bundle PyInstaller.
- **Consequência:** a GUI é um servidor web local. O item "Interface web" do fora de escopo passa a excluir só o servidor acessível pela rede ou multiusuário; a GUI fica em `127.0.0.1`.

## 2. Linux em modo navegador

- **Contexto:** a janela nativa no Linux depende de PyGObject e WebKitGTK congelados, e o PyInstaller não tem hook para `gi.repository.WebKit2`.
- **Decisão:** no Linux, a GUI abre no navegador padrão, em `127.0.0.1` e porta livre, com seletor de pasta do lado do servidor.
- **Descartado:** `pywebview[gtk]` no Linux, pelo risco no empacotamento.

## 3. PyInstaller onedir com instalador

- **Contexto:** na medição, o onefile abriu em 5,4 s (extrai 630 MB a cada execução) e o onedir em 2,6 s. O onefile com `.app` está obsoleto no macOS e será bloqueado no PyInstaller 7.
- **Decisão:** onedir em todos os sistemas, distribuído por instalador.
- **Descartado:** onefile `.exe` solto.

## 4. Inno Setup no Windows

- **Contexto:** o runner `windows-latest` já traz o Inno Setup; o NSIS precisaria ser instalado no CI.
- **Decisão:** Inno Setup, com atalho no menu Iniciar, desinstalador e verificação do WebView2.
- **Descartado:** NSIS (passo extra no CI, sem ganho para o usuário) e `.msi` (WiX, mais complexo).

## 5. Tesseract embutido

- **Contexto:** o usuário leigo não instala Tesseract; o app só chama `pytesseract.image_to_string(..., lang='por')` e procura o binário com `shutil.which`.
- **Decisão:** o Tesseract vai no bundle, sem as ferramentas de treino, com `por.traineddata` do `tessdata_fast` (o mesmo modelo do pacote `tesseract-ocr-por` do Debian e do Ubuntu, para o OCR não mudar). O launcher põe o binário no início do `PATH` e define `TESSDATA_PREFIX`; a lógica não muda. Origem: MSYS2 no Windows, build enxuto com `delocate` no macOS, AppImage oficial extraído no Linux.
- **Descartado:**
  - Baixar o Tesseract na primeira execução: exige rede e quebra a regra de nenhuma chamada sem opt-in.
  - `tessdata_best`: mais lento e mudaria a leitura em relação ao Tesseract do sistema.

## 6. Sem assinatura de código na primeira versão

- **Contexto:** a Apple cobra 99 USD por ano; no Windows, o Azure Artifact Signing não aceita pessoa física no Brasil, e um certificado OV custa de 150 a 300 USD por ano.
- **Decisão:** artefatos sem assinatura, com `SHA256SUMS` na release e o passo a passo do SmartScreen e do Gatekeeper no README.
- **Consequência:** a assinatura fica como item futuro.

## 7. Dependências da GUI num extra

- **Contexto:** o `uvx` instala só as dependências do projeto, e a CLI deve continuar leve.
- **Decisão:** extra `[gui]` com `nicegui[native]`; o executável instala `.[gui,llm,pci]`.
- **Descartado:** NiceGUI como dependência principal.

## 8. Camada de aplicação extraída da CLI

- **Contexto:** a orquestração (cadeia da análise, escolha de candidato, prática, radar, sincronização, importação de simulado) estava nos helpers privados de `cli/comandos.py`, misturada com `typer.echo`.
- **Decisão:** pacote `concursos.aplicacao`, usado pela CLI e pela GUI. As mensagens vão para `Opcoes.saida` (na CLI, `typer.echo`), as perguntas para `Opcoes.interacao` e o progresso para `Opcoes.ao_progresso`. Os erros (`ErroDoUsuario`, `ErroDoAmbiente`) passam para `concursos.erros`.
- **Descartado:** a GUI chamar `concursos.cli.main([...])` como subprocesso (sem perguntas interativas nem progresso) e reescrever a orquestração na GUI (duplicaria regra).

## 9. tec-erros no monorepo

- **Contexto:** o `tec-erros` não estava em nenhum repositório, e a regra de mesclagem do contrato v1 existe em JavaScript (`core/nucleo.js`) e em Python (`pratica_tec.py`).
- **Decisão:** o código vem para `tec-erros/` na raiz. As fixtures do contrato ficam em `tests/contrato_tec/` e passam pelos dois testes; o CI ganha um job com Node; o build da extensão alimenta o instalador.
- **Descartado:** repositório próprio com releases (duas versões para casar) e copiar o `dist/` à mão.
- **Para depois:** a ponte ao vivo da extensão com a GUI (mudaria a promessa de "nenhum pedido de rede" da extensão) e a publicação na Chrome Web Store.
