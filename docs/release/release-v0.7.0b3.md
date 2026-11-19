Terceira versão beta da fase 7, com o app sob o nome **Gabarito Vivo** e a interface reorganizada. Por ser beta, ela só chega pelo atualizador a quem escolheu o canal `beta` em Configurações > Avançado, ou a quem baixar daqui.

## Como instalar

Baixe o arquivo do seu sistema em "Assets", logo abaixo:

| Sistema | Arquivo |
|---|---|
| Windows 10 ou 11, 64 bits | `gabarito-vivo-0.7.0b3-windows-x64-setup.exe` |
| macOS em Mac com chip Apple (M1 em diante) | `gabarito-vivo-0.7.0b3-macos-arm64.dmg` |
| Linux 64 bits, distribuições de 2019 em diante | `gabarito-vivo-0.7.0b3-linux-x86_64.AppImage` |

Quem está na 0.7.0b2 pode usar Sobre > Verificar atualizações, com o canal `beta` escolhido em Configurações > Avançado > Atualizações. O `SHA256SUMS` traz a impressão digital de cada arquivo, para conferir o download.

O comando na linha de comando passa a ser `gabarito-vivo` (o antigo `concurso-analise` continua funcionando, com aviso). A pasta do projeto, as análises e `~/.concurso` não mudam.

## O que mudou

- **Nome Gabarito Vivo.** Janela, instalador, AppImage, menu Iniciar e Sobre usam o nome novo; o pacote Python e a pasta `.concurso/` continuam iguais.
- **Menu em quatro áreas.** Minhas Provas (início), Resultados, Estudar e Concursos; Configurações e Sobre ficam no rodapé do menu.
- **Onboarding em três passos.** Nome, pasta e primeiro resultado; as opções avançadas de atualização ficam em Configurações.
- **Relatório HTML.** Banner da última prova, medidor de corte quando o edital traz o corte, e atalhos (prazos, prática, onde estudar) em seções recolhíveis.
- **Resultados.** Seletor do concurso analisado e atalhos para o simulado e a prática no TEC.
- **Radar de prazos** com tela própria em Concursos.
- **Linguagem.** “Parar de acompanhar” no lugar de cancelar; progresso da análise e toasts sem jargão técnico.

## Privacidade

Tudo continua no seu computador. A internet só é usada quando você liga a IA, a busca de concursos ou o aviso de versão nova, e quando você prepara a biblioteca; cada um mostra antes o que é enviado.

## Limitações conhecidas

- A biblioteca de estudo ainda não funciona no macOS.
- Um livro grande leva um tempo para ficar pesquisável; ele fica disponível aos poucos, e fechar o app não perde o trabalho.
