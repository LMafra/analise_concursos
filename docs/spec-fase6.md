# Spec da fase 6: confiança do sistema, atualização e polimento da GUI (Windows e Linux)

As decisões, com as alternativas descartadas, estão em `docs/decisoes-fase6.md`; os campos de arquivo (`[atualizacao]`, `atualizacao.json`), em `docs/modelo.md`. A fase 5 (`docs/spec-fase5.md`) continua valendo; esta fase só acrescenta. O macOS fica de fora: o job dele no `release.yml` não muda.

## Objetivo

O usuário sem nenhuma linguagem instalada e sem disposição para contornar avisos instala, abre, atualiza e entende o app. Seis frentes:

1. **Assinatura no Windows** pela SignPath Foundation: o publisher aparece identificado. O aviso do SmartScreen continua até a reputação acumular; o app não promete "sem aviso".
2. **WebView2:** o instalador o instala em silêncio quando falta, e a GUI avisa quando abre no navegador por falta dele.
3. **Partida medida:** o build já é onedir; o `--smoke` mede a partida, e o checklist exige menos de 3 s.
4. **AppImage autocontido:** as bibliotecas do Tesseract e do bundle são verificadas, e o OCR roda em contêiner limpo.
5. **Atualizador:** "Verificar atualizações" no Sobre e `upgrade` no executável baixam o instalador ou o AppImage, conferem o manifesto assinado (Ed25519) e o SHA-256, e aplicam a atualização sem terminal. Canais `stable` e `beta`.
6. **GUI:** tokens de design, componentes, onboarding em 4 passos com um exemplo, estados vazios com ação, etapa atual na barra e acessibilidade.

## Termos

| Termo | Significado |
|---|---|
| manifesto | `atualizacao.json`, asset de cada release, com a versão, o canal e o nome, o SHA-256 e o tamanho de cada artefato |
| assinatura do manifesto | `atualizacao.json.sig`: Ed25519 sobre os bytes exatos do manifesto, com a chave privada do mantenedor |
| canal | `stable` (a release marcada como "latest") ou `beta` (a release publicada mais nova, pré-release ou não) |
| decisão da janela | `nativa`, `navegador_pedido` (`--browser`), `navegador_linux` ou `navegador_sem_webview2` |
| etapa | o passo de um concurso dentro da análise: lendo arquivos, lendo a folha, corrigindo, classificando tópicos, gerando relatórios; e a consolidação no fim |
| exemplo | um concurso sintético num projeto separado em `~/.concurso/exemplo/`, recriado a cada uso |

## Histórias

### Confiança

1. Como candidato no Windows, quero ver "SignPath Foundation" como editor no aviso do SmartScreen e nas propriedades do `.exe`, para saber que o arquivo não foi alterado.
2. Como candidato, quero conferir o SHA-256 de cada download na página da release.
3. Como candidato, quero que o README explique por que o Windows avisa na primeira execução e como seguir.
4. Como candidato no Linux, quero que o AppImage leia folhas por OCR sem instalar nada, e que ele apareça no menu do sistema se eu quiser.

### Janela

5. Como candidato num Windows sem WebView2, quero que o instalador o instale sozinho.
6. Como candidato, se o WebView2 faltar ou a janela falhar, quero ler "Componente de janela indisponível; o app abre no navegador", com o link para instalar, e poder dispensar o aviso.

### Atualização

7. Como candidato, quero clicar em "Verificar atualizações" no Sobre e atualizar sem terminal.
8. Como candidato, quero, se eu ligar, um aviso discreto no cabeçalho quando houver versão nova, com no máximo uma consulta por dia.
9. Como candidato que testa versões novas, quero escolher o canal `beta` em Configurações > Avançado.
10. Como mantenedor, quero que o app recuse um manifesto sem assinatura válida, um artefato com SHA-256 diferente e uma versão mais velha que a instalada.

### GUI

