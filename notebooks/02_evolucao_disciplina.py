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
# # 02 · Evolução por disciplina
#
# **Pergunta:** estou melhorando em cada disciplina ao longo do tempo, com conhecimentos gerais e
# específicos separados?
#
# A leitura principal é o z-score: quanto a disciplina ficou acima ou abaixo da minha média naquela
# prova, escalado pelo n da disciplina. Ele independe da régua de cada banca, então compara Cebraspe e FGV.

# %%
from concursos.analytics.consolidado import carregar_consolidado
from concursos.analytics.evolucao import (
    correlacao_tempo_zscore,
    modelos_distintos,
    percentual_por_disciplina_ao_longo_do_tempo,
    tendencia_por_disciplina,
    zscore_por_disciplina,
)
from concursos.analytics.visualizacao import aviso_modelos, box_por_disciplina, linha_evolucao, resumir

consolidado = carregar_consolidado()
aviso_modelos(modelos_distintos(consolidado))

# %% [markdown]
# ## Percentual por disciplina
#
# Uma linha por concurso, bloco e disciplina canônica, com as três versões do percentual, a nota
# normalizada pelo edital e o n. `amostra_insuficiente` marca disciplinas com menos de 5 questões.

# %%
resumir(percentual_por_disciplina_ao_longo_do_tempo(consolidado), n=10, contar='bloco')

# %% [markdown]
# ## Evolução: série única
#
# Percentual ajustado e z-score ao longo da ordem cronológica, com a banca como cor dos pontos e o n no
# tamanho. Pontos com n < 5 ficam soltos e transparentes. O menu escolhe a disciplina.

# %%
zscores = zscore_por_disciplina(consolidado)
linha_evolucao(zscores)

# %% [markdown]
# ## Evolução estratificada por banca
#
# Uma linha por banca: separa a tendência real do efeito de trocar de banca.

# %%
linha_evolucao(zscores, estrato='banca')

# %% [markdown]
# ## Distribuição entre concursos
#
# Cada ponto é um concurso. Caixa estreita e longe de 0 é força ou fraqueza consistente.

# %%
box_por_disciplina(zscores)

# %% [markdown]
# ## Tendências
#
# Slope do z-score pela ordem, só com 3 pontos ou mais de n ≥ 5, da menor para a maior p-value. Depois,
# a mesma leitura por banca e a correlação de Spearman (p exato por permutação).

# %%
resumir(tendencia_por_disciplina(consolidado), n=12, contar='situacao')

# %%
resumir(tendencia_por_disciplina(consolidado, estrato='banca'), n=10, contar='situacao')

# %%
resumir(correlacao_tempo_zscore(consolidado), n=10)

# %% [markdown]
# ## Conclusão
#
# Nenhuma disciplina tem tendência significativa (p < 0,05). As séries com pontos suficientes cobrem
# três a oito concursos, e com tão poucos pontos só um efeito muito grande apareceria: por permutação,
# uma ordenação perfeita de 3 concursos tem p de 1/3, e de 4 concursos, p de 1/12.
#
# Os sinais mais fortes, ainda não conclusivos, estão nos conhecimentos específicos: Segurança da
# Informação e Banco de Dados sobem em relação à minha média; Contratações de TI, Governança e Gestão de
# TI, Engenharia de Software e Ciência de Dados e IA descem. Nos gerais, Língua Portuguesa, a disciplina
# com mais pontos, oscila em torno da média sem direção, com quedas fortes em provas pontuais.
#
# Como a base mistura três modelos de correção, só o ajustado e o z-score comparam níveis entre
# concursos; a estratificação por banca mostra que todas as séries com tendência são Cebraspe.
