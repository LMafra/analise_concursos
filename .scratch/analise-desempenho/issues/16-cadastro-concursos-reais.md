# 16: Cadastro dos 12 concursos reais e verificação final

**What to build:** os 12 concursos existentes são cadastrados com `adicionar`, o que valida a detecção com dados reais. Os YAMLs gerados são revisados, `analisar --forcar` roda completo e os critérios de aceite do projeto são verificados. Os concursos sem respostas (`dataprev_2024`, `senappen`, `creci`) aparecem como incompletos até o usuário fornecer o `respostas.txt` e o tipo ou prova.

**Blocked by:** 07, 09, 10, 12, 13, 14

**Status:** done

- [x] Os 12 concursos têm `concurso.yaml`. A detecção acerta o papel de todos os arquivos, ou as divergências ficam registradas como bugs.
- [x] `python -m pytest` passa.
- [x] Cada concurso completo tem as 4 saídas obrigatórias (respostas extraídas, desempenho por disciplina, desempenho por tópico, relatório) com o schema exigido.
- [x] `respostas_extraidas.csv` tem a coluna de confiança e lista todas as questões, inclusive brancas e ambíguas.
- [x] O comparativo consolidado responde quais tópicos são consistentemente fracos.
- [x] A validação oficial da `cpnu` bate. Divergências em outros concursos ficam investigadas e documentadas.

## Verificação final (provas/ reais)

- `concurso.yaml` nos 10 concursos que não dependem de informação pendente. Foram cadastrados com `adicionar` em cópias idênticas da pasta (conferidas por lista de arquivos) e copiados para `provas/`. Recadastro com `--aceitar-sugestoes` dá "sem mudanças" em agsus, cd_25, cpnu, funpresp_jud, infrasa, pf_perito, tcu_25 e telebras. cprm usa o tipo 1 escolhido pelo usuário; creci, a banca quadrix (pergunta interativa).
- dataprev_2024 e senappen ficam sem `concurso.yaml`: o usuário ainda não sabe o tipo do caderno (Dataprev 1–4) nem a prova (SENAPPEN A/B), e não há respostas. Pastas sem cadastro passam a aparecer como `incompleto` no `status` e no consolidado, com a instrução de rodar `adicionar`. Ao cadastrar a Dataprev, configurar `resultado_oficial.pesos` (específicas peso 2,5) para validar os 72,5 pontos.
- `analisar --forcar`: 9 concursos completos com as 4 saídas obrigatórias no schema; `respostas_extraidas.csv` lista todas as questões com `confianca_ocr` (as folhas reais não têm brancos nem leituras abaixo do limiar).
- Comparativo: tópicos baixos em 2+ concursos (coesão textual; compreensão de textos em inglês; desenvolvimento de sistemas) e disciplinas (Língua Portuguesa em 4 concursos, Legislação, Língua Inglesa, Bancos de Dados).
- Validação oficial: cpnu confere (52 acertos). creci (44, inclui discursiva) é só informativa e fica pendente das respostas.
- `python -m pytest`: 136 testes passando.
