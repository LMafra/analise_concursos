Segunda versão beta da fase 7, com correções do que apareceu no uso da 0.7.0b1. Por ser beta, ela só chega pelo atualizador a quem escolheu o canal `beta` em Configurações > Avançado, ou a quem baixar daqui.

## Como instalar

Baixe o arquivo do seu sistema em "Assets", logo abaixo:

| Sistema | Arquivo |
|---|---|
| Windows 10 ou 11, 64 bits | `concurso-analise-0.7.0b2-windows-x64-setup.exe` |
| macOS em Mac com chip Apple (M1 em diante) | `concurso-analise-0.7.0b2-macos-arm64.dmg` |
| Linux 64 bits, distribuições de 2019 em diante | `concurso-analise-0.7.0b2-linux-x86_64.AppImage` |

Quem está na 0.7.0b1 pode usar Sobre > Verificar atualizações, com o canal `beta` escolhido em Configurações > Avançado > Atualizações. O `SHA256SUMS` traz a impressão digital de cada arquivo, para conferir o download.

## O que mudou

- **Preparar a biblioteca numa versão de teste.** O app de teste agora encontra a biblioteca de teste sem precisar trocar de canal. Quando nenhuma biblioteca serve, a mensagem diz o motivo: se o app é antigo demais, ela mostra a versão exigida e a que você tem; se só existe uma versão de teste da biblioteca, ela indica o canal `beta`.
- **Verificar atualizações no canal stable.** Enquanto não há versão estável publicada, o app responde que você já tem a versão mais nova, em vez de mostrar um erro do site.
- **Registro da análise na janela.** As linhas mostram `aviso:` e `erro:`, como no terminal, no lugar de `WARNING` e `INFO`.
- **Dica do open-notebook.** Quando o app não consegue falar com o open-notebook, a dica explica o que fazer na própria janela: conferir o endereço em Configurações > Avançado, ou, se for a biblioteca do app, abrir o app de novo ou prepará-la outra vez em Estudar.
- **Prova anterior ainda sem os arquivos.** Uma prova anterior do PCI cujos PDFs não foram baixados agora gera um aviso só, com o link da página para baixá-los, em vez de dois avisos com um erro técnico.
- **Cadastro sem nome.** Deixar o nome em branco usa o nome tirado do edital, em vez de dar erro.
- **Disciplinas fora da lista.** Quando muitas disciplinas não estão na lista de equivalentes, o aviso diz quantas são e dá três exemplos; a lista completa fica nos detalhes técnicos.
- **Tamanho do download da biblioteca** por sistema: cerca de 420 MB no Windows e 360 MB no Linux.

## Privacidade

Tudo continua no seu computador. A internet só é usada quando você liga a IA, a busca de concursos ou o aviso de versão nova, e quando você prepara a biblioteca; cada um mostra antes o que é enviado.

## Limitações conhecidas

- A biblioteca de estudo ainda não funciona no macOS.
- Um livro grande leva um tempo para ficar pesquisável; ele fica disponível aos poucos, e fechar o app não perde o trabalho.
