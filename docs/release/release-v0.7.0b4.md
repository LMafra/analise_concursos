Quarta versão beta da fase 7, com a interface alinhada ao protótipo Vitals. Por ser beta, ela só chega pelo atualizador a quem escolheu o canal `beta` em Configurações > Avançado, ou a quem baixar daqui.

## Como instalar

Baixe o arquivo do seu sistema em "Assets", logo abaixo:

| Sistema | Arquivo |
|---|---|
| Windows 10 ou 11, 64 bits | `gabarito-vivo-0.7.0b4-windows-x64-setup.exe` |
| macOS em Mac com chip Apple (M1 em diante) | `gabarito-vivo-0.7.0b4-macos-arm64.dmg` |
| Linux 64 bits, distribuições de 2019 em diante | `gabarito-vivo-0.7.0b4-linux-x86_64.AppImage` |

Quem está na 0.7.0b3 pode usar Sobre > Verificar atualizações, com o canal `beta` escolhido em Configurações > Avançado > Atualizações. O `SHA256SUMS` traz a impressão digital de cada arquivo, para conferir o download.

## O que mudou

- **Resultados no padrão Vitals.** Hero com nota e corte, gráfico de evolução, tendência em frase e atalhos para treinar os assuntos fracos.
- **Concursos.** Busca do PCI em grade de cards, com prazo e selo legíveis.
- **Configurações.** Aparência e meta de nota na frente; o restante fica em Avançado.
- **Campos e casca.** Rótulos, tipografia e espaçamento alinhados ao protótipo; ícones Material.
- **Relatórios HTML.** Painel por fonte (concursos, TEC, simulados) sem inventar “ganho estimado”.
- **Estabilidade.** Cobertura do gate de arquitetura, e testes do Windows menos sensíveis a atraso de tela e à conexão do servidor de embeddings.

## Privacidade

Tudo continua no seu computador. A internet só é usada quando você liga a IA, a busca de concursos ou o aviso de versão nova, e quando você prepara a biblioteca; cada um mostra antes o que é enviado.

## Limitações conhecidas

- A biblioteca de estudo ainda não funciona no macOS.
- Um livro grande leva um tempo para ficar pesquisável; ele fica disponível aos poucos, e fechar o app não perde o trabalho.
