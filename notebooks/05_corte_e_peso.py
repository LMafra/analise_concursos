# ---
# jupyter:
#   jupytext:
#     formats: py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 05 · Corte e peso
#
# **Pergunta:** pela regra de cada edital, quanto falta para os cortes, em que disciplina, e quanto o peso e
# o desconto por erro mexem na comparação entre concursos?
#
# Os cortes, o desempate e as peculiaridades vêm do edital estruturado de cada concurso (fase 3). A
# anulada vale ponto e acerto, como dizem os editais; o corte da discursiva fica fora do "atingido". Com
# `concurso_alvo` no `config.yaml`, as tabelas mostram só esse concurso; sem ele, todos.

# %%
from IPython.display import Markdown

from concursos.analytics.consolidado import (
    carregar_consolidado,
    cortes_por_concurso,
    raiz_do_projeto,
    regras_por_concurso,
)
from concursos.analytics.evolucao import (
    comparar_percentual_e_gap,
    gap_para_corte,
    gap_por_disciplina,
    nota_ponderada_por_disciplina,
    ranking_concursos_por_metrica,
    simular_cenario,
)
from concursos.analytics.insights import (
    descrever_simulacao,
    desempate_por_concurso,
    destaque_do_ranking,
    peculiaridades_do_edital,
)
from concursos.analytics.visualizacao import barras_gap_por_disciplina, resumir
from concursos.configuracao import carregar_configuracao_global

consolidado = carregar_consolidado()
regras = regras_por_concurso()
cortes = cortes_por_concurso(regras)
alvo = carregar_configuracao_global(raiz_do_projeto() / 'config.yaml').concurso_alvo
Markdown(
    f'Concurso-alvo: {alvo or "nenhum (todos os concursos)"}; {len(cortes)} concursos com cortes no edital.'
)

# %% [markdown]
# ## Gap para cada corte
#
# Uma linha por corte aplicável: a nota no escopo, na unidade do corte, e o gap absoluto e em pontos
# percentuais da nota máxima do escopo. `atingido` só é verdadeiro quando todos os cortes do concurso são
# satisfeitos.

# %%
gaps = gap_para_corte(consolidado, cortes, alvo)
resumir(gaps, n=40, contar='atingido')

# %% [markdown]
# ## Quanto melhorar em cada disciplina
#
# Cada disciplina comparada com a exigência do corte que mais a aperta: um corte de bloco ou do conjunto
# exige `corte / nota máxima` do escopo. Em cada concurso, a disciplina mais longe vem primeiro; `falta`
# está na unidade do corte. Barras transparentes têm n < 5.

# %%
por_disciplina = gap_por_disciplina(consolidado, cortes, alvo)
resumir(por_disciplina, n=20, contar='no_ritmo')

# %%
barras_gap_por_disciplina(por_disciplina)

# %% [markdown]
# ## Bruto, ponderado e gap, lado a lado

# %%
resumir(comparar_percentual_e_gap(consolidado, cortes, alvo), n=12)

# %% [markdown]
# ## O ranking entre as métricas
#
# Bruto conta acertos; corrigido aplica peso e desconto; ponderado aplica só o peso. O deslocamento é
# quantas posições o concurso sobe em relação ao bruto. A anulada vale acerto e ponto, como no gap; o
# ranking do notebook 02 a exclui, então os percentuais diferem nos concursos com anulada.

# %%
ranking = ranking_concursos_por_metrica(consolidado)
Markdown(destaque_do_ranking(ranking))

# %%
resumir(ranking, n=12)

# %% [markdown]
# ## Nota ponderada por disciplina
#
# O acerto vale o peso do item, sem desconto.

# %%
resumir(nota_ponderada_por_disciplina(consolidado, alvo), n=12)

# %% [markdown]
# ## Simulação: +20 p.p. em Língua Portuguesa
#
# A simulação converte erros e brancos em acertos na proporção atual e recalcula nota e gap; é uma
# estimativa de cenário, não uma previsão.

# %%
simulacao = simular_cenario(consolidado, cortes, 'Língua Portuguesa', 20, alvo)
Markdown(descrever_simulacao(simulacao, 'Língua Portuguesa', 20))

# %% [markdown]
# ## Desempate
#
# Os critérios de cada edital, na ordem das alíneas, sem cálculo.

# %%
resumir(desempate_por_concurso(regras, alvo), n=16)

# %% [markdown]
# ## Peculiaridades do edital
#
# As descobertas de alto impacto e os cortes que fogem da régua em pontos: corte em acertos, corte da
# discursiva, teto de classificados e a regra de anulação.

# %%
resumir(peculiaridades_do_edital(regras, alvo), n=45, contar='peculiaridade')

# %% [markdown]
# ## Conclusão
#
# 1. **Pela regra do edital, 5 dos 9 concursos atingem todos os cortes**: o CPNU nas três variantes (52
#    acertos contra 36), `tcu_25`, `infrasa`, `telebras` e `agsus`. O `agsus` passa por pouco, com 16
#    acertos contra 15 nos específicos (+3,3 p.p.). Os outros 4 param num corte:
#    - `funpresp_jud` e `cprm` nos específicos, a −15,7 e −15,0 p.p. (o `cprm` faz 14 de 20 acertos);
#    - `cd_25` nos gerais, com 10 pontos contra 18 (−8,9 p.p.);
#    - `pf_perito` no conjunto, com 40 contra 48 (−6,7 p.p.).
#
#    No `cprm`, os gerais ficam exatamente no corte (15 de 15), e Língua Portuguesa, com 1 acerto, fica no
#    mínimo da disciplina.
# 2. **44 das 115 disciplinas estão abaixo da exigência do corte que as aperta**; as de n < 5 aparecem
#    transparentes no gráfico. Com n ≥ 5, as mais longe são:
#    - Banco de Dados no `telebras`: −45,5% contra 30% exigidos, faltam 8,3 pontos;
#    - Legislação no `infrasa`: −63,3 p.p.;
#    - Previdência Complementar no `funpresp_jud`: −55,0 p.p.;
#    - Noções de Informática no `pf_perito`: −54,3 p.p.
#
#    O `telebras` atinge os cortes mesmo assim: outras disciplinas compensam dentro do bloco.
# 3. **O desconto por erro mexe no ranking; o peso, quase nada.** No corrigido, as provas FGV sem desconto
#    sobem (`agsus` 6 posições, `cprm` 5), o CPNU também sobe 5, e as Cebraspe caem 2 ou 3. No ponderado,
#    só o CPNU muda: as variantes B3-08-A e B3-10-A sobem 1 posição (63,3% contra 57,8% no bruto), e o
#    `cd_25` cai 1.
# 4. **Subir 20 p.p. em Língua Portuguesa não faz nenhum concurso passar a atingir os cortes** (é uma
#    estimativa). No `cd_25`, os gerais chegam ao corte (10 → 18 pontos), mas o conjunto continua a −4.
#    No `pf_perito`, o conjunto vai de −8 a −2, e os específicos seguem a −3. O gargalo do `cprm`, do
#    `funpresp_jud` e do `pf_perito` são os específicos.
# 5. **Peculiaridades:**
#    - os 9 editais atribuem a anulada a todos os candidatos;
#    - 7 cortes são em acertos, entre eles o do CPNU (36 acertos ao lado da nota ponderada);
#    - 7 concursos têm corte de discursiva, fora do "atingido";
#    - o `tcu_25` tem teto de 80 classificados, que não é nota mínima.
