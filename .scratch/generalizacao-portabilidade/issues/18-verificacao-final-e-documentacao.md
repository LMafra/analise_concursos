# 18: Verificação final e documentação

**What to build:** a fase fecha com a documentação e as verificações finais:

- **`AGENTS.md`:** ganha as convenções de perfil, o template de banca nova, a forma de acrescentar um fallback e a lista do que está fora de escopo.
- **README:** abre com o comando único, três prints (wizard, progresso e relatório) e a seção "Problemas comuns".
- **Verificações:** os notebooks rodam do zero e a paridade final passa contra os dados reais migrados.

**Blocked by:** 17

**Status:** ready-for-agent

- [ ] `grep -r "/home/" src/` retorna vazio, e o teste de ausência de dado pessoal passa.
- [ ] Nenhum arquivo do pacote importa de `notebooks/`.
- [ ] O `AGENTS.md` e o README estão atualizados.
- [ ] `scripts/rodar_notebooks.sh` executa todos os notebooks do zero.
- [ ] A suíte está verde, o ruff está limpo e a paridade final não mostra diferença.
