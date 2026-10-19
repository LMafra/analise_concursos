# 16: Cadastro dos 12 concursos reais e verificação final

**What to build:** os 12 concursos existentes são cadastrados com `adicionar`, o que valida a detecção com dados reais. Os YAMLs gerados são revisados, `analisar --forcar` roda completo e os critérios de aceite do projeto são verificados. Os concursos sem respostas (`dataprev_2024`, `senappen`, `creci`) aparecem como incompletos até o usuário fornecer o `respostas.txt` e o tipo ou prova.

**Blocked by:** 07, 09, 10, 12, 13, 14

**Status:** ready-for-agent

- [ ] Os 12 concursos têm `concurso.yaml`. A detecção acerta o papel de todos os arquivos, ou as divergências ficam registradas como bugs.
- [ ] `python -m pytest` passa.
- [ ] Cada concurso completo tem as 4 saídas obrigatórias (respostas extraídas, desempenho por disciplina, desempenho por tópico, relatório) com o schema exigido.
- [ ] `respostas_extraidas.csv` tem a coluna de confiança e lista todas as questões, inclusive brancas e ambíguas.
- [ ] O comparativo consolidado responde quais tópicos são consistentemente fracos.
- [ ] A validação oficial da `cpnu` bate. Divergências em outros concursos ficam investigadas e documentadas.
