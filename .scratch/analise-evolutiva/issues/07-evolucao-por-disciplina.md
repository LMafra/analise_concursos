# 07: Evolução por disciplina (notebook 02)

**What to build:** um notebook que responde se estou melhorando em cada disciplina ao longo do tempo, com conhecimentos gerais e específicos separados. A leitura principal é o z-score.

- **`percentual_por_disciplina_ao_longo_do_tempo`:** uma linha por concurso e disciplina canônica, com:
  - concurso, ordem, disciplina, bloco;
  - percentual bruto, corrigido e ajustado;
  - nota normalizada;
  - n;
  - modelo de correção e fator.
- **`zscore_por_disciplina`:** \(z_d = (\bar s_d - \bar s_g)/(\sigma_g/\sqrt{n_d})\), sobre a pontuação de cada item na versão escolhida. As versões possíveis são bruta, corrigida e ajustada, com padrão ajustada.
- **`correlacao_tempo_zscore`:** Spearman entre a ordem e o z-score médio, com p-value e n.
- **Estratificação:** as funções temporais aceitam série única (banca como cor) ou estratificada por banca.
- **Tendência:** só com 3 pontos ou mais.
- **`modelos_distintos`:** quando a base tem mais de um modelo de correção, o topo do notebook mostra o aviso "⚠ modelos de correção distintos".
- **Gráficos:**
  - linha com o percentual ajustado e o z-score por disciplina ao longo da ordem, com marcas indicando n; pontos com n < 5 ficam soltos e transparentes, sem linha contínua; filtro por disciplina e hover com n;
  - box com os pontos sobrepostos da distribuição por disciplina entre concursos.
- O notebook abre com a pergunta e fecha com uma conclusão em prosa, e não contém lógica de negócio.

Ver `docs/spec-fase2.md` (histórias 36–42, 46, 48, 52, 53, 55 e 57).

**Blocked by:** 05 (Taxonomia de disciplinas e bloco geral/específico)

**Status:** done

- [x] Testes de cada função:
  - n < 5 marcado como amostra insuficiente;
  - um concurso só, sem tendência e sem erro;
  - correção líquida comparada à bruta;
  - geral e específico separados;
  - estratificação por banca;
  - z-score igual entre bruta e ajustada numa prova FGV sem brancos;
  - menos de 3 pontos não gera tendência.
- [x] Testes de que as funções de gráfico recebem o DataFrame pronto. Pontos com n < 5 não entram na série de linha contínua.
- [x] O aviso de modelos distintos aparece com os dados reais (Cebraspe líquida e FGV bruta ou ponderada).
- [x] O notebook 02 executa do zero pelo script.
- [x] `uv run pytest` e `ruff` verdes.

## Decisões na implementação

- **Correlação por disciplina:** `correlacao_tempo_zscore` dá um Spearman por disciplina, não um sobre o z médio do concurso. O z é relativo ao próprio concurso, e a média dos z de um concurso fica perto de 0 por construção, então não mede tendência.
- **p exato:** com até 9 pontos, o p do Spearman é por permutação; a aproximação do scipy dá p = 0 para ordenação perfeita com 3 pontos.
- **Só pontos com n ≥ 5 nas séries:** tendência e correlação ignoram pontos com amostra insuficiente, como o gráfico de linha. Nos dados reais, uma tendência "significativa" (p = 0,027) vinha de 10 questões em 4 concursos.
- **Estrato só nas séries:** `tendencia_por_disciplina` e `correlacao_tempo_zscore` aceitam `estrato='banca'`; as tabelas por concurso já trazem a banca em cada linha, e o gráfico de linha também estratifica.