11. Como candidato novo, quero um onboarding de 4 passos com indicador de progresso e "Pular" nos opcionais, que me mostre um resultado em menos de 60 s.
12. Como candidato, quero que toda tela vazia diga o que fazer, com um botão para isso.
13. Como candidato, quero ver a etapa da análise na barra ("Lendo a folha…", "Classificando tópicos…").
14. Como candidato com baixa visão ou daltonismo, quero contraste AA, foco visível, teclado e status com ícone e texto, nunca só cor.
15. Como candidato, quero escolher tema claro, escuro ou o do sistema.

## Entregas

Cada fatia é um PR com TDD e fecha com `uv run pytest`, `ruff`, `scripts/smoke.py` e o teste em máquina limpa registrado.

0. Spec, decisões, licença MIT, emendas no `AGENTS.md` e no `docs/modelo.md`, candidatura à SignPath.
1. (A) Partida e OCR real no `--smoke`.
2. (B) WebView2 no instalador, decisão da janela e aviso na GUI.
3. (C) Assinatura no CI, gate de Authenticode, README.
4. (D) Verificação de bibliotecas do AppImage, OCR em `ubuntu:22.04` e `debian:12`, integração ao desktop.
5. (E) Atualizador, `upgrade` no executável, Sobre, manifesto assinado na release, workflow ponta a ponta.
6. (F) Tokens, componentes, onboarding, estados vazios, etapas, acessibilidade.
7. (G) Relatório de smoke na release e checklist manual consolidado.

Betas `v0.6.0bN` saem depois de B, E e F. Tags PEP 440 com `a`, `b` ou `rc` viram pré-release; `v0.6.0` vira stable, e a promoção a "latest" é manual, depois do workflow `atualizacao.yml`.

## Decisões de implementação

### Assinatura

- Só os binários próprios: `concurso-analise.exe`, `concurso-analise-cli.exe` e o `setup.exe`. DLLs de terceiros e o `unins000.exe` ficam sem assinatura (`docs/decisoes-fase6.md`).
- Os `.exe` levam recurso de versão (`ProductName=concurso-analise`, `ProductVersion` igual à do pacote), gerado por `empacotamento/windows/versao.py`; o Inno leva `VersionInfo*`.
- No CI, a assinatura só roda com o secret `SIGNPATH_API_TOKEN` e as variáveis `SIGNPATH_ORGANIZATION_ID` e `SIGNPATH_PROJECT_SLUG`; sem eles, o build segue sem assinatura. Numa tag, a política é `release-signing` (aprovação manual); à mão, `test-signing`.
- O `smoke_maquina_limpa.ps1 -ExigirAssinatura` exige `Get-AuthenticodeSignature` com `Status` `Valid` no setup e nos dois `.exe` instalados.

### WebView2

- O instalador embute o bootstrapper (`MicrosoftEdgeWebview2Setup.exe`, baixado no build por `empacotamento/windows/obter_webview2.ps1`) e o roda com `/silent /install` quando `pv` falta ou é `0.0.0.0` em HKLM (WOW6432Node e nativo) e HKCU. Sem administrador, ele instala por usuário.
- `concursos.janela.decidir_janela(sistema, navegador, ler_registro, versao_pelo_loader)` devolve a `DecisaoJanela`; `gui/app.py` só a consome. No Windows, além do registro, pergunta a versão ao `WebView2Loader.dll` embutido no pywebview (`GetAvailableCoreWebView2BrowserVersionString`).
- Se `ui.run(native=True)` falhar, ou se a janela fechar sem nenhuma página ter conectado, o app reabre no navegador com `CONCURSO_JANELA_FALHOU=1`, o que mostra o aviso mesmo que o usuário o tenha dispensado.
- O aviso some com "Entendi" (`[gui] aviso_webview2_dispensado = true` no `config.toml` global).

### Partida

- `concursos.empacotado` guarda o instante da importação e o `--smoke` imprime `partida: X,Y s` até o primeiro HTTP 200 da GUI. Com `CONCURSO_SMOKE_LIMITE_PARTIDA` (segundos), falha acima dele; o CI usa 10.
- O `--smoke` gera uma imagem com PIL e exige que o Tesseract leia a palavra `CONCURSO` nela.

