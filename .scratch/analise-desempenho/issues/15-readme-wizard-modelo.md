# 15: README, assistente bash e documento do modelo

**What to build:** um usuário novo segue o README e adiciona um concurso do zero. O assistente bash interativo cria a pasta, orienta a cópia dos arquivos (incluindo o formato do `respostas.txt` e a troca de gabarito) e chama `adicionar` e depois `analisar`. O documento do modelo descreve as entidades do domínio: Concurso, Prova, Questão, Disciplina/Tópico, Gabarito com status, RespostaMarcada, Resultado e EventoHistórico.

**Blocked by:** 07, 14

**Status:** ready-for-agent

- [ ] O README cobre instalação (uv, Tesseract opcional), o fluxo coletar, cadastrar e analisar, o formato do `respostas.txt`, a revisão de tópicos, a troca de gabarito e o comando `status`.
- [ ] O assistente bash executa o fluxo completo num concurso sintético (verificação manual registrada).
- [ ] O documento do modelo está alinhado com o schema do `concurso.yaml` e com os contratos de saída.
