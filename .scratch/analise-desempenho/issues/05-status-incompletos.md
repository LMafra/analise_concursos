# 05: Comando status e concursos incompletos

**What to build:** o usuário roda `concursos status` e vê cada concurso como completo, incompleto (com motivo: falta edital, respostas, gabarito ou prova) ou desatualizado. O `analisar` pula concursos incompletos com aviso, processa os demais e nunca falha silenciosamente. A validação do `concurso.yaml` aponta o campo ou o arquivo exato com problema.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] `status` mostra a tabela com concurso, status, motivo e status do gabarito.
- [ ] Um concurso sem respostas não impede a análise de outro concurso completo (teste ponta a ponta).
- [ ] Arquivo referenciado e ausente gera erro específico com o caminho completo.
- [ ] YAML inválido gera erro apontando o campo.
