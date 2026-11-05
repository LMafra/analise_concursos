Primeira versão para quem não usa terminal: o concurso-analise agora tem uma janela e instaladores que já trazem o Python e o Tesseract.

## Como instalar

Baixe o arquivo do seu sistema em "Assets", logo abaixo:

| Sistema | Arquivo |
|---|---|
| Windows 10 ou 11, 64 bits | `concurso-analise-0.5.0-windows-x64-setup.exe` |
| macOS em Mac com chip Apple (M1 em diante) | `concurso-analise-0.5.0-macos-arm64.dmg` |
| Linux 64 bits, distribuições de 2019 em diante | `concurso-analise-0.5.0-linux-x86_64.AppImage` |

O app não tem assinatura digital paga. Na primeira vez, o Windows mostra "O Windows protegeu o computador" (clique em "Mais informações" e em "Executar assim mesmo"), e o macOS pede "Abrir Mesmo Assim" em Ajustes do Sistema > Privacidade e Segurança. O passo a passo com as telas está no [README](https://github.com/LMafra/analise_concursos#instalação-para-usuários-leigos).

O `SHA256SUMS` traz a impressão digital de cada arquivo, para conferir o download.

## O que há de novo

- **Janela** (no Linux, no navegador): escolher a pasta do projeto, criar um concurso soltando os arquivos da banca (o app detecta o edital, o gabarito, a prova e as respostas e pede confirmação), digitar as respostas quando a folha não puder ser lida, analisar com barra de progresso e log, e ver o relatório, as recomendações de estudo e a prática no TEC na própria tela.
- **Configurações** sem editar arquivo: limiares da análise, concurso-alvo e a leitura de editais por IA, desligada por padrão, com a chave no cofre de senhas do sistema.
- **Integrações** na janela: descobrir concursos e provas anteriores no PCI Concursos, importar uma prova anterior como simulado, sincronizar com o open-notebook e importar a prática do TEC. Cada uma fica desligada até você concordar, e a tela mostra antes o que sai do computador.
- **Vários candidatos** no mesmo projeto, com o comparativo de todos.
- **Captura do TEC** (`tec-erros`) no mesmo repositório, com a extensão e o userscript dentro do instalador.
- Na CLI, o subcomando `concurso-analise gui` e o extra `[gui]`. Os demais comandos não mudaram.

## Privacidade

A janela só é acessível no seu computador (`127.0.0.1`). Nada sai da máquina sem você ligar uma integração, e o app não manda telemetria nem se atualiza sozinho.

## Limitações conhecidas

- Sem assinatura de código no Windows e no macOS.
- macOS só em Mac com chip Apple; Mac com Intel e Windows ou Linux em ARM ficam para depois.
- No Linux, a tela abre no navegador; use "Fechar o app" no menu para encerrar.
