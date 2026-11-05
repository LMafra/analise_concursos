# Retro da fase 5: GUI e executável para usuário leigo

Branch `feat/gui-leigo`, dez fatias (spec, camada de aplicação, tec-erros, GUI mínima, onboarding e cadastro, resultados e configurações, integrações, Windows, Linux e macOS, documentação).

## O que funcionou

- **A camada de aplicação veio antes de qualquer tela.** Extrair `aplicacao/` da CLI, com a paridade conferida antes e depois, deixou cada tela da GUI fina: nenhuma regra nova em `gui/`, e o teste por AST garante que `gui/` e `aplicacao/` não importam `typer`.
- **`nicegui.testing.User` com a aplicação falsa.** As telas foram escritas test-first, inclusive upload, abas e diálogos vindos da thread de trabalho (`InteracaoGui`). A suíte da GUI roda em cerca de 20 s.
- **Smoke do executável dentro dele.** O `--smoke` (versão, perfis, Tesseract com `por`, GUI respondendo em `127.0.0.1`) e o `scripts/smoke.py congelado` deram um gate igual nos três sistemas e acharam no Linux um problema que nenhum teste unitário pegaria.
- **Contêiner limpo como máquina limpa.** `debian:12` sem Python nem Tesseract reproduziu o usuário leigo no Linux em minutos.

## O que deu errado ou custou mais que o previsto

- **A `libstdc++` do Tesseract na raiz do pacote.** O PyInstaller 6 trata as `.so` em `datas` como binários e puxa as dependências delas para `_internal/`; a `libstdc++` do AppImage do Tesseract (GLIBC_2.38) venceu a do sistema e quebrou o executável no Debian 12. Correção: copiar a árvore do Tesseract depois do `COLLECT`. Só apareceu no contêiner limpo.
- **`LD_LIBRARY_PATH` do bootloader.** No Linux, o executável congelado passava as bibliotecas dele para o navegador e o `xdg-open`. O launcher agora devolve o valor original.
- **Status com um candidato só.** A tela de concursos mostrava "respostas não configuradas" quando o projeto tinha um único candidato, porque o seletor só gravava o candidato quando havia mais de um. Apareceu só ao montar o projeto de demonstração para os screenshots; virou teste.
- **Modo navegador sem saída.** No Linux, fechar a aba deixava o servidor rodando escondido. Entrou o botão "Fechar o app", só no modo navegador.
- **cp1252 no Windows.** O primeiro run do `release.yml` (`v0.5.0-rc1`) mostrou que o `concurso-analise-cli doctor` quebrava no ✓ com a saída redirecionada: o executável não tem o `PYTHONUTF8` do ambiente de desenvolvimento. O launcher passa stdout e stderr para UTF-8. O mesmo run achou três testes das fases 3 e 4 que falhavam no Windows também no `main`.

## Desvios do plano

- **Tesseract no macOS:** em vez de compilar um Tesseract enxuto e relocar com `delocate`, o build copia o do Homebrew e relocaliza só as dylibs de que ele depende com o `dylibbundler`.
- **Arrastar arquivos:** o `ui.upload` cobre arrastar e escolher em todos os modos; o evento `drop` nativo da janela não foi implementado.
- **Smoke da janela:** o `--smoke` sobe a GUI em modo navegador, sem abrir janela; a janela nativa (WebView2, WKWebView) fica para o checklist manual.
- **Release como rascunho:** o job `publicar` cria a release em rascunho, para o checklist do Windows Sandbox vir antes da publicação.

## Em aberto

- O checklist do Windows Sandbox e abrir o DMG num Mac (`docs/pendencias.md`, "Fase 5"); o `release.yml` já passou nos três sistemas em `v0.5.0-rc2`.
- Medir e cortar o tamanho do pacote (pyarrow, codecs do OpenCV) num ticket separado.
- Assinatura de código, macOS Intel e builds ARM do Windows e do Linux.

## Para a próxima fase

- Montar o projeto de demonstração e olhar as telas cedo, não só no fim: os cinco problemas acima apareceram ao rodar o produto de verdade (contêiner limpo, runner limpo ou projeto de demonstração), e nenhum nos testes.
- Todo build de executável passa por um contêiner ou VM sem Python antes de ser dado como pronto.
