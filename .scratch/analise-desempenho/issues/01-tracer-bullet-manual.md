# 01: Primeiro fluxo completo com dados manuais

**What to build:** o usuário cria a pasta de um concurso com um `concurso.yaml` escrito à mão, um gabarito em texto e um `respostas.txt`, roda `concursos analisar` e obtém as respostas extraídas, o desempenho por disciplina (disciplina vinda das faixas de itens do YAML, tópico `nao_mapeado`) e um relatório mínimo. Este ticket também monta a base do projeto: uv com entrypoint da linha de comando, git, pre-commit (ruff + pytest), `.gitignore` excluindo provas, análises e dados pessoais, configuração global de limiares e `logging`. A pontuação é simples (múltipla escolha).

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `uv run concursos analisar` processa um concurso sintético numa pasta temporária, ponta a ponta.
- [x] O parser do `respostas.txt` aceita "1 A", "01: A", "1-C" e minúsculas. "-", linha vazia ou questão omitida contam como em branco. Linhas com `#` são comentário. Resposta inválida, número duplicado ou fora da faixa geram erro com o número da linha.
- [x] O gabarito manual em texto/CSV é aceito como formato canônico.
- [x] `respostas_extraidas.csv` lista todas as questões da faixa com as colunas do contrato (`origem=manual`, `confianca_ocr=1.0`).
- [x] `desempenho_por_disciplina.csv` tem as colunas `concurso, prova, disciplina, topico, total, acertos, erros, percentual`.
- [x] `relatorio.md` mínimo é gerado.
- [x] O teste ponta a ponta pela linha de comando passa com `python -m pytest`, e o pre-commit roda ruff e pytest.