### AppImage

- `empacotamento/linux/verificar_bibliotecas.sh <onedir>`: o Tesseract é conferido pelo carregador embutido (`ld-linux-x86-64.so.2 --list --library-path`), e nada pode vir de fora de `tesseract/lib`; o resto do bundle, por `ldd`, só pode resolver fora do bundle as bibliotecas de `bibliotecas_do_sistema.txt` (glibc e o carregador). `not found` falha sempre.
- O AppDir ganha `.DirIcon`, o ícone em `usr/share/icons/hicolor/256x256/apps/` e `X-AppImage-Version`; o `.desktop` passa por `desktop-file-validate` quando ele existe.

### Atualizador

- `concursos.atualizador` (núcleo, sem rede direta) e `concursos.aplicacao.atualizador` (orquestração para a CLI e a GUI). O transporte é injetável: `baixar(url, limite) -> bytes` e `baixar_para(url, destino, limite)`.
- Stable: `https://github.com/LMafra/analise_concursos/releases/latest/download/atualizacao.json`. Beta: `GET https://api.github.com/repos/LMafra/analise_concursos/releases?per_page=10`, primeira release não rascunho; manifesto e assinatura pelos assets dela.
- Defesas: só HTTPS; redirecionamento só para `github.com`, `api.github.com`, `objects.githubusercontent.com` e `release-assets.githubusercontent.com`; manifesto até 64 KB; assinatura conferida antes de ler o JSON; `arquivo` validado por regex; URL do artefato montada pela base da release e pelo `arquivo`; download limitado ao `tamanho`; SHA-256 antes de executar; só versão maior (`packaging.version`); o cliente stable recusa manifesto `beta`.
- Chaves públicas em `CHAVES_PUBLICAS` (tupla; qualquer uma vale, para rotacionar). A chave privada é o secret `CHAVE_ATUALIZACAO` do environment `release`, e `scripts/assinar_manifesto.py` gera o manifesto e a assinatura.
- Windows: com o `.exe` atual assinado, o setup baixado precisa ter Authenticode válido do mesmo signatário. Depois da confirmação, roda `setup.exe /SILENT /SUPPRESSMSGBOXES /CLOSEAPPLICATIONS /REABRIR=1`, e o app fecha; o setup espera o mutex `concurso-analise`, que o executável segura, sumir.
- Linux: grava num temporário na pasta de `$APPIMAGE`, `chmod 755` e `os.replace` no mesmo caminho; o app oferece "Reabrir agora?". Pasta sem escrita: `ErroDoUsuario` com a dica de baixar à mão.
- `[atualizacao] verificar_ao_abrir` (padrão `false`) consulta ao abrir no máximo uma vez a cada 24 h; a data fica em `~/.concurso/atualizacao.json`. Falha nessa consulta vai só para o log; no botão, aparece como `erro:` e `dica:`.
- `--offline` e `--dry-run` não consultam nada. Fora do executável, `upgrade` continua com o `uv`.

### GUI

- `gui/tema.py` tem os tokens e `aplicar_tema(modo)`; nenhum hex, classe de cor do Quasar ou `gap-*` fora dele (teste). O espaçamento vai por `style='gap: ...'`.
- Componentes em `gui/componentes/`: `cartao`, `dialogo`, `estado_vazio`, `assistente`, `situacao`, `etapas`, `aviso`.
- O onboarding (`/inicio`) é um assistente de 4 passos: nome; pasta (avançado: provas e análises); opcionais desmarcados (IA para editais e aviso de versão nova, cada um com o texto de consentimento); primeiro resultado (exemplo ou cadastro). A calibração sai do onboarding e fica em Configurações.
- `concursos.exemplo` monta o concurso sintético (o mesmo de `scripts/smoke.py`); `aplicacao.exemplo.analisar_exemplo` o analisa em `~/.concurso/exemplo/`.
- `pipeline.analisar_todos(..., ao_etapa=None)` chama `ao_etapa(concurso, Etapa)`. Com `None`, nada muda (paridade).
- `[gui] tema` (`sistema`, `claro`, `escuro`) no `config.toml` global.

