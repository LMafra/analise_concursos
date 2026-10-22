# 02: Notas de corte com unidade e escopo

**What to build:** o edital estruturado ganha a régua de aprovação inteira do cargo, sem colapsar nada num número único. Cada corte tem valor, unidade (`pontos` ou `acertos`), escopo, fonte, trecho, documento, página e confiança.

Os cortes são:

- **Conjunto das objetivas:** CD 54 pontos, TCU 60, CPNU 36 acertos.
- **Por bloco:** gerais e específicos (Cebraspe P1/P2 em pontos; AgSUS e CPRM em acertos).
- **Mínimo de acertos por disciplina:** "não zerar" na AgSUS, "ao menos 1 por disciplina do módulo I" no CPRM.
- **Discursiva:** só informativo, fora do "atingido".

A precedência é edital, depois configuração, depois default. O default emite aviso quando o texto do edital menciona "peso", "nota mínima", "corte", "desempate" ou "distribuição".

O arquivo de correção não muda.

Ver `docs/spec-fase3.md`, histórias 19–23 e 31–34.

**Blocked by:** 01 (Identificação do concurso e escopo por cargo)

**Status:** done

- [x] Testes puros com trechos reais curtos: quadro 7.1 e item 8.11 do Cebraspe, AgSUS 9.5 e 9.14, CPRM 12.13 e CPNU 8.15.
- [x] Teste puro: com dois cargos e cortes diferentes, sai o corte do cargo certo.
- [x] Teste puro: o default com palavra-gatilho emite aviso.
- [x] Sempre que a fonte for o edital, o trecho, o documento e a página vêm preenchidos.
- [x] Teste de CLI: os cortes aparecem no edital estruturado.
- [x] `docs/modelo.md` documenta o bloco de cortes.
- [x] `uv run pytest` e `ruff` verdes.
