# Checklist de máquina limpa da fase 6

O roteiro é o de `docs/spec-fase6.md` ("Checklist manual"). Antes de tirar a release do rascunho, rode-o sobre os artefatos dela, confira o `RELATORIO-SMOKE.md` que veio junto e registre aqui a data, a versão e o resultado. Ele vem depois dos gates automáticos do `release.yml` (`--smoke`, `scripts/smoke.py congelado`, `verificar_bibliotecas.sh`, Authenticode na tag) e não os substitui.

## Ambientes

| Ambiente | Para quê | Como deixar limpo |
|---|---|---|
| Windows Sandbox (Win11) | fluxo completo, passos 1, 2 e 4 a 9 | toda abertura já é limpa; ativar em "Recursos do Windows" |
| VM Win10 LTSC sem WebView2 | passo 3 (bootstrapper e aviso) | snapshot logo depois da instalação, antes de qualquer Edge ou WebView2; voltar ao snapshot antes de cada rodada |
| Contêiner `ubuntu:22.04` e `debian:12` | AppImage sem Python e sem Tesseract | `docker run --rm` com o AppImage montado só leitura |
| Desktop Linux real | menu e ícone depois de integrar | AppImageLauncher ou Gear Lever, com usuário novo |

## Roteiro (Windows)

1. Baixar o setup da release em rascunho. O SmartScreen mostra "Editor: SignPath Foundation" (ou "Editor desconhecido", sem assinatura); a mensagem pode aparecer mesmo assinado, até o certificado ganhar reputação. Seguir por "Mais informações" e "Executar assim mesmo".
2. Instalar com os padrões: atalho no menu Iniciar, sem senha de administrador.
3. Na VM Win10: o setup instala o WebView2 em silêncio e o app abre em janela. Voltar ao snapshot, cortar a rede e instalar de novo: o app abre no navegador com o aviso "Componente de janela indisponível"; "Entendi" esconde o aviso na abertura seguinte.
4. Abrir pelo menu Iniciar e cronometrar até a janela: menos de 3 s (a segunda abertura; a primeira inclui a verificação do antivírus).
5. Onboarding: nome, pasta padrão, "Pular" nos opcionais, "Ver com um exemplo". O relatório aparece em menos de 60 s, contados do primeiro clique. Conferir em Configurações que a IA e o aviso de versão continuam desligados.
6. Criar um concurso com o `gabarito.txt` e o `respostas.txt` de `scripts/smoke.py`; importar uma folha escaneada; analisar (a barra mostra a etapa: "Lendo a folha…", "Corrigindo…"); abrir o relatório.
7. Integrações: ligar o open-notebook contra um servidor de teste e sincronizar.
8. Sobre: versão, canal, janela, log; "Conferir o ambiente"; com a versão anterior instalada, "Verificar atualizações" leva à atual e o app reabre nela.
9. Fechar pelo "Fechar o app" e conferir no Gerenciador de Tarefas que nenhum processo `concurso-analise` ficou; desinstalar pelo "Aplicativos instalados".

Também: Configurações > Aparência em Escuro e Claro; Tab percorre os botões com o contorno de foco visível.

## Roteiro (Linux)

1. Contêineres: `--smoke` e `doctor` em `debian:12` e `ubuntu:22.04` sem `python3` nem `tesseract`; `scripts/smoke.py congelado` no host.
2. GUI com `HOME` vazio: os passos 5, 6 e 8 do roteiro do Windows.
3. Desktop real: integrar o AppImage, abrir pelo menu (ícone e nome certos), atualizar pela GUI a partir da versão anterior e aceitar "Reabrir agora?".

## Registro

| Data | Versão | Ambiente | Passos | Resultado |
|---|---|---|---|---|
| 2026-11-05 | 0.5.0 (build local, commit da fatia F) | contêineres `debian:12` e `ubuntu:22.04` | Linux 1 | ok: OCR leu "CONCURSO 2026"; partida 2,6 s e 3,2 s, com a extração do AppImage (sem FUSE); `doctor` sem erros; `smoke.py congelado` em 4,2 s, idempotente |
| 2026-11-05 | 0.5.0 (build local, commit da fatia F) | AppImage no WSL, `HOME` vazio, navegador | Linux 2 (passos 5 e 8) | ok depois de duas correções (botões do cabeçalho sem contraste e ícone do cartão pequeno), conferidas pela GUI de desenvolvimento; detalhes em `smoke-local-linux.md` |
| pendente | primeira release da fase 6 | Windows Sandbox | Windows 1, 2, 4 a 9 | o setup só sai do `release.yml` (Inno Setup e SignPath no runner Windows) |
| pendente | primeira release da fase 6 | VM Win10 LTSC | Windows 3 | idem |
| pendente | primeira release da fase 6 | desktop Linux real | Linux 3 | o WSL não tem menu de aplicativos; o passo da atualização precisa de duas releases com manifesto |
