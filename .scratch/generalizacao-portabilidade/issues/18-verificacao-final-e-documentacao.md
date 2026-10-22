# 18: Verificação final e documentação

**What to build:** a fase fecha com a documentação e as verificações finais:

- **`AGENTS.md`:** ganha as convenções de perfil, o template de banca nova, a forma de acrescentar um fallback e a lista do que está fora de escopo.
- **README:** abre com o comando único, três prints (wizard, progresso e relatório) e a seção "Problemas comuns".
- **Verificações:** os notebooks rodam do zero e a paridade final passa contra os dados reais migrados.

**Blocked by:** 17

**Status:** done

- [x] `grep -r "/home/" src/` retorna vazio, e o teste de ausência de dado pessoal passa. (Só os `.pyc` de `__pycache__` casam, fora do git.)
- [x] Nenhum arquivo do pacote importa de `notebooks/`.
- [x] O `AGENTS.md` e o README estão atualizados. (Wizard e progresso como captura de terminal; relatório em `docs/img/relatorio.png`, de um projeto sintético.)
- [x] `scripts/rodar_notebooks.sh` executa todos os notebooks do zero. (O 00 contava as questões na raiz de `analises/`; passou a usar a pasta do candidato.)
- [x] A suíte está verde, o ruff está limpo e a paridade final não mostra diferença. (Retrato regravado: as mensagens de pasta sem cadastro no `comparativo_concursos.md` passaram a citar `concurso-analise add`.)
