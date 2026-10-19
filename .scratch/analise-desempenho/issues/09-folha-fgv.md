# 09: Leitura da folha de resposta FGV

**What to build:** concursos FGV com o cartão-resposta em PDF ou imagem geram `respostas_extraidas.csv` (alternativas A–E) com os mesmos campos de confiança, revisão e rastreabilidade da folha Cebraspe. São dois templates: o modelo de 70 questões em blocos (agsus, cprm) e o cartão de 90 questões do CPNU. O pré-processamento e o alinhamento são reaproveitados do ticket 08.

**Blocked by:** 08

**Status:** ready-for-agent

- [ ] Testes com imagens sintéticas de 5 alternativas cobrem os estados marcada, branco e múltipla.
- [ ] A calibração manual em `agsus`, `cprm` e `cpnu` lista todas as questões, e as questões marcadas para revisão são conferidas.
- [ ] Imagem de depuração gerada para cada folha.
