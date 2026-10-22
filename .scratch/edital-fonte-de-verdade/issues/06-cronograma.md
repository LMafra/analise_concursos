# 06: Cronograma do concurso

**What to build:** o edital estruturado ganha as datas da prova objetiva, da discursiva, do resultado preliminar, do resultado final e do recurso, quando o edital as traz (Anexo I no Cebraspe).

- Data ausente fica vazia, com aviso, e nunca é imputada.
- O cronograma distingue a discursiva no mesmo dia, em outro turno (Cebraspe), da discursiva em outro dia (CPNU, 07/12/2025).
- A data da prova no consolidado continua sendo a da objetiva, resolvida como na fase 2.
- O CSV de discrepâncias ganha um `info` quando a data da configuração difere da data do edital.

Ver `docs/spec-fase3.md`, histórias 24–27 e 48.

**Blocked by:** 01 (Identificação do concurso e escopo por cargo)

**Status:** ready-for-agent

- [ ] Teste puro: o Anexo I do Cebraspe dá a objetiva e a discursiva no mesmo dia.
- [ ] Teste puro: a discursiva em outro dia sai com a própria data.
- [ ] Teste puro: data ausente fica vazia com aviso.
- [ ] Teste de validação: uma data divergente gera `info`.
- [ ] A data da prova no consolidado não muda.
- [ ] `docs/modelo.md` documenta o bloco de cronograma.
- [ ] `uv run pytest` e `ruff` verdes.
