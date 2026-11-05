# Pesquisa: interface gráfica e executável por sistema

As fontes foram consultadas em 05/11/2026: documentação oficial, repositórios, issues e releases dos projetos, e o PyPI. Versões e datas vêm das páginas de release ou da API JSON do PyPI. Os números da seção 8 foram medidos neste repositório e não vêm de fonte externa.

## 1. NiceGUI

### Versão e requisitos

- **Versão:** 4.0.0, publicada em 04/11/2026 ([release](https://github.com/zauberzeug/nicegui/releases/tag/v4.0.0), [PyPI](https://pypi.org/project/nicegui/4.0.0/)). Licença MIT.
- **Requisitos da 4.0** ([guia de migração](https://github.com/zauberzeug/nicegui/releases/tag/v4.0.0)):
  - Python 3.11 ou mais novo (a 3.19 aceitava 3.10), o que cabe no 3.11/3.12 do projeto;
  - FastAPI 0.143.1, Chrome/Edge 121 e Safari 17.2;
  - Pillow 13 no extra `matplotlib`;
  - `httpx2` no lugar do `httpx`.
- **Mudanças de comportamento que afetam um app empacotado** ([release 4.0.0](https://github.com/zauberzeug/nicegui/releases/tag/v4.0.0)):
  - `run.cpu_bound` passa a usar "spawn": a função precisa ser importável no processo filho.
  - `WEB_CONCURRENCY` acima de 1 gera `ValueError`.
  - Os IDs no DOM mudam de `c12` para `ng-12`.
- **Segurança recente:**
  - A 3.19.0 remove prefixos de drive do Windows (`C:`) dos nomes de arquivo do `ui.upload`, que podiam escapar da pasta de upload ([GHSA-75w7-4mx9-8qqc](https://github.com/zauberzeug/nicegui/releases/tag/v3.19.0)).
  - A 3.18.0 recusa upload para um `ui.upload` desabilitado ou oculto ([release](https://github.com/zauberzeug/nicegui/releases/tag/v3.18.0)).
- **Extras:** `native = ["pywebview>=5.0.1,<7"]` e `plotly = ["plotly>=5.13,<8.0"]` ([pyproject.toml](https://github.com/zauberzeug/nicegui/blob/main/pyproject.toml)). O pywebview mais recente é o 6.2.1, BSD-3 ([PyPI](https://pypi.org/project/pywebview/6.2.1/)).
- **Tamanho:** o wheel `nicegui-4.0.0-py3-none-any.whl` tem 8,2 MB ([PyPI](https://pypi.org/project/nicegui/4.0.0/#files)). No bundle medido, a pasta `nicegui` ocupa 23 MB (seção 8).

### Modo nativo (`ui.run(native=True)`)

- **Como funciona:**
  - Abre uma janela do pywebview de 800×600, desliga o `show` e procura uma porta livre ([docstring de `ui.run`](https://github.com/zauberzeug/nicegui/blob/main/nicegui/ui_run.py)).
  - A janela roda num processo separado (`multiprocessing`). Por isso, a configuração feita dentro do `if __name__ == '__main__':` é ignorada pela janela ([docs](https://nicegui.io/documentation/section_configuration_deployment#native_mode)).
- **Motor exigido:** Chromium 121+ ou WebKit/Safari 17.2+ ([docs](https://nicegui.io/documentation/section_configuration_deployment#native_mode)).
- **Windows:**
  - O backend EdgeChromium usa o .NET Framework e o WebView2 Runtime ([docs NiceGUI](https://nicegui.io/documentation/section_configuration_deployment#native_mode), [pywebview](https://pywebview.flowrl.com/guide/web_engine.html)).
  - O pywebview prefere o .NET 6+ Desktop Runtime e cai para o .NET Framework 4.6.2 ([instalação](https://pywebview.flowrl.com/guide/installation.html)).
  - O Evergreen WebView2 Runtime faz parte do Windows 11 e "the vast majority of Windows 10 devices" já o têm; a Microsoft recomenda verificar a presença ([distribuição do WebView2](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)).
  - Existe um contorno documentado para o erro com `WebView2Loader.dll`: mover a DLL um nível acima ([docs NiceGUI](https://nicegui.io/documentation/section_configuration_deployment#native_mode), [pywebview #1078](https://github.com/r0x0r/pywebview/issues/1078)).
- **macOS:** usa o `WKWebView` do sistema, por meio do pyobjc ([web engine](https://pywebview.flowrl.com/guide/web_engine.html), [instalação](https://pywebview.flowrl.com/guide/installation.html)).
- **Linux:**
  - É preciso escolher entre `pywebview[gtk]` e `pywebview[qt]`. Com GTK, entram `python3-gi`, `gir1.2-gtk-3.0` e `gir1.2-webkit2-4.1` do sistema ([instalação](https://pywebview.flowrl.com/guide/installation.html)).
  - O extra `nicegui[native]` instala só o `pywebview` ([pyproject.toml](https://github.com/zauberzeug/nicegui/blob/main/pyproject.toml)).
  - Um WebKit antigo quebra o layout: em [#5639](https://github.com/zauberzeug/nicegui/issues/5639), o motor não suportava CSS Cascade Layers.
  - O PyInstaller tem hook para `gi.repository.Gtk`, mas não encontrei hook para `gi.repository.WebKit2`, nem no núcleo ([hooks](https://github.com/PyInstaller/pyinstaller/tree/develop/PyInstaller/hooks)) nem no contrib ([stdhooks](https://github.com/pyinstaller/pyinstaller-hooks-contrib/tree/master/_pyinstaller_hooks_contrib/stdhooks)). Congelar o modo nativo no Linux é a parte menos garantida.
- **Maturidade (issues recentes, todas fechadas):**
  - [#6392](https://github.com/zauberzeug/nicegui/issues/6392): o processo não terminava ao fechar a janela num build sem console (`sys.stdout` igual a `None`). Fechada em 26/10/2026.
  - [#5648](https://github.com/zauberzeug/nicegui/issues/5648), [#6082](https://github.com/zauberzeug/nicegui/issues/6082) e [#6093](https://github.com/zauberzeug/nicegui/issues/6093): `app.native.window_args` era ignorado em apps empacotados.
  - [#1430](https://github.com/zauberzeug/nicegui/issues/1430): "Connection lost" ao abrir o seletor de arquivos no modo nativo. Fechada em 06/2026.
  - [#4899](https://github.com/zauberzeug/nicegui/issues/4899): app empacotado com `nicegui-pack` não abria no macOS.
- **Armazenamento:** `app.storage` grava em `NICEGUI_STORAGE_PATH`, por padrão `.nicegui` na pasta de trabalho. Duas instâncias do mesmo executável sobrescrevem os dados uma da outra ([docs](https://nicegui.io/documentation/section_configuration_deployment#native_mode)).

### Host e porta

- **Host:** o padrão é `127.0.0.1` no modo nativo e `0.0.0.0` no modo navegador ([`ui.run`](https://github.com/zauberzeug/nicegui/blob/main/nicegui/ui_run.py)). Sem `host='127.0.0.1'` explícito, o modo navegador fica exposto na rede local, o que conflita com a regra de dados locais.
- **Porta:**
  - No modo nativo, `native.find_open_port()` varre as portas de 8000 a 8999 e permite várias cópias do executável ao mesmo tempo.
  - No modo navegador, o padrão é 8080, sem varredura ([docs](https://nicegui.io/documentation/section_configuration_deployment#native_mode)).
- **Variáveis de ambiente:** desde a 3.17, `NICEGUI_PORT`, `NICEGUI_HOST` e `NICEGUI_PROTOCOL` definidas e ignoradas geram aviso ([release 3.17.0](https://github.com/zauberzeug/nicegui/releases/tag/v3.17.0)).

### Empacotamento com PyInstaller (`nicegui-pack`)

- **Pré-requisitos:** `ui.run(..., reload=False)` e uma função `root` ou ao menos um `@ui.page` ([docs](https://nicegui.io/documentation/section_configuration_deployment#package_for_installation)).
- **O que o `nicegui-pack` faz:** é um invólucro fino do PyInstaller ([pack.py](https://github.com/zauberzeug/nicegui/blob/main/nicegui/scripts/pack.py)).
  - Chama `python -m PyInstaller`, ou `pyinstaller` no Windows.
  - Acrescenta `--add-data <nicegui>:nicegui`.
  - Repassa `--name`, `--windowed`, `--onefile`, `--onedir`, `--icon`, `--osx-bundle-identifier`, `--clean` e `--noconfirm`.
  - Tem `--dry-run`, que só imprime o comando.
  - O pyinstaller-hooks-contrib também tem um `hook-nicegui.py` com `collect_data_files('nicegui')` ([hook](https://github.com/pyinstaller/pyinstaller-hooks-contrib/blob/master/_pyinstaller_hooks_contrib/stdhooks/hook-nicegui.py)).
- **Ressalvas do `--onefile`** ([docs](https://nicegui.io/documentation/section_configuration_deployment#package_for_installation)):
  - Abre mais devagar, porque descompacta tudo numa pasta temporária a cada execução. A documentação sugere distribuir a pasta do `--onedir` compactada.
  - `--windowed` sem `native=True` deve ser evitado: o usuário fica sem como encerrar o app.
  - No macOS, `--windowed` gera `dist/myapp.app`.
- **`freeze_support()`:**
  - Deve ser a primeira instrução dentro do main guard, para o app empacotado não criar processos em laço.
  - As configurações de `app.native` ficam fora do main guard ([docs](https://nicegui.io/documentation/section_configuration_deployment#package_for_installation)).
- **Nuitka:** é alternativa documentada, com `--include-package=nicegui --include-package-data=nicegui` ([docs](https://nicegui.io/documentation/section_configuration_deployment#package_for_installation)).

### Upload e seletor de pasta

- **`ui.upload`:**
  - Tem `max_file_size`, `save()` e o evento `on_upload`. O arquivo chega como `e.file`, lido com `await e.file.text()` ([docs](https://nicegui.io/documentation/upload)).
  - Arquivo grande passa pelo multipart do Starlette. A documentação mostra como aumentar o limite mantido em RAM ([docs](https://nicegui.io/documentation/upload)).
  - Mesmo no app local, o PDF é copiado do disco pelo navegador para o servidor.
- **Seletor nativo:**
  - `await app.native.main_window.create_file_dialog(dialog_type, directory, allow_multiple, save_filename, file_types)` devolve uma tupla de caminhos ([native.py](https://github.com/zauberzeug/nicegui/blob/main/nicegui/native/native.py)).
  - Para escolher pasta, usa-se `webview.FileDialog.FOLDER` do pywebview, ao lado de `OPEN` e `SAVE` ([webview/__init__.py](https://github.com/r0x0r/pywebview/blob/master/webview/__init__.py)).
  - Só existe no modo nativo.
  - No Windows com .NET 6 a 8, o seletor de pasta devolve uma pasta só, mesmo com `allow_multiple=True` ([web engine](https://pywebview.flowrl.com/guide/web_engine.html)).
- **Arrastar e soltar:** o evento nativo `drop` entrega `files`, uma lista de caminhos do sistema de arquivos ([docs](https://nicegui.io/documentation/section_configuration_deployment#native_window_events)).
- **Modo navegador:** não há seletor nativo. O exemplo oficial [local_file_picker](https://github.com/zauberzeug/nicegui/tree/main/examples/local_file_picker) navega pelo disco do lado do servidor.

### Testes

- **Plugin:** o plugin pytest se ativa com `-p nicegui.testing.plugin`, ou só com `user_plugin` ou só com `screen_plugin` ([docs](https://nicegui.io/documentation/section_testing)).
- **Configuração:** pede `asyncio_mode = auto` e `main_file` no `pytest.ini` ou no `pyproject.toml`. `main_file = ""` dispensa um arquivo principal, e cada teste registra as próprias páginas ([docs](https://nicegui.io/documentation/section_testing)).
- **Fixture `user`:**
  - Simula o navegador em Python, no mesmo loop do app. É rápida como teste unitário e não precisa de Selenium. A documentação recomenda usá-la sempre que der ([docs](https://nicegui.io/documentation/user)).
  - O upload se testa com `upload.handle_uploads([ui.upload.SmallFileUpload(...)])` ([docs](https://nicegui.io/documentation/user)).
  - O escopo do loop do asyncio deve ficar em `function` ([docs](https://nicegui.io/documentation/user)).
  - Na 4.0, a fixture usa tipos do `httpx2` ([release](https://github.com/zauberzeug/nicegui/releases/tag/v4.0.0)).
- **Fixture `screen`:** abre um navegador headless de verdade (Selenium). É lenta, e a documentação recomenda usá-la só quando for indispensável ([docs](https://nicegui.io/documentation/screen)).

## 2. Flet

- **Versão:**
  - Estável: 1.0.5, de 21/10/2026 ([release](https://github.com/flet-dev/flet/releases/tag/v1.0.5), [PyPI](https://pypi.org/project/flet/1.0.5/)).
  - A 1.1 está em `dev4`, de 03/11/2026 ([releases](https://github.com/flet-dev/flet/releases)).
  - A `1.1.0.dev2` empacota CPython 3.12.16, 3.13.18 e 3.14.10 e assina o cliente Windows com Azure Artifact Signing ([release](https://github.com/flet-dev/flet/releases/tag/v1.1.0.dev2)).
- **`flet build`** ([publish](https://flet.dev/docs/publish/)):
  1. Gera um projeto Flutter em `build/flutter`.
  2. Empacota o Python com `serious_python`, instalando as dependências do pypi.org e do pypi.flet.dev para a plataforma alvo.
  3. Roda `flutter build`.
  - O Flutter SDK é obrigatório e baixado automaticamente.
  - Não há compilação cruzada: macOS só se gera no macOS, e Windows só no Windows ([matriz](https://flet.dev/docs/publish/#platform-matrix)).
  - No Windows, exige o Visual Studio com "Desktop development with C++" ([Windows](https://flet.dev/docs/publish/windows/)).
  - No Linux, exige `clang`, `lld`, `libgtk-3-dev`, GStreamer e `libmpv` no build ([Linux](https://flet.dev/docs/publish/linux/)).
- **Dependências nativas no desktop:**
  - A instalação a partir do código-fonte já é permitida no desktop. O índice pypi.flet.dev existe para Android e iOS ([publish](https://flet.dev/docs/publish/#source-packages), [pacotes binários](https://flet.dev/docs/reference/binary-packages-android-ios/)).
  - Portanto, os wheels normais do PyPI (opencv, scipy, pyarrow) devem servir. Não encontrei teste oficial desse conjunto no desktop.
  - A issue [#6570](https://github.com/flet-dev/flet/issues/6570) mostra `opencv-python` falhando no `flet build apk`, que é mobile.
- **Encerramento:** um app gerado pelo `flet build` termina imediatamente. `atexit`, `__del__` e buffers não gravados não têm garantia de execução ([publish](https://flet.dev/docs/publish/#how-a-built-app-terminates)).
- **`flet pack`:**
  - Usa PyInstaller, gera só desktop e roda o Python ao lado do cliente Flet pré-compilado.
  - As dependências vêm da análise estática do PyInstaller. Para macOS, gera sempre `.app` ([flet pack](https://flet.dev/docs/publish/using-pyinstaller/)).
  - No desenvolvimento, o pacote `flet-desktop` baixa o cliente Flutter na primeira execução e o guarda em cache ([código](https://github.com/flet-dev/flet/blob/main/sdk/python/packages/flet-desktop/src/flet_desktop/__init__.py)).
- **Relatório HTML:** o `flet-webview` não roda no Windows nem no Linux, só no macOS, iOS, Android e web ([README](https://github.com/flet-dev/flet/blob/main/sdk/python/packages/flet-webview/README.md)). O relatório existente teria de abrir no navegador.
- **Testes:**
  - `flet test` roda testes pytest contra o app construído, "on the target device", com Python embutido.
  - Exige o Flutter SDK, e a primeira execução é lenta ([integration testing](https://flet.dev/docs/getting-started/integration-testing/)).
  - Não há equivalente da fixture `user` do NiceGUI, que roda em processo.
- **Tamanho:** a documentação não publica tamanho de app desktop, e eu não medi.

## 3. Tauri com o Python como sidecar

- **Versão:** Tauri 2.12.5, de 21/10/2026. A 3.0 está em alfa ([releases](https://github.com/tauri-apps/tauri/releases)).
- **Como funciona:**
  - O sidecar entra em `bundle.externalBin`, com um binário por arquitetura chamado `nome-$TARGET_TRIPLE`, por exemplo `-aarch64-apple-darwin` ([sidecar](https://v2.tauri.app/develop/sidecar/)).
  - A execução passa pelo plugin `shell` e exige permissão `shell:allow-execute` ou `shell:allow-spawn` em `capabilities/default.json` ([sidecar](https://v2.tauri.app/develop/sidecar/)).
  - A documentação cita "Python CLI applications or API servers bundled using `pyinstaller`" como caso típico.
- **Tamanho:**
  - Um app Tauri mínimo pode ter menos de 600 KB, porque usa o webview do sistema ([intro](https://v2.tauri.app/start/)).
  - O sidecar PyInstaller continua com o tamanho da seção 8. O Tauri não reduz o peso do Python.
  - No Linux, o AppImage sobe "from the 2-6 MB range to 70+ MB" ([AppImage](https://v2.tauri.app/distribute/appimage/)).
- **Webview:** WebView2 no Windows, já instalado no Windows 11 e garantido pelo instalador nas versões anteriores ([webview versions](https://v2.tauri.app/reference/webview-versions/)). WKWebView no macOS. `webkit2gtk-4.1` no Linux, com build na base mais antiga suportada, como Ubuntu 22.04 ou Debian 12 ([AppImage](https://v2.tauri.app/distribute/appimage/)).
- **Instaladores:** MSI (WiX, só no Windows) ou NSIS `-setup.exe`. O NSIS tem compilação cruzada com ressalvas ([Windows installer](https://v2.tauri.app/distribute/windows-installer/)).
- **Complexidade:** são três toolchains (Rust, Node com o frontend JS e Python com PyInstaller), duas linguagens de UI e IPC por processo filho. A interface teria de ser reescrita em JS/TS.

## 4. PyInstaller

- **Versão:** 6.22.3, de 12/09/2026, sob GPLv2 com exceção que permite distribuir programas não livres ([PyPI](https://pypi.org/project/pyinstaller/6.22.3/), [releases](https://github.com/pyinstaller/pyinstaller/releases)).
- **Compatibilidade:**
  - Python 3.8 a 3.15, ou seja, 3.11 e 3.12 inclusos.
  - Windows 8+ (32 e 64 bits, ARM64) e macOS 10.15+ (`x86_64` ou `arm64`).
  - Não é compilador cruzado: o executável de cada sistema se gera nele mesmo ([README](https://github.com/pyinstaller/pyinstaller/blob/develop/README.rst)).
- **onefile e onedir** ([operating mode](https://pyinstaller.org/en/stable/operating-mode.html)):
  - O onefile cria `_MEIxxxxxx` na pasta temporária, extrai tudo e apaga ao sair. Se o programa cair, a pasta fica.
  - O onefile é mais lento para abrir.
  - Não se deve dar privilégio de administrador a um onefile no Windows.
  - `sys._MEIPASS` aponta para a pasta dos arquivos do bundle ([runtime information](https://pyinstaller.org/en/stable/runtime-information.html)).
- **macOS:**
  - **Onefile com `.app`:** está obsoleto desde a 6.13.0 e "will be blocked in v7.0", porque "heavily penalised by macOS's security scanning". Use onedir ([changelog 6.13.0](https://pyinstaller.org/en/stable/CHANGES.html)).
  - **Assinatura ad hoc:** por padrão, o PyInstaller reassina ad hoc todos os binários e o executável. Com `--codesign-identity`, assina com a identidade e liga o hardened runtime (`--options=runtime`). Certificado autoassinado não serve ([feature notes](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing)).
  - **Arquitetura:** o padrão é a arquitetura da máquina. `universal2` exige que todas as extensões sejam fat binaries. Juntar dois executáveis com `lipo` não funciona ([feature notes](https://pyinstaller.org/en/stable/feature-notes.html#macos-multi-arch-support)).
  - **Wheels do projeto:** `opencv-python-headless` e `pyarrow` só publicam wheels `macosx_*_arm64` e `macosx_*_x86_64` separados, sem `universal2` ([PyPI opencv](https://pypi.org/project/opencv-python-headless/#files), [PyPI pyarrow](https://pypi.org/project/pyarrow/#files)). Na prática, é um build por arquitetura.
- **Gatekeeper:**
  - A partir do macOS Sequoia, Control-clique não contorna mais o Gatekeeper. O usuário precisa ir a Ajustes do Sistema > Privacidade e Segurança ([Apple Developer, 06/08/2024](https://developer.apple.com/news/?id=saqachfa)).
  - O caminho é: abrir uma vez, ir a Privacidade e Segurança, clicar em "Abrir Mesmo Assim" e confirmar. A exceção fica gravada ([suporte Apple](https://support.apple.com/en-us/102445)).
- **Notarização** ([Apple](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)):
  - Exige certificado "Developer ID", hardened runtime, timestamp seguro e `notarytool`.
  - Vale para app, DMG e pacote de instalação.
  - Faz parte do Apple Developer Program, que custa 99 USD por ano ([enroll](https://developer.apple.com/programs/enroll/)).
- **SmartScreen no Windows:**
  - Um executável sem assinatura mostra "Windows protected your PC", e o usuário precisa escolher "Run anyway". Autoassinado tem o mesmo efeito.
  - Assinado com OV, o aviso é "unrecognized" com o nome do editor, até acumular reputação.
  - O EV não dá mais reputação imediata.
  - Sem assinatura, cada versão recomeça do zero ([SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)).
  - O Azure Artifact Signing custa a partir de 9,99 USD por mês, mas só aceita pessoa física nos EUA e no Canadá. Fora disso, a alternativa é um certificado OV, de 150 a 300 USD por ano ([publish first app](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/publish-first-app)).
- **Hooks para as dependências do projeto:**
  - No núcleo: `pandas`, `scipy`, `numpy`, `matplotlib` e `PIL` ([hooks](https://github.com/pyinstaller/pyinstaller/tree/develop/PyInstaller/hooks)).
  - No pyinstaller-hooks-contrib 2026.9, de 20/10/2026 ([PyPI](https://pypi.org/project/pyinstaller-hooks-contrib/2026.9/)): `cv2`, `sklearn`, `pyarrow`, `plotly`, `pypdfium2`, `pdfminer`, `uvicorn`, `webview` e `nicegui` ([stdhooks](https://github.com/pyinstaller/pyinstaller-hooks-contrib/tree/master/_pyinstaller_hooks_contrib/stdhooks)).
  - O pytesseract é Python puro e não precisa de hook.
  - A 6.22.0 atualizou o hook de `matplotlib.backends` para o Matplotlib 3.11 ([changelog](https://pyinstaller.org/en/stable/CHANGES.html)).
- **Linux:** o PyInstaller não empacota a `glibc`. O executável funciona em sistemas iguais ou mais novos que o do build ([usage](https://pyinstaller.org/en/stable/usage.html#making-gnu-linux-apps-forward-compatible)). Os wheels de `pyarrow`, `scipy` e `numpy` são `manylinux_2_28` ([PyPI](https://pypi.org/project/pyarrow/#files)), logo a base mínima é glibc 2.28.
- **Programa auxiliar** ([common issues](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)):
  - Os caminhos de biblioteca do bundle são herdados pelos subprocessos: `LD_LIBRARY_PATH` no Linux e `SetDllDirectoryW` no Windows. Assim, um executável auxiliar empacotado, como o `tesseract`, usa as bibliotecas do bundle.
  - Um programa do sistema chamado do app pode quebrar por conflito de bibliotecas. Nesse caso, restaure `LD_LIBRARY_PATH_ORIG`.
  - Binários acrescentados com `--add-binary` passam pela busca de dependências ([spec files](https://pyinstaller.org/en/stable/spec-files.html#adding-binary-files)).

## 5. Tesseract embutido

### Licenças

- **Tesseract:** Apache-2.0 ([licença](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE)). A versão mais recente é a 5.5.4, de 28/10/2026 ([release](https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.4)).
- **Leptonica:** licença BSD de 2 cláusulas. A redistribuição binária reproduz o aviso de copyright ([licença](https://github.com/DanBloomberg/leptonica/blob/master/leptonica-license.txt)). O Homebrew a classifica como `BSD-2-Clause` ([fórmula](https://formulae.brew.sh/formula/leptonica)). A versão mais recente é a 1.87.0 ([releases](https://github.com/DanBloomberg/leptonica/releases)).
- **Dependências transitivas:** libpng, libjpeg-turbo, libtiff, openjpeg, webp e giflib, no caso da Leptonica do Homebrew ([fórmula](https://formulae.brew.sh/formula/leptonica)). Cada uma tem a própria licença permissiva, e o bundle precisa de um `LICENSES/` com todas.
- **Modelos:** os `tessdata` são Apache-2.0 ([tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast)).

### Windows

- **Fonte dos binários:** a tessdoc indica os instaladores da UB Mannheim ([instalação](https://tesseract-ocr.github.io/tessdoc/Installation.html)).
- **Versão:** a mais recente é `tesseract-ocr-w64-setup-5.5.3.20260724.exe`, de 24/07/2026. Desde a 5.3.1, ela é montada com pacotes do MSYS2 e só sai em 64 bits ([wiki UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)).
- **Tamanho:** o instalador da 5.4.0 no GitHub tem 50 MB e inclui as ferramentas de treino ([release](https://github.com/UB-Mannheim/tesseract/releases/tag/v5.4.0.20240606)). O servidor `digi.bib.uni-mannheim.de` devolveu 403 à consulta automática, então não confirmei o tamanho da 5.5.3.
- **Uso portátil:**
  - A UB Mannheim não documenta uso sem instalador.
  - O caminho oficial equivalente é o MSYS2 (`pacman -S mingw-w64-x86_64-tesseract-ocr` e `mingw-w64-x86_64-tesseract-data-por`) ([instalação](https://tesseract-ocr.github.io/tessdoc/Installation.html)). Dele se copiam `tesseract.exe` e as DLLs de que depende.
  - A lista de DLLs não está documentada. Ela precisa sair de uma análise das dependências, por exemplo com o `--add-binary` do PyInstaller (seção 4).

### macOS

- **Homebrew:**
  - O `tesseract` 5.5.4 tem bottles só para `arm64` (Sequoia, Tahoe e Golden Gate) e Linux, com cellar em `/opt/homebrew/Cellar`, ou seja, caminhos absolutos ([API da fórmula](https://formulae.brew.sh/api/formula/tesseract.json)).
  - Depende de cairo, pango, glib, harfbuzz, icu4c, leptonica, libarchive, fontconfig e freetype ([fórmula](https://formulae.brew.sh/formula/tesseract)). Boa parte vem das ferramentas de treino.
- **Intel:**
  - O Homebrew parou de gerar bottles para Intel. O macOS Tahoe 26 é o último macOS em Intel, e o Intel macOS é Tier 3 ([Support Tiers](https://docs.brew.sh/Support-Tiers)).
  - Um Tesseract `x86_64` exige compilar do código-fonte.
- **Relocação:**
  - `delocate-path` copia as bibliotecas de que uma árvore depende para dentro dela e corrige `install_name` e `rpath` ([delocate](https://github.com/matthew-brett/delocate)).
  - O `dylibbundler` (MIT) faz o mesmo para app bundles ([macdylibbundler](https://github.com/auriamg/macdylibbundler)).
  - Depois de relocar, é preciso reassinar.
- **Build enxuto:** o CMake do Tesseract tem `BUILD_TRAINING_TOOLS`, `DISABLE_ARCHIVE`, `DISABLE_CURL` e `GRAPHICS_DISABLED` ([CMakeLists.txt](https://github.com/tesseract-ocr/tesseract/blob/main/CMakeLists.txt)). Com eles, a dependência se reduz a leptonica e às bibliotecas de imagem.

### Linux

- **AppImage oficial:** a tessdoc indica o AppImage de AlexanderP. A 5.5.4, de 31/10/2026, tem 24 MB, inclui `por` e `osd` e roda em Debian ≥ 10 e Ubuntu ≥ 18.04 ([instalação](https://tesseract-ocr.github.io/tessdoc/Installation.html#appimage), [release](https://github.com/AlexanderP/tesseract-appimage/releases/tag/v5.5.4)).
- **Pacotes da distribuição:** `tesseract-ocr` e `tesseract-ocr-por` no Debian e no Ubuntu ([instalação](https://tesseract-ocr.github.io/tessdoc/Installation.html)). O `doctor` já sugere esse caminho.
- **Snap:** não traz os traineddata ([instalação](https://tesseract-ocr.github.io/tessdoc/Installation.html#snap)).

### Como apontar o binário e os dados

- **Executável:** `pytesseract.pytesseract.tesseract_cmd = r'<caminho completo>'` ([README do pytesseract](https://github.com/madmaze/pytesseract)). A versão mais recente do pytesseract é a 0.3.13, de 08/2024, Apache-2.0 ([PyPI](https://pypi.org/project/pytesseract/0.3.13/)).
- **Pasta dos modelos:**
  - `TESSDATA_PREFIX` aponta para a pasta dos `.traineddata` ([linha de comando](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html), [FAQ](https://tesseract-ocr.github.io/tessdoc/FAQ.html)).
  - Por chamada, use `config='--tessdata-dir "<pasta>"'`, com aspas ([README do pytesseract](https://github.com/madmaze/pytesseract)).
- **No projeto:** a única chamada é `pytesseract.image_to_string(imagem, lang='por')`, em `texto.py`. Bastam `por.traineddata` e o executável.

### Tamanho do `por.traineddata`

| Repositório | Tamanho | Modelo |
|---|---|---|
| [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast/blob/main/por.traineddata) | 1,98 MB | LSTM inteiro, menor e mais rápido, o menos preciso |
| [tessdata_best](https://github.com/tesseract-ocr/tessdata_best/blob/main/por.traineddata) | 8,16 MB | LSTM float, o mais preciso e o mais lento |
| [tessdata](https://github.com/tesseract-ocr/tessdata/blob/main/por.traineddata) | 15,34 MB | legado + LSTM (best inteirizado), o único que aceita `--oem 0` |

- **Fontes:** os tamanhos vêm da API de conteúdo do GitHub, e as características vêm de [Data Files](https://tesseract-ocr.github.io/tessdoc/Data-Files.html).
- **Ressalva:** `fast` e `best` não suportam o motor legado.
- **`osd`:** o `osd.traineddata` tem cerca de 10,6 MB e só é necessário para detectar a orientação, o que o projeto não faz.

## 6. Instaladores e runners

### Windows

- **NSIS:** a versão mais recente é a 3.13, de 27/09/2026 ([SourceForge](https://sourceforge.net/projects/nsis/files/NSIS%203/3.13/)). Não vem instalado no runner `windows-2025-vs2026`.
- **Inno Setup:**
  - A versão mais recente é a 7.1.1, de 28/10/2026 ([issrc](https://github.com/jrsoftware/issrc/releases/tag/is-7_1_1)).
  - O runner `windows-latest` (Windows Server 2025 com VS 2026) já traz o InnoSetup 6.7.1 e o WiX 3.14 ([readme da imagem](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-VS2026-Readme.md)).
  - Por isso, o Inno Setup evita um passo de instalação no CI.

### macOS

- **create-dmg:** a versão mais recente é a 1.3.0, de 02/07/2026 ([repositório](https://github.com/create-dmg/create-dmg)).
  - Tem `--volname`, `--icon` e `--app-drop-link`, que é o atalho para Aplicativos.
  - O DMG precisa ser notarizado à parte, porque "Disk images (UDIF format)" estão entre os artefatos notarizáveis ([Apple](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)).

### Linux

- **appimagetool:** só tem build contínuo, de 01/11/2026 ([repositório](https://github.com/AppImage/appimagetool)).
  - Baixa o runtime type-2 na hora do build. Para um build sem rede, use `--runtime-file`.
  - O runtime atual é estático e dispensa a `libfuse2` no sistema do usuário ([type2-runtime](https://github.com/AppImage/type2-runtime)). AppImages antigos ainda pedem `libfuse2`, renomeada `libfuse2t64` no Ubuntu 24.04 ([docs AppImage](https://docs.appimage.org/user-guide/troubleshooting/fuse.html)).
- **linuxdeploy:** só tem build contínuo, de 01/11/2026 ([releases](https://github.com/linuxdeploy/linuxdeploy/releases)).
- **Base do build:** compile na base mais antiga suportada (seção 4). O runner `ubuntu-22.04` tem glibc 2.35; para chegar à 2.28, use um contêiner `manylinux_2_28`.

### Runners do GitHub Actions

- **Imagens disponíveis** ([runner-images](https://github.com/actions/runner-images)):
  - `macos-latest`, `macos-26` e `macos-15` são `arm64`.
  - `macos-26-intel` e `macos-15-intel` são `x64`.
  - `windows-latest` é o Windows Server 2025.
  - `ubuntu-latest` é o Ubuntu 24.04. Há também `ubuntu-22.04`, `ubuntu-26.04` e as variantes `-arm`.
  - `windows-11-arm` existe para ARM64.
- **macOS 13:** foi descontinuado e ficou sem suporte em 04/12/2025 ([#13046](https://github.com/actions/runner-images/issues/13046)).
- **macOS 14:** foi aposentado no GitHub Actions em 02/11/2026 ([#15226](https://github.com/actions/runner-images/issues/15226)).
- **Intel:** `macos-15-intel` está "available from now until August 2027" e é "the last available x86_64 image" ([#13046](https://github.com/actions/runner-images/issues/13046)).
- **`macos-latest`:** passou para o macOS 26 em junho de 2026 ([#14167](https://github.com/actions/runner-images/issues/14167)).
- **Notarização no Intel:** há uma issue aberta em que o grampeamento da notarização falha no `macos-15-intel` desde 12/10/2026 ([#14924](https://github.com/actions/runner-images/issues/14924)).
- **universal2 ou um build por arquitetura:** pelos wheels sem `universal2` e pelas restrições do PyInstaller (seção 4), o caminho viável é um build `arm64` no `macos-latest` e, se necessário, um `x86_64` no `macos-15-intel` enquanto ele existir. O Tesseract Intel também exige compilação (seção 5).

## 7. Publicação de release

- **Limites:** cada arquivo de uma release precisa ter menos de 2 GiB, e uma release aceita até 1000 assets, sem limite de tamanho total nem de banda ([About releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases); valores em [`releases.yml`](https://github.com/github/docs/blob/main/data/variables/releases.yml) e [`large_files.yml`](https://github.com/github/docs/blob/main/data/variables/large_files.yml)).
- **`softprops/action-gh-release`:** a versão mais recente é a v3.0.3, de 30/08/2026 ([repositório](https://github.com/softprops/action-gh-release)).
- **`gh release create` e `gh release upload`:** fazem o mesmo sem action de terceiros, com o `gh` 2.103.3, de 26/10/2026 ([manual](https://cli.github.com/manual/gh_release_create), [releases](https://github.com/cli/cli/releases)).
- **Margem:** os artefatos estimados na seção 9 ficam bem abaixo de 2 GiB.

## 8. Medição local: bundle PyInstaller deste projeto

O build foi feito em 05/11/2026 no WSL2 (Linux x86_64), com Python 3.12.3, PyInstaller 6.22.3, `uv sync --no-dev --frozen` e `nicegui[native]==4.0.0`. O ponto de entrada é `concursos.cli:executar` com `--collect-data nicegui`. Ele ainda não importa a GUI, então o código Python do NiceGUI e as dependências dele (FastAPI, uvicorn) não entram; só os dados do pacote.

- **Versões resolvidas:** pyarrow 26.0.0, opencv 5.0.0, scipy 1.18.1, scikit-learn 1.9.1, pandas 3.0.6, numpy 2.5.4, matplotlib 3.11.2 e plotly 7.1.0.
- **Tamanho:**

| Formato | Tamanho |
|---|---|
| onedir descompactado | 630 MB |
| onedir em `tar.gz` | 249 MB |
| onefile | 248 MB |

- **Maiores pastas:**
  - `pyarrow`, 160 MB (25%);
  - `cv2` com `opencv_python_headless.libs`, 152 MB (24%, inclui `libavcodec`);
  - `scipy` com `scipy.libs`, 71 MB;
  - `numpy.libs`, 27 MB;
  - `nicegui`, 23 MB;
  - `sklearn`, 17 MB.
- **Abertura (`--help`, com os imports da CLI):**
  - onedir: 3,5 s na primeira vez e 2,6 s depois;
  - onefile: 5,6 s e 5,4 s, porque extrai tudo a cada execução.
- **Com o ambiente de desenvolvimento (sem `--no-dev`):**
  - O bundle sobe para 816 MB, com `jedi`, `nbformat` e afins.
  - O `--help` imprime um traceback: o plotly tenta importar `nbformat`, que puxa `jsonschema` e `rfc3987_syntax`, cujo `.lark` não foi coletado.
  - Moral: o build de release parte de `--no-dev`.
- **Problema do projeto:** os YAML de `concursos/perfis/bancas/` e `perfis/folhas/` não entraram no bundle.
  - `perfis/__init__.py` lê com `importlib.resources.files('concursos.perfis')`, e o PyInstaller não coleta dados de pacote sem hook.
  - O build precisa de `--collect-data concursos`, ou de um hook próprio.
  - O `concurso_analise-0.4.0.dist-info` foi coletado, o que deve manter os entry points `concurso.banca` e `concurso.ocr` funcionando. Falta confirmar num teste.
- **Wheels comprimidos por sistema** (cp312, PyPI, soma de pyarrow, opencv-headless, scipy, numpy, pandas, scikit-learn, matplotlib, pypdfium2 e pillow):

| Sistema | Soma dos wheels |
|---|---|
| Linux `manylinux` x86_64 | 208 MB |
| Windows `win_amd64` | 160 MB |
| macOS `arm64` | 161 MB |

  O Windows e o macOS devem gerar bundles cerca de 20% menores que o Linux. É uma estimativa por proporção, não uma medição.

## 9. Recomendação

### Comparação

- **Tamanho:**
  - Nas três opções, o peso vem do Python científico (seção 8), não da GUI.
  - O NiceGUI acrescenta dezenas de MB: os dados do pacote, mais FastAPI, uvicorn e pywebview.
  - O Flet acrescenta o runtime Flutter. Não medi o quanto, e a documentação não informa.
  - O Tauri economiza só o que já seria pequeno: o sidecar PyInstaller é o mesmo bundle de 630 MB, e o AppImage ainda embute o WebKitGTK.
- **Suporte do PyInstaller:**
  - O NiceGUI tem `nicegui-pack`, hook no contrib e a seção "Package for Installation", com `freeze_support` documentado.
  - O Flet tem `flet pack`, mas o caminho principal é o `flet build`, com Flutter, Visual Studio no Windows e GTK/GStreamer no Linux.
  - O Tauri usa o PyInstaller só para o sidecar e acrescenta Rust e Node.
- **Maturidade:**
  - O NiceGUI está na 4.0, com releases quase semanais e correções de segurança e de modo nativo empacotado ao longo de 2026. O modo nativo no Linux depende do WebKitGTK do sistema e não tem hook de WebKit2 no PyInstaller.
  - O Flet chegou à 1.0 em 2026 e ainda corrige bugs do `flet build` a cada dev release.
  - O Tauri 2 é estável, mas é um ecossistema separado do Python.
- **Testes:**
  - O NiceGUI tem a fixture `user`, em processo, rápida e sem Selenium, que entra no `pytest` atual.
  - O Flet só testa o app construído, com Flutter.
  - O Tauri precisaria de testes de frontend JS e de testes da CLI em separado.
- **Encaixe com o relatório HTML:**
  - O NiceGUI é web: serve o `index.html` existente com `app.add_static_files` ou o abre na mesma janela ou no navegador, sem reescrita.
  - O `flet-webview` não roda no Windows nem no Linux, então o relatório abriria fora do app.
  - O Tauri exibe HTML nativamente, mas exige uma interface nova em JS.

**Escolha: NiceGUI 4.x**, com PyInstaller em modo **onedir**, no Python 3.12. Pontos a seguir:

1. **Janela por sistema:** `native=True` no Windows (WebView2) e no macOS (WKWebView). No Linux, modo navegador, para não depender de PyGObject e WebKitGTK congelados.
2. **Host:** sempre `host='127.0.0.1'`. Porta com `native.find_open_port()` e `show=True`.
3. **Armazenamento e desligamento:** `NICEGUI_STORAGE_PATH` na pasta global (`~/.concurso`), e não na pasta de trabalho. `reload=False`. `freeze_support()` como primeira linha do main guard.
4. **Escolha de arquivos:** seletor de pasta nativo (`create_file_dialog` com `FileDialog.FOLDER`) quando há janela nativa. No Linux, o seletor do lado do servidor, como no exemplo `local_file_picker`. O `ui.upload` fica como alternativa, porque copia o PDF.
5. **Build:**
   - Partir de `--no-dev` e acrescentar `--collect-data concursos`, porque os perfis não entram sem isso.
   - O Tesseract entra como `--add-binary`, com `por.traineddata` do `tessdata_best` (8 MB) ou do `fast` (2 MB). O app define `tesseract_cmd` e `--tessdata-dir` a partir de `sys._MEIPASS`.
   - Uma camada de fallback mantém o Tesseract do sistema, com o cuidado de restaurar `LD_LIBRARY_PATH_ORIG`.
6. **Distribuição:**
   - Windows: Inno Setup, que já está no runner, ou NSIS.
   - macOS: um `.app` onedir num DMG (create-dmg), só `arm64` no `macos-latest`.
   - Linux: AppImage montado num contêiner `manylinux_2_28`.
   - Publicação com `gh release upload`.
7. **Assinatura:** sem assinatura, o guia de instalação precisa mostrar o "Mais informações > Executar assim mesmo" do SmartScreen e o "Abrir Mesmo Assim" em Privacidade e Segurança. Para remover os avisos, são 99 USD por ano da Apple e um certificado OV no Windows, já que o Artifact Signing não aceita pessoa física no Brasil.
8. **Testes:** os da GUI usam `nicegui.testing.user_plugin` com `main_file = ""`, num arquivo próprio, para não mudar a configuração dos testes atuais. O `scripts/smoke.py` ganha uma etapa que roda o executável congelado: `doctor`, uma análise de fixture e a idempotência.

### Tamanho esperado por sistema

O Linux x86_64 foi medido sem o código da GUI (seção 8). Os outros sistemas e o acréscimo da GUI e do Tesseract são estimativas: a incerteza fica em ±30% para Windows e macOS e em ±15% para Linux. O Flet e o Tauri não foram medidos.

| Sistema | Artefato | Descompactado (instalado) | Download | Base da estimativa |
|---|---|---|---|---|
| Linux x86_64 | AppImage | 650–700 MB | 250–300 MB | 630 MB medidos, mais uns 20–40 MB de código NiceGUI, FastAPI, uvicorn e Tesseract enxuto com `por` ([AppImage do tesseract](https://github.com/AlexanderP/tesseract-appimage/releases/tag/v5.5.4): 24 MB com 8 idiomas) |
| Windows x64 | instalador Inno ou NSIS (LZMA) | 500–650 MB | 180–260 MB | wheels cerca de 23% menores que os do Linux, mais o Tesseract MSYS2 (o instalador UB Mannheim de 50 MB inclui as ferramentas de treino); o WebView2 já está no sistema |
| macOS arm64 | `.app` onedir num DMG | 500–700 MB | 180–280 MB | wheels do mesmo porte que os do Windows; Tesseract do Homebrew relocado, com cairo, pango e icu, de 40 a 80 MB, ou de 10 a 20 MB se compilado sem as ferramentas de treino |
| macOS x86_64 (opcional) | `.app` num DMG | 520–720 MB | 190–290 MB | wheels `x86_64` próprios; Tesseract compilado, porque o Homebrew não tem bottle Intel; runner `macos-15-intel` até 08/2027 |

As maiores reduções possíveis, ainda não testadas, são duas. Excluir partes do pyarrow que o projeto não usa (`flight`, `s3`, `substrait`) atacaria 25% do bundle, e não é a GUI que pesa. O mesmo vale para os codecs de vídeo do OpenCV, embutidos no wheel.
