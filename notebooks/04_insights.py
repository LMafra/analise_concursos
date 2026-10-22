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
# # 04 · Insights
#
# **Pergunta:** o que as análises anteriores dizem, em conclusões acionáveis? Quatro perguntas: em quais
# disciplinas melhorei de forma significativa, quais tópicos continuam fracos, qual a correlação entre a
# ordem e o desempenho, e se o ranking de concursos muda entre bruto, corrigido e ajustado.
#
# Tudo no ajustado ao acaso, com a evolução lida pelo z-score. As respostas abaixo são geradas a partir
# dos dados; a conclusão no fim as interpreta.

# %%
from IPython.display import Markdown

from concursos.analytics.consolidado import carregar_consolidado
from concursos.analytics.evolucao import comparar_com_meta
from concursos.analytics.insights import (
    calcular_achados,
    gravar_relatorio_evolucao,
    respostas_em_markdown,
    sensibilidade_em_markdown,
)
from concursos.analytics.visualizacao import resumir
from concursos.configuracao import configuracao_do_projeto

consolidado = carregar_consolidado()
limiar = configuracao_do_projeto().limiar_topico_baixo
achados = calcular_achados(consolidado, limiar)

# %%
Markdown(respostas_em_markdown(achados))

# %% [markdown]
# ## Distância até a meta
#
# Nota normalizada pelo edital (anulada vale ponto, truncada em 0) contra a meta de 70%, por concurso e
# variante. O CPNU aparece com as 3 variantes.

# %%
resumir(comparar_com_meta(consolidado), n=12)

# %% [markdown]
# ## Sensibilidade: sem o nível médio
#
# Os achados recalculados sem os concursos de nível médio (hoje, só o `cd_25`):

# %%
Markdown(sensibilidade_em_markdown(consolidado, achados))

# %% [markdown]
# ## Relatório de evolução
#
# As respostas, a sensibilidade e as imagens estáticas da linha de evolução, do heatmap e do painel de
# correção vão para a pasta do consolidado.

# %%
gravar_relatorio_evolucao(consolidado, limiar=limiar)

# %% [markdown]
# ## Conclusão
#
# 1. **Nenhuma disciplina melhorou de forma significativa.** Só 10 séries têm 3 concursos ou mais com
#    n ≥ 5, e com 3 ou 4 pontos só um efeito enorme chegaria a p < 0,05. O sinal mais forte é Segurança
#    da Informação (+0,81 z por concurso, p = 0,11, n = 45). Não dá para afirmar melhora em nada.
# 2. **Sete tópicos são fracos persistentes, e quatro resistem à saída do `cd_25`.** O principal é
#    "Domínio da estrutura morfossintática do período": 36 questões em 6 concursos, abaixo de 60% em
#    todos, com 28% ajustado. Sem o `cd_25`, saem "Noções de organização administrativa", "Domínio dos
#    mecanismos de coesão textual" e "Agentes públicos", que só tinham dois concursos abaixo e um deles
#    era o de nível médio. Ficam a morfossintaxe, a reescrita de frases, a gestão de contratação de TI e
#    DevOps, a lista mais segura para priorizar.
# 3. **O desempenho geral não melhora com o tempo.** Entre a ordem e o percentual ajustado de cada
#    concurso, ρ = −0,53 (p = 0,15, 9 concursos); sem o `cd_25`, ρ = −0,40 (p = 0,33). Por disciplina, 4
#    séries sobem e 6 descem, nenhuma com p < 0,05. A média dos z-scores não serve para isso, porque fica
#    perto de 0 por construção. Ressalva: as três provas FGV são as primeiras (ordem 2 a 4) e as Cebraspe
#    vêm depois, então parte do ρ negativo é a troca de banca, que o ajuste ao acaso não iguala por
#    completo; o z-score por disciplina é a leitura livre desse efeito.
# 4. **O ranking muda muito, e isso é um achado.** Todas as 11 linhas mudam de posição, até 6 posições.
#    O CPNU vai de 6º no bruto para 1º no ajustado, o `tcu_25` cai de 1º para 3º, e o `cprm` sobe de 9º
#    para 3º no corrigido (FGV sem penalidade) e volta a 7º no ajustado. O ranking bruto não compara
#    bancas; para isso, use o ajustado.
#
# Nenhum concurso bateu a meta de 70%. O mais perto foi o CPNU, com 63% nas variantes B3-08-A e B3-10-A;
# o mais longe, o `funpresp_jud`, com 15%.
