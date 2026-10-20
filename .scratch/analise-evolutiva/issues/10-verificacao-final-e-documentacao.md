# 10: Verificação final e documentação

**What to build:** a fase 2 verificada contra todos os critérios de aceite com os dados reais, e documentada para quem usa e para futuras sessões de agentes.

- **Verificação (`verify-and-stop`), sem ampliar o escopo:**
  - todos os notebooks executam do zero pelo script;
  - a suíte e o ruff ficam verdes;
  - os critérios de aceite da spec são conferidos com os dados reais.
  - Qualquer falha vira correção pontual ou ticket novo, nunca uma feature nova.
- **README:** seção "Análise evolutiva" com:
  - o que cada notebook responde;
  - como instalar o grupo de dependências de análise;
  - como rodar os notebooks e o script de execução;
  - onde ficam o cache e o relatório de evolução;
  - como declarar correção, variantes e data da prova no `concurso.yaml`.
- **Convenções para agentes (`writing-for-agents`):**
  - notebooks sem parsing, OCR, regra de negócio ou cálculo de correção;
  - jupytext no formato percent, com o notebook gerado fora do git;
  - a métrica padrão é a ajustada ao acaso, e a evolução se lê pelo z-score;
  - todo percentual vem com n, n < 5 é amostra insuficiente e não há tendência com menos de 3 pontos;
  - gerais e específicos ficam separados;
  - onde mora cada lógica (correção, consolidado, evolução, visualização).
- **Modelo de domínio:** revisão final, conferindo que os campos, contratos e fórmulas documentados batem com o implementado.

Ver `docs/spec-fase2.md` (histórias 65–67) e a seção "Testing Decisions".

**Blocked by:** 09 (Insights e relatório de evolução)

**Status:** ready-for-agent

- [ ] Todos os notebooks (00 a 04) executam do zero, sem erro, pelo script.
- [ ] O parquet tem tantas linhas quanto a soma das tabelas de questões, e o schema é validado.
- [ ] Todo concurso analisado tem `modelo_correcao` resolvido e `fonte_correcao` preenchida.
- [ ] Sempre que a fonte é o edital, o trecho de origem está preenchido e confere com o PDF (amostra de 3 concursos conferida à mão).
- [ ] Com penalidade, a versão corrigida difere da bruta em pelo menos uma questão com erro; sem penalidade, as duas coincidem. Isso está coberto por teste paramétrico.
- [ ] Toda função de correção e de evolução tem teste, incluindo n < 5, um concurso só, tópico sem gabarito e edital sem menção a correção.
- [ ] Nenhuma lógica de negócio em notebook (revisão das células).
- [ ] README com a seção "Análise evolutiva".
- [ ] `AGENTS.md` criado com as convenções.
- [ ] `uv run pytest` e `ruff` verdes.
