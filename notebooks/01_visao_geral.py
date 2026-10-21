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
# # 01 · Visão geral e painel de correção
#
# **Pergunta:** quanto dá para concluir com esta base, e quanto a regra de correção muda a comparação
# entre concursos?
#
# Primeiro, o tamanho das amostras: com poucas questões por tópico, um acerto a mais muda muito o
# percentual. Depois, o mesmo desempenho em três réguas: bruta (acertos), corrigida pela regra do edital
# (desconto por erro na Cebraspe, pesos no CPNU) e ajustada ao acaso (um chute vale 0 em qualquer formato).

# %%
from concursos.analytics.consolidado import (
    N_MINIMO_TOPICO,
    carregar_consolidado,
    n_por_topico,
    perfil_de_n,
    topicos_por_n,
)
from concursos.analytics.evolucao import comparar_bruto_vs_corrigido
from concursos.analytics.visualizacao import painel_correcao, resumir

consolidado = carregar_consolidado()

# %% [markdown]
# ## Perfil de n
#
# Por concurso e prova: questões, anuladas, tópicos, tópicos com pelo menos 5 questões (`N_MINIMO_TOPICO`) e a
# mediana de questões por tópico. Questões sem tópico classificado não formam tópico.

# %%
resumir(perfil_de_n(consolidado), n=20, contar='concurso')

# %% [markdown]
# Quantas combinações de tópico e prova têm cada n. Só as da última faixa sustentam um percentual de
# tópico; o resto entra nas análises somado entre concursos ou por disciplina.

# %%
topicos_por_n(consolidado, min_n=N_MINIMO_TOPICO)

# %% [markdown]
# Os tópicos com mais questões em uma mesma prova.

# %%
resumir(n_por_topico(consolidado), n=15)

# %% [markdown]
# ## Bruto, corrigido e ajustado
#
# Ranking dos concursos nas três versões, sem as anuladas. O CPNU tem uma linha por variante de cargo,
# porque o peso dos eixos muda o corrigido; as posições contam concursos, e cada variante é posicionada
# contra os outros. O deslocamento é quantas posições o concurso sobe em relação ao ranking bruto
# (negativo: desce).

# %%
comparacao = comparar_bruto_vs_corrigido(consolidado)
comparacao.round(1)

# %%
painel_correcao(comparacao)

# %% [markdown]
# ## Conclusão
#
# A base é esparsa: a maioria dos tópicos tem uma ou duas questões por prova, e só uma minoria chega a
# 5. Percentual de tópico isolado não é evidência; as análises seguintes trabalham por disciplina
# canônica e somam tópicos entre concursos.
#
# A régua muda a comparação. Pelo bruto, as provas Cebraspe lideram; pela regra do edital, o desconto por
# erro as derruba e as provas FGV, sem desconto, sobem para o topo. Esse salto é mecânico: um chute vale
# 0 esperado na Cebraspe e 20% na FGV. O ajustado ao acaso põe os dois formatos na mesma escala e é a
# métrica padrão dos notebooks seguintes; o corrigido fica para comparar com a nota oficial de cada
# concurso.