## Seams de teste

- **Atualizador:** transporte falso (dicionário URL → bytes), par de chaves Ed25519 gerado no teste, `abrir_processo` falso no Windows, `$APPIMAGE` em `tmp_path`.
- **Janela:** `ler_registro` e `carregar_loader` falsos.
- **GUI:** a fixture `user`, com a aplicação trocada por falsos.
- **Tokens:** contraste WCAG calculado dos tokens; regex sobre os fontes de `gui/`.
- **Executável:** `--smoke` (partida, OCR), `scripts/smoke.py congelado`, `verificar_bibliotecas.sh`.

## Checklist manual (antes de publicar)

Windows Sandbox (Win11) para o fluxo; VM Win10 LTSC com snapshot limpo, sem WebView2, para o passo 3.

1. Baixar o setup da release em rascunho; o SmartScreen mostra "Editor: SignPath Foundation" (ou "desconhecido", sem assinatura). Seguir.
2. Instalar com os padrões: atalho no menu Iniciar, sem senha de administrador.
3. Na VM Win10: o setup instala o WebView2 em silêncio, e o app abre em janela. Cortando a rede antes, o app abre no navegador com o aviso.
4. Abrir: cronometrar até a janela; menos de 3 s.
5. Onboarding: nome, pasta padrão, pular os opcionais, "Ver com um exemplo": resultado em menos de 60 s, contados do primeiro clique.
6. Criar um concurso com o `gabarito.txt` e o `respostas.txt` de `scripts/smoke.py`; importar uma folha escaneada; analisar; abrir o relatório.
7. Integrações: ligar o open-notebook contra um servidor de teste e sincronizar.
8. Sobre: versão, canal, janela, log; "Verificar atualizações" com a versão anterior instalada leva à atual.
9. Fechar e conferir que nenhum processo ficou; desinstalar.

Linux: o mesmo fluxo num contêiner `ubuntu:22.04` (pelo `smoke.py congelado`) e num desktop real (abrir pelo menu depois de integrar com o AppImageLauncher ou o Gear Lever).

Registrar data, versão e resultado na descrição da release. Os ambientes, o roteiro do Linux e a configuração da chave e da SignPath estão em `docs/release.md`.

## Fora do escopo

- macOS (assinatura, notarização, dylib), Microsoft Store, Tauri.
- Atualização silenciosa ou automática sem clique; delta e zsync do AppImage.
- WebView2 fixo empacotado.
- Assinar binários de terceiros.
- Ilustrações próprias: os estados vazios usam ícones Material.

## Critérios de aceitação

- **0:** spec e decisões; `LICENSE` MIT; `AGENTS.md` e `modelo.md` coerentes.
- **A:** `--smoke` imprime a partida e falha acima do limite; OCR real no smoke dos dois sistemas.
- **B:** sem WebView2, o setup o instala; sem ele, a GUI mostra o aviso com o link; nenhuma queda em silêncio para o navegador.
- **C:** com o secret, os três binários têm Authenticode válido e o CI confere; o README explica o aviso do Windows.
- **D:** `verificar_bibliotecas.sh` verde; OCR em `ubuntu:22.04` e `debian:12` sem `tesseract-ocr`; `.desktop` válido.
- **E:** a versão anterior atualiza sem terminal nos dois sistemas; manifesto adulterado, SHA-256 errado e versão menor são recusados; a release traz `atualizacao.json` e `.sig`.
- **F:** onboarding de 4 passos com exemplo; estados vazios com ação; etapa na barra; testes de contraste e de "sem hex" verdes.
- **G:** `RELATORIO-SMOKE.md` na release; checklist registrado.
