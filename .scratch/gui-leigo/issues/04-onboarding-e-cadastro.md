# 04: Onboarding, cadastro com detecção e respostas manuais

**What to build:** onboarding em formulário; `InteracaoGui`; novo concurso com arquivos soltos, papel detectado por `deteccao.classificar_arquivo` e confirmação; respostas do candidato em `provas/<concurso>/candidatos/<nome>/`; seletor de candidato e "analisar todos"; aviso sem Tesseract e formulário manual que grava `respostas.csv`.

**Blocked by:** 03

**Status:** todo

- [ ] O onboarding grava pelas mesmas funções do `init` (`onboarding.aplicar` e `gravar`).
- [ ] Trocar o papel antes de cadastrar muda o nome ou a pasta do arquivo conforme o cadastro espera.
- [ ] As perguntas do `cadastrar` chegam como diálogos; cancelar não grava nada.
- [ ] O CSV do formulário manual é aceito por `respostas.ler_respostas_csv`.
- [ ] Com mais de um candidato, o seletor aparece e "todos" chama a análise com `todos=True`.
