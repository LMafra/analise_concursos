# Decisões da fase 6

Registro curto das escolhas da fase 6 (Windows e Linux), com o contexto e as alternativas descartadas. A spec está em `docs/spec-fase6.md`.

## 1. Assinatura pela SignPath Foundation

- **Contexto:** desde 2024, nem o certificado EV dá reputação imediata no SmartScreen; um binário assinado ainda avisa até acumular reputação, mas mostra o editor. O Azure Artifact Signing aceita pessoa física só nos EUA e no Canadá, e organização só numa lista de países sem o Brasil ([quickstart](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart)).
- **Decisão:** SignPath Foundation, gratuita para projeto open source: a chave fica no HSM dela, a assinatura sai de um workflow do GitHub com a origem verificada, e cada assinatura de release passa por aprovação manual. O editor exibido é "SignPath Foundation".
- **Pré-requisitos:** licença OSI (MIT, nesta fase), repositório público, MFA no GitHub e na SignPath, `ProductName` e `ProductVersion` nos binários.
- **Descartado:** Azure Artifact Signing (inelegível); certificado OV ou EV comercial (150 a 400 USD por ano, sem vantagem de reputação); Microsoft Store (muda a distribuição).
- **Se a SignPath recusar ou demorar mais de 4 semanas:** a versão sai sem assinatura, com o `SHA256SUMS` e o manifesto assinado, e a questão volta depois.

## 2. Só os binários próprios são assinados

- **Contexto:** a política da SignPath proíbe assinar binário de terceiros com o certificado do projeto; o Inno só assina o desinstalador com um `SignTool` local, e a SignPath só aceita artefatos vindos do workflow.
- **Decisão:** assinar `concurso-analise.exe`, `concurso-analise-cli.exe` e o `setup.exe`. `python312.dll`, as DLLs do Tesseract (MSYS2) e o `unins000.exe` ficam sem assinatura.
- **Consequência:** o SmartScreen olha o arquivo baixado (o setup), que é assinado; os arquivos instalados não têm a marca da internet e não disparam o aviso.

## 3. Atualizador por manifesto assinado

- **Contexto:** o PyUpdater está arquivado. O tufup 0.10 (out/2025) ainda é pré-release, troca o diretório onedir no lugar (o registro do Inno fica com a versão velha) e não trata o AppImage, que é um arquivo só.
- **Decisão:** `atualizacao.json` em cada release, assinado com Ed25519 (`cryptography`), com as chaves públicas embutidas no app. O app baixa o artefato do sistema, confere o SHA-256 e o tamanho, e aplica: o setup do Inno no Windows, a troca do arquivo no Linux.
- **Defesas:** HTTPS com hosts permitidos, nome do arquivo por regex, URL montada pelo app, limite de tamanho, só versão maior, canal conferido, Authenticode do mesmo signatário no Windows quando o app atual é assinado.
- **Risco aceito:** sem os metadados de tempo do TUF, quem controlar a rede pode servir um manifesto antigo válido e "congelar" o usuário numa versão; não consegue instalar um binário que o mantenedor não assinou.
- **Chave:** gerada offline, com cópia no gerenciador de senhas; no CI, secret `CHAVE_ATUALIZACAO` do environment `release`, com revisor obrigatório. `CHAVES_PUBLICAS` é uma tupla, para rotacionar sem quebrar quem está instalado.
- **Descartado:** tufup; `version.json` sem assinatura; zsync do AppImage (não cobre o Windows).

## 4. Atualização sempre iniciada pelo usuário

- **Contexto:** o `AGENTS.md` proíbe chamada de rede sem opt-in e atualização silenciosa.
- **Decisão:** consulta no botão "Verificar atualizações" ou, se o usuário ligar `[atualizacao] verificar_ao_abrir` (desligado por padrão), no máximo uma vez a cada 24 h. A instalação só começa depois de uma confirmação. No Windows, o setup roda com `/SILENT` (barra de progresso, sem perguntas) e reabre o app; no Linux, o arquivo é trocado no mesmo caminho, para não quebrar atalhos, e o app pergunta se reabre.
- **Descartado:** consultar a cada abertura sem opt-in; trocar o nome do AppImage pela versão nova (quebra o atalho do menu).

## 5. WebView2 pelo bootstrapper embutido

- **Contexto:** o WebView2 vem no Windows 11 e na maioria dos Windows 10, mas pode faltar; sem ele, a fase 5 abria no navegador sem avisar.
- **Decisão:** o setup embute o bootstrapper (cerca de 2 MB) e o roda em silêncio quando o runtime falta. A GUI explica quando abre no navegador por falta dele ou por falha da janela.
- **Descartado:** WebView2 fixo empacotado (cerca de 150 MB a mais, e as correções de segurança dele passam a ser nossas).

## 6. Onedir mantido, sem splash

- **Contexto:** o build já é onedir desde a fase 5 (2,6 s medidos; o onefile, 5,4 s).
- **Decisão:** nenhuma migração; o `--smoke` passa a medir a partida, e o checklist exige menos de 3 s.

## 7. Onboarding com exemplo separado

- **Contexto:** o formulário da fase 5 pedia nome, duas pastas, calibração e o doctor antes de qualquer resultado.
- **Decisão:** assistente de 4 passos. O último oferece um concurso de exemplo num projeto separado (`~/.concurso/exemplo/`), com `respostas.txt` sintético e sem OCR, para o primeiro resultado sair em menos de 60 s sem misturar dado falso no projeto real. A calibração vai para Configurações.

## 8. Tokens de design

- **Contexto:** cores do Quasar espalhadas pelas páginas (`bg-red-1`, `text-grey-8`) e nenhum modo escuro.
- **Decisão:** `gui/tema.py` com uma escala de azul ancorada no ícone (`#1976D2`), cores semânticas com fundo, ícone e texto, e neutros sem preto puro. Os tons de texto que não passavam no AA foram escurecidos: verde `#2E7D32`, vermelho `#C62828`, alerta `#B45309`. Um teste calcula o contraste de cada par.
- **Consequência:** a numeração da escala é do projeto (`#1976D2` é o 500 aqui e o 700 no Material).
