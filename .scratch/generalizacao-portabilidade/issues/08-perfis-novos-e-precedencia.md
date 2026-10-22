# 08: Perfis novos e precedência com fonte `perfil`

**What to build:** perfis `fcc`, `vunesp`, `ibfc`, `idecan` e `generic`, baseados nos editais da pesquisa.

O valor de cada regra segue esta precedência: edital, depois `concurso.yaml`, depois perfil da banca, depois `generic`. O que vem do perfil leva a fonte `perfil`.

Mudanças nos cortes:

- "Não zerar disciplina" vira um tipo de corte.
- Escore padronizado e corte por quantidade de classificados ficam marcados como não calculáveis, com aviso, e saem do "atingido".

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] Trechos curtos dos editais da pesquisa produzem, por banca, o formato, as alternativas, a penalidade, o peso e os cortes esperados. Os editais são PF 2025, TSE 2024, PC-PE 2023, STN 2024, CVM 2024, TRT-6 2024, MP-PI 2025, TJSP 2023, TRF-5 2024, Fortaleza 2023 e EMPARN 2025.
- [ ] Um edital Cebraspe de múltipla escolha vence o padrão do perfil e fica sem penalidade.
- [ ] Um campo ausente no edital e na configuração é preenchido pelo perfil, com fonte `perfil` e confiança menor. A fonte nova aparece no parquet.
- [ ] Um corte não calculável é registrado com aviso e não entra no "atingido".
- [ ] "Não zerar disciplina" reprova o "atingido" quando alguma disciplina tem zero.
- [ ] O `docs/modelo.md` registra a fonte `perfil` e os tipos de corte novos.
- [ ] A paridade com os dados reais não mostra diferença.
