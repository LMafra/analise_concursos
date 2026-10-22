# 14: Wizard de onboarding e `init`

**What to build:** a primeira execução, ou `init`, faz as perguntas do onboarding em português, cada uma com `[n/6]` e o padrão entre colchetes:

1. nome;
2. pasta de provas;
3. pasta de análises;
4. rodar o `doctor`.

A calibração e o LLM entram nos tickets 15 e 16.

Antes de gravar, o wizard mostra um resumo e pede confirmação. Ele grava a configuração global, o perfil do candidato e a configuração do projeto, roda a análise e abre o relatório.

Cada pergunta também tem flag e variável de ambiente. Sem TTY, com `CI=true` ou com `--yes`, o wizard usa os padrões sem perguntar.

**Blocked by:** 04, 10, 13

**Status:** ready-for-agent

- [ ] Com stdin roteirizado aceitando todos os padrões, o comando grava as três configurações e gera o `index.html`.
- [ ] Sem TTY, nada é perguntado e os padrões são listados no log.
- [ ] Na segunda execução, o wizard não reaparece. `init` refaz as perguntas e oferece as respostas atuais como padrão.
- [ ] Se a pasta de provas não existir, o wizard oferece criá-la com um `LEIA-ME.txt` que explica o que colocar.
- [ ] O onboarding cronometrado no concurso sintético termina em até 90 segundos.
