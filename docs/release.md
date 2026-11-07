# Release

Como gerar, conferir e publicar uma versão. O `release.yml` faz o build e os gates automáticos; o resto é do mantenedor.

## Configurar uma vez

### Chave do manifesto de atualização

A chave pública fica em `atualizador.CHAVES_PUBLICAS`; a privada (Ed25519, PEM) nunca entra no repositório.

1. `uv run python scripts/assinar_manifesto.py gerar-chave <destino.pem>` gera o par com permissão 600 e imprime a chave pública, que vai para `CHAVES_PUBLICAS`.
2. No GitHub, Settings > Environments > New environment: `release`. Ligue "Required reviewers" com o mantenedor e restrinja "Deployment branches and tags" às tags `v*` e à branch `main` (o `estudo.yml` publica o pacote de estudo a partir dela, pela agenda ou à mão).
3. Em `release`, crie o secret `CHAVE_ATUALIZACAO` com o PEM inteiro (com as linhas `-----BEGIN PRIVATE KEY-----` e `-----END PRIVATE KEY-----`).
4. Guarde uma cópia do PEM num cofre de senhas e apague o arquivo local.

Sem o secret, o job `publicar` falha no passo "Manifesto de atualização assinado": nenhuma release sai sem manifesto.

**Rotacionar:** gere um par novo, acrescente a pública em `CHAVES_PUBLICAS` (sem tirar a antiga) e publique uma versão ainda assinada com a antiga; depois troque o secret pelo PEM novo e, quando a maioria tiver atualizado, tire a pública antiga numa versão seguinte.

**Se a privada vazar:** troque o secret, publique logo uma versão só com a pública nova e avise na página de releases para quem estiver nas versões anteriores atualizar à mão.

### Assinatura no Windows (SignPath)

Opcional: sem o secret `SIGNPATH_API_TOKEN`, o build segue sem assinar. Com o projeto aprovado na [SignPath Foundation](https://signpath.org/apply.html):

1. Na SignPath: projeto `concurso-analise`, Trusted Build System "GitHub.com" ligado ao projeto e o GitHub App instalado no repositório.
2. Artifact configurations, as duas com Authenticode e a restrição de metadados `ProductName=concurso-analise`:
   - `executaveis`: zip com `concurso-analise.exe` e `concurso-analise-cli.exe` na raiz;
   - `instalador`: o `setup.exe` solto.
3. Signing policies: `release-signing` (aprovação manual) e `test-signing`.
4. No GitHub: o secret `SIGNPATH_API_TOKEN` (usuário com papel de submitter) e as variáveis de repositório `SIGNPATH_ORGANIZATION_ID` e `SIGNPATH_PROJECT_SLUG`.
5. Rode o `release.yml` à mão (política `test-signing`) e confira o gate de assinatura antes da primeira tag.

Só os binários próprios são assinados; DLLs de terceiros e o desinstalador ficam sem assinatura.

## Gerar uma versão

1. Confira que há um pacote de estudo publicado (release `estudo-v*`, do `estudo.yml`) com `app_minimo` menor ou igual à versão nova. Numa tag `v*`, o `release.yml` falha sem ele: o gate de máquina limpa baixa o mais novo e roda `scripts/smoke.py estudo` com o executável (instala a biblioteca do arquivo, envia um PDF com uma página escaneada ao open-notebook e pergunta).
2. Suba `version` no `pyproject.toml` (PEP 440; `b` e `rc` viram prerelease) e, se quiser notas próprias, escreva `docs/release-v<versão>.md`.
3. Crie e envie a tag `v<versão>`. O `release.yml` gera o instalador do Windows, o AppImage e o DMG, roda o gate de máquina limpa de cada sistema e, depois da aprovação no environment `release`, cria a release como rascunho com os artefatos, o `atualizacao.json` e o `.sig`, o `RELATORIO-SMOKE.md` e o `SHA256SUMS`.
4. Confira o `RELATORIO-SMOKE.md`: uma seção por sistema, todas com `smoke: ok` e, no Windows e no Linux, a linha da biblioteca.
5. Rode o checklist de máquina limpa (abaixo) sobre os artefatos do rascunho e registre data, versão e resultado na descrição da release.
6. Publique o rascunho (prerelease para `b` e `rc`). A release não vira "latest" sozinha.
7. Teste a atualização de ponta a ponta: rode o workflow `atualizacao` com `de` = a tag anterior que já tem o atualizador, `esperada` = a versão nova e o canal. Só depois promova a release a "latest".

Para só gerar os instaladores, sem tag e sem release: `gh workflow run release.yml --ref <branch>` e baixe os artefatos da execução (`gh run download`).

## Checklist de máquina limpa

O roteiro do Windows (9 passos) está em "Checklist manual" de [docs/spec-fase6.md](spec-fase6.md). Ele vem depois dos gates automáticos e não os substitui.

| Ambiente | Para quê | Como deixar limpo |
|---|---|---|
| Windows Sandbox (Win11) | passos 1, 2 e 4 a 9 | toda abertura já é limpa; ativar em "Recursos do Windows" (Pro ou Enterprise) |
| VM Win10 LTSC sem WebView2 | passo 3 (bootstrapper e aviso) | snapshot logo depois da instalação, antes de qualquer Edge ou WebView2; voltar a ele antes de cada rodada |
| Contêineres `debian:12` e `ubuntu:22.04` | AppImage sem Python e sem Tesseract | `docker run --rm` com o AppImage montado só leitura |
| Desktop Linux real | menu, ícone e atualização | AppImageLauncher ou Gear Lever, com usuário novo |

No Windows, confira também o modo Escuro e o Claro em Configurações > Aparência, e que o Tab percorre os botões com o contorno de foco visível.

Biblioteca (fase 7), no Windows Sandbox e na VM Win10, com o PDF de `python scripts/smoke.py fixture livro.pdf` (uma página de texto e uma escaneada):

1. Estudar > Meus livros > **Preparar agora**: o aviso diz o tamanho do download, a barra avança e a tela diz que a biblioteca está pronta. O Windows Defender não põe nada em quarentena nem pede confirmação (o `surreal.exe` e o `python.exe` do pacote ficam em `%USERPROFILE%\.concurso\open-notebook\`).
2. **Adicionar livros** com o PDF: o livro passa por "Lendo página…" até "Pronto para perguntas", sem nenhuma janela de console abrindo.
3. Estudar > Perguntar: "autarquia" traz o trecho da página 2, e "licitacao", o da página 3 (lida pelo OCR).
4. Nenhuma tela mostra localhost, porta, servidor, Docker, API, source, sincronizar, embedding ou terminal, fora de Configurações > Avançado.
5. Sobre > **Verificar atualizações do app e da biblioteca** responde sem erro.
6. Feche o app: o Gerenciador de Tarefas não mostra mais `surreal.exe` nem o `python.exe` do pacote.

Linux:

1. `--smoke` e `doctor` nos dois contêineres, sem `python3` nem `tesseract`; `scripts/smoke.py congelado` e `scripts/smoke.py estudo <pacote> <AppImage>` no host.
2. A GUI com `HOME` vazio: os passos 5, 6 e 8 do roteiro do Windows.
3. No desktop: integrar o AppImage, abrir pelo menu (ícone e nome certos), atualizar pela GUI a partir da versão anterior e aceitar "Reabrir agora?".
4. Os passos 1 a 6 da biblioteca, acima; no 6, `pgrep -f open-notebook` não acha nada depois de fechar o app.
