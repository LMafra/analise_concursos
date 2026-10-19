# 11: Edital estruturado e disciplina pelo caderno

**What to build:** a análise extrai do edital (ou de um anexo, como no CPNU) o conteúdo programático do cargo configurado como conhecimento, disciplina e tópicos (peso opcional) e salva o edital estruturado em JSON. Se a extração falhar, exige um edital manual estruturado com erro claro. Nos cadernos FGV e SELECON, a disciplina de cada questão passa a vir dos cabeçalhos do caderno, sem depender das faixas manuais. A tabela de questões (número, disciplina, gabarito, anulada) é gerada por concurso.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Teste com trecho de edital com vários cargos: só o cargo configurado é extraído.
- [ ] Teste com trecho de caderno FGV: as faixas por disciplina são extraídas.
- [ ] Edital manual tem precedência quando presente, e a falha sem ele gera mensagem clara.
- [ ] A verificação manual nos editais reais de `cd_25`, `agsus` e `cpnu` (anexo do Bloco 3) produz disciplinas coerentes.
