# 01: Spec, pesquisa e retrato de paridade

**What to build:** a fase 4 ganha a spec, a pesquisa que a fundamenta e uma rede de segurança para os refactors. Ela mostra se uma mudança alterou alguma saída dos concursos reais. Nenhum comportamento do pipeline muda.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `docs/spec-fase4.md` com problema, solução, histórias, decisões, testes, fora de escopo e notas.
- [x] `docs/pesquisa-fase4.md` com as regras de peso, corte e desempate das seis bancas (item do edital e URL), padrões de UX de CLI, bibliotecas, OMR e distribuição.
- [x] Os 18 tickets em `.scratch/generalizacao-portabilidade/issues/`.
- [x] `scripts/paridade.py retrato|comparar` grava o hash de cada saída da análise e compara, ignorando o manifesto.
- [x] Retrato de base gravado fora do git, depois de confirmar que as saídas são determinísticas em duas execuções com `--forcar`.
