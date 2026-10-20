# 09: Leitura da folha de resposta FGV

**What to build:** concursos FGV com o cartão-resposta em PDF ou imagem geram `respostas_extraidas.csv` (alternativas A–E) com os mesmos campos de confiança, revisão e rastreabilidade da folha Cebraspe. São dois templates: o modelo de 70 questões em blocos (agsus, cprm) e o cartão de 90 questões do CPNU. O pré-processamento e o alinhamento são reaproveitados do ticket 08.

**Blocked by:** 08

**Status:** done

- [x] Testes com imagens sintéticas de 5 alternativas cobrem os estados marcada, branco e múltipla.
- [x] A calibração manual em `agsus`, `cprm` e `cpnu` lista todas as questões, e as questões marcadas para revisão são conferidas.
- [x] Imagem de depuração gerada para cada folha.

## Calibração manual

Mudanças comuns às bancas:
- Página normalizada para 2480 px de largura.
- Bolhas detectadas como círculos escuros (anel ou bolha cheia) e claros (miolo branco sobre faixa cinza).
- Preenchimento medido como tinta: pixels abaixo de metade do branco do papel.
- Colunas escolhidas pelas de maior contagem, porque os números dos itens geram colunas fracas.

| Concurso | Template | Questões listadas | `revisar` | Conferência |
|---|---|---|---|---|
| agsus | fgv_mod70ae (4×20) | 70/70 | 0 | sobreposição conferida; itens 1–20 e 61–70 conferidos um a um |
| cprm | fgv_mod70ae (4×20) | 70/70 | 0 | confiança mínima 1,0 |
| cpnu | fgv_cpnu_90 (5×18) | 90/90 | 0 | itens 1–18 conferidos; 52 acertos = resultado oficial (16 CG + 8+3+11+9+5 eixos) |

As folhas Cebraspe do ticket 08 continuam lidas por inteiro, com confiança mínima 1,0.
