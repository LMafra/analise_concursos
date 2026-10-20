# 05: Taxonomia de disciplinas e bloco geral/específico

**What to build:** cada questão do consolidado passa a ter uma disciplina canônica e um bloco (geral ou específico). Assim, a mesma matéria pode ser comparada entre editais que usam nomes diferentes, e conhecimentos gerais e específicos podem ser analisados em separado.

- **Taxonomia:**
  - Um arquivo de configuração manual e revisável mapeia cada nome bruto de disciplina, como aparece nas análises, para uma disciplina canônica e um bloco.
  - Hoje são cerca de 53 nomes em 9 concursos. Exemplos: "Raciocínio Lógico Matemático" e "Raciocínio Análitico" viram "Raciocínio Lógico", e "Bancos de Dados" e "Banco de Dados" viram a mesma disciplina.
- **Revisão humana:** o agente escreve o rascunho completo do mapeamento a partir dos nomes reais e o usuário revisa antes de fechar o ticket.
- **Bloco:**
  - Nas provas divididas, vem da própria prova: `cg` e `cb` são geral, `ce` é específico.
  - Na prova única (FGV), vem da taxonomia.
- **Identidade de tópico:** é a disciplina canônica mais as palavras-chave normalizadas do nome do tópico, reaproveitando a normalização do comparativo da fase 1.
- A validação do consolidado falha, com a lista de nomes, quando algum nome de disciplina não estiver mapeado. Não há fallback silencioso.
- A taxonomia entra na checagem por mtime do cache.

Ver `docs/spec-fase2.md` (histórias 28–30) e a decisão "Identidade de disciplina".

**Blocked by:** 04 (Consolidado em parquet e notebook de carregamento)

**Status:** ready-for-agent

- [ ] Testes:
  - mapeamento aplicado;
  - nome sem mapeamento falha a validação com a lista de nomes;
  - bloco pela prova dividida e pela taxonomia na prova única;
  - chave de tópico estável para variações de acento, caixa e palavras vazias;
  - alterar a taxonomia reconstrói o cache.
- [ ] Rascunho da taxonomia cobrindo 100% dos nomes de disciplina dos 9 concursos.
- [ ] Revisão do usuário registrada neste ticket: o que foi aceito e o que mudou.
- [ ] Notebook 00 mostra quantas disciplinas canônicas aparecem em 1, 2 e 3 ou mais concursos.
- [ ] `docs/modelo.md` atualizado com a taxonomia, o bloco e a identidade de tópico.
- [ ] `uv run pytest` e `ruff` verdes, e o notebook 00 executa do zero.
