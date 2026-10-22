# 05: Migração automática das fases 1 a 3

**What to build:** na primeira execução da v4, os dados das fases 1 a 3 passam para o layout multi-candidato sem perda, nesta ordem:

1. Backup verificado por hash em `~/.concurso/backup-<timestamp>/`.
2. Criação do candidato padrão.
3. Saídas movidas para `analises/<slug>/`.
4. Seção de respostas e identificador extraídos de cada `concurso.yaml` para o `candidato.yaml`.
5. `config.yaml` e `taxonomia.yaml` convertidos para `./.concurso/`.
6. Migração registrada.

Uma pasta legada copiada depois é migrada na hora.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Uma árvore legada sintética migra, e cada saída anterior existe no caminho novo com o mesmo hash.
- [ ] O backup contém tudo o que foi alterado e é verificado por hash antes de qualquer mudança.
- [ ] Uma segunda execução não migra de novo.
- [ ] `--dry-run` lista as operações e não grava nada.
- [ ] Uma pasta legada copiada depois da migração é migrada sozinha, com aviso.
- [ ] A paridade com os dados reais, comparada contra `analises/<slug>`, não mostra diferença.
