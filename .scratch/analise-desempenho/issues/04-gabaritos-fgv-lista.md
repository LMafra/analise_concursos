# 04: Gabaritos FGV e lista "01: A" em PDF

**What to build:** o usuário aponta gabaritos com várias seções e informa cargo e tipo (ou prova A/B) no `concurso.yaml`. A análise seleciona a seção certa. Há dois formatos:
- **FGV:** cabeçalhos "cargo - tipo - turno" ou "cargo - TIPO n", inclusive o gabarito do CPNU por bloco temático e tipo; "*" marca anulada.
- **Lista "NN: R":** SELECON e Quadrix, com seções por código/cargo e "PROVA A/B"; "X" ou "*" marca anulada.

O parser também expõe a listagem das seções disponíveis, que o assistente de cadastro vai usar.

**Blocked by:** 01

**Status:** done

- [x] Trechos reais anonimizados de cada formato são interpretados nos testes de texto para estrutura.
- [x] Cargo/tipo inexistente gera erro listando as seções disponíveis.
- [x] A listagem de seções retorna cargo, tipo e quantidade de questões de cada seção.
- [x] O status preliminar ou definitivo é detectado (por exemplo, nos dois gabaritos da CRECI).
- [x] A verificação manual nos gabaritos reais de `agsus`, `cprm`, `cpnu`, `dataprev_2024`, `senappen` e `creci` extrai a seção esperada.

## Verificação manual (19/10/2026)

| Concurso | Seções no PDF | Seção selecionada | Itens | Anuladas | Status |
|---|---|---|---|---|---|
| agsus | 25 | Analista de Gestão Tecnologia da Informação, tipo 1 | 70 | 0 | definitivo |
| cprm | 53 | Analista em Geociências - Análise e Desenvolvimento de Sistemas, tipo 1 | 70 | 0 | definitivo |
| cpnu | 36 | Bloco Temático 3 - Ciências, Dados e Tecnologia, tipo 2 | 90 | 1 | definitivo |
| dataprev_2024 | 35 | Analista de TI - Desenvolvimento de Software, tipo 1 | 70 | 1 | definitivo |
| senappen | 16 | 501 - Analista Técnico em Direito, prova A | 60 | 2 | definitivo |
| creci (definitivo) | 12 | 101 - PAS - Analista de TI | 40 | 2 | definitivo |
| creci (preliminar) | 12 | 101 - PAS - Analista de TI | 40 | 0 | preliminar |

Bug encontrado e corrigido: o preliminar da CRECI era detectado como definitivo porque as instruções de recurso citam "gabarito oficial definitivo". O status agora vem da primeira menção (o título).
