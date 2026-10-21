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
# # 00 · Carregamento
#
# **Pergunta:** a base consolidada está íntegra e comparável?
#
# Íntegra: uma linha por questão de cada concurso analisado, com colunas, tipos e domínios esperados.
# Comparável: cada concurso tem data da prova (para entrar na ordem cronológica) e regra de correção
# vinda do edital ou declarada no `concurso.yaml`, não do default.

# %%
from concursos.analytics.consolidado import (
    avisos_do_consolidado,
    carregar_consolidado,
    contar_questoes,
    perfil_por_concurso,
    raiz_do_projeto,
    validar_schema,
)
from concursos.analytics.visualizacao import resumir

consolidado = carregar_consolidado()

# %% [markdown]
# ## Validação
#
# Colunas, tipos e domínios, e o número de linhas igual à soma das tabelas de questões. Um concurso
# analisado sem `correcao.json` ou `concurso.yaml` fica fora do consolidado e reprova a contagem.
# Se algo estiver errado, a célula abaixo falha listando todos os problemas.

# %%
validar_schema(consolidado, contar_questoes(raiz_do_projeto() / 'analises'))
resumir(consolidado, n=5, contar='concurso')

# %% [markdown]
# ## Perfil de cada concurso
#
# Em ordem cronológica: data, regra de correção e de onde ela veio, número de questões, anuladas e
# variantes de peso.

# %%
perfil_por_concurso(consolidado)

# %% [markdown]
# ## Avisos de data e de correção
#
# Concursos sem data ficam fora das análises de tendência; correção no default ou com confiança baixa
# pede conferência do edital ou declaração no `concurso.yaml`.

# %%
avisos = avisos_do_consolidado(consolidado)
avisos if len(avisos) else 'Nenhum aviso: todos os concursos têm data e regra de correção confirmada.'

# %% [markdown]
# ## Conclusão
#
# Se a validação passou e não há avisos, a base está íntegra e comparável: cada questão aparece uma vez,
# cada concurso tem posição na ordem cronológica e a pontuação de cada item segue a regra do próprio
# edital. Os notebooks seguintes podem agregar por tópico e por concurso sem conferir a base de novo.
# Avisos de data tiram o concurso das tendências; avisos de correção tornam a nota daquele concurso
# provisória até a regra ser confirmada.
