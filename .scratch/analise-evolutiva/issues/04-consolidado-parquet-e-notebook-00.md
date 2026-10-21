# 04: Consolidado em parquet e notebook de carregamento

**What to build:** um dataframe único com uma linha por questão de todos os concursos analisados, cacheado em parquet. Um notebook de carregamento valida esse dataframe e lista os avisos. Este ticket também monta a estrutura de notebooks reproduzíveis que os próximos usam.

- **Construção do consolidado.** Junta:
  - as tabelas de questões de todos os concursos, acrescentando o nome do concurso;
  - o arquivo de correção (modelo, fator, nota máxima, nota de corte, fonte, confiança e peso de cada item por variante);
  - os metadados da configuração (banca, cargo, formato, nível, escolaridade e data da prova).
- **Colunas derivadas:**
  - `ordem`: posição cronológica pela data da prova, vazia quando não houver data;
  - a pontuação de cada item nas três versões (bruta, corrigida e ajustada);
  - a quantidade de questões do tópico, como apelido do total que já existe.
- **Cache:** a função de carregar lê o parquet ou o reconstrói quando alguma tabela de análise, arquivo de correção ou configuração de concurso for mais nova que ele (checagem por mtime).
- **Validação de schema:** escrita à mão, sem dependência nova. Verifica colunas, tipos e domínios (modelo, fonte, escolaridade, resultado). Verifica também que o número de linhas é igual à soma das linhas das tabelas de questões.
- **Estrutura dos notebooks:**
  - grupo opcional de dependências de análise (pyarrow, scipy, plotly, jupyter, jupytext, papermill, nbconvert, ipykernel);
  - notebooks versionados como scripts jupytext no formato percent, com os arquivos de notebook gerados e o cache fora do git;
  - um script que converte e executa todos os notebooks em ordem e falha se algum quebrar;
  - um helper de resumo de tabelas (os N primeiros e as contagens) para as células.
- **Notebook 00:**
  - abre com a pergunta que responde ("a base consolidada está íntegra e comparável?");
  - carrega, valida e mostra a contagem por concurso, os avisos de data e de correção e a fonte da correção de cada concurso;
  - fecha com uma conclusão em prosa;
  - não contém lógica de negócio.

Ver `docs/spec-fase2.md` (histórias 21, 25–27, 31, 49 e 60–64).

**Blocked by:** 01 (Correção do edital ponta a ponta), 03 (Data da prova e metadados do concurso)

**Status:** done

- [x] Testes sobre consolidados mínimos montados por uma factory de teste:
  - construção, `ordem` com e sem data;
  - as três versões da pontuação por item;
  - rebuild por mtime (reconstrói quando um CSV fica mais novo e não reconstrói sem mudança);
  - a validação de schema falha com coluna ausente, domínio inválido e contagem divergente.
- [x] Com dados reais, o parquet tem tantas linhas quanto a soma das tabelas de questões (1.070 hoje), e todo concurso tem `modelo_correcao` e `fonte_correcao` preenchidos.
- [x] O script de execução roda o notebook 00 do zero sem erro.
- [x] `docs/modelo.md` atualizado com o schema do consolidado.
- [x] `uv run pytest` e `ruff` verdes.
