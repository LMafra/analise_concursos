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
# # 03 · Evolução e fraquezas por tópico
#
# **Pergunta:** quais tópicos do edital foram cobrados e quais continuam fracos?
#
# A amostra por prova é pequena (mediana de 2 questões por tópico), então a leitura principal soma
# acertos e erros entre concursos. Tópico é a disciplina canônica mais as palavras-chave do nome, e o
# percentual é o ajustado ao acaso, que compara Cebraspe e FGV.

# %%
from concursos.analytics.consolidado import carregar_consolidado, raiz_do_projeto, topicos_do_edital
from concursos.analytics.evolucao import (
    cobertura_edital,
    evolucao_por_topico,
    percentual_por_topico,
    topicos_fracos_persistentes,
)
from concursos.analytics.visualizacao import barras_fracos, heatmap_topicos, resumir
from concursos.configuracao import carregar_configuracao_global

consolidado = carregar_consolidado()
limiar = carregar_configuracao_global(raiz_do_projeto() / 'config.yaml').limiar_topico_baixo

# %% [markdown]
# ## Cobertura do edital
#
# Quantos tópicos distintos do edital estruturado cada prova cobrou. O casamento é pelas palavras-chave
# do tópico. Tópicos nunca cobrados ficam fora da evolução, para não confundir ausência de questões com
# desempenho.

# %%
resumir(cobertura_edital(consolidado, topicos_do_edital()), n=10)

# %% [markdown]
# ## Tópicos por concurso
#
# Só tópicos cobrados em 2 concursos ou mais. A cor e o percentual aparecem onde n ≥ 5; o resto fica
# cinza com "n<5", e o branco é tópico não cobrado naquela prova.

# %%
heatmap_topicos(percentual_por_topico(consolidado, min_concursos=2))

# %% [markdown]
# ## Evolução por tópico
#
# Slope do percentual ajustado pela ordem, só com 3 pontos ou mais de n ≥ 5.

# %%
resumir(evolucao_por_topico(consolidado), n=5, contar='situacao')

# %% [markdown]
# ## Tópicos fracos persistentes
#
# Abaixo do `limiar_topico_baixo` do `config.yaml` (60%, no ajustado) em pelo menos 2 concursos, com n
# somado de pelo menos 5, do mais fraco para o mais forte.

# %%
fracos = topicos_fracos_persistentes(consolidado, limiar=limiar)
resumir(fracos, n=10)

# %%
barras_fracos(fracos)

# %% [markdown]
# ## Comparação com o comparativo da fase 1
#
# A fase 1 usava o percentual bruto, sem n mínimo e com os nomes de disciplina de cada edital. Os mesmos
# critérios sobre o consolidado:

# %%
resumir(topicos_fracos_persistentes(consolidado, limiar=limiar, usar='bruta', min_n=1), n=10)

# %% [markdown]
# ## Conclusão
#
# A cobertura do edital varia de 25% (cprm) a 100% (cpnu, cujo edital lista só os eixos temáticos). Todo
# tópico cobrado casa com um tópico do edital, como esperado, já que a fase 1 classifica as questões pelos
# tópicos do edital. Quase nenhum tópico tem série temporal: só
# "Domínio da estrutura morfossintática do período", de Língua Portuguesa, tem 3 concursos com n ≥ 5,
# e o slope dele não é significativo (p ≈ 0,8). Por tópico, a pergunta "estou melhorando?" não tem
# resposta com estes dados; a soma entre concursos é a leitura que sobra.
#
# Somando, sete tópicos são fracos persistentes. Os mais fracos são "Noções de organização
# administrativa" (Direito Administrativo) e "Domínio dos mecanismos de coesão textual" (Língua
# Portuguesa), com ajustado negativo. O mais importante é "Domínio da estrutura morfossintática do
# período": 36 questões em 6 concursos, abaixo do limiar em todos, com 64% bruto e 28% ajustado.
#
# A lista difere da fase 1 por três motivos:
#
# - **n mínimo:** dos três tópicos da fase 1, só "coesão textual" (n = 5) continua. "Compreensão de
#   textos variados" (Língua Inglesa) e "Desenvolvimento de sistemas" têm 3 questões somadas.
# - **Taxonomia:** com os critérios da fase 1, aparecem mais dois tópicos, "Noções de organização
#   administrativa" e "Estrutura lógica de relações arbitrárias". A fase 1 os separava porque o nome da
#   disciplina mudava entre editais ("Noções de Direito Administrativo" e "Direito Administrativo").
# - **Ajustado ao acaso:** na Cebraspe, um erro anula um acerto, então 60% bruto vira 20% ajustado.
#   Cinco dos sete tópicos só entram pelo ajustado: "Agentes públicos", "Reescrita de frases e
#   parágrafos", "Domínio da estrutura morfossintática do período", "Gestão de contratação de soluções
#   de TI" e "DevOps". É o critério certo para a Cebraspe, onde chutar custa ponto.
