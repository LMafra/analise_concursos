import pandas as pd

from concursos.pratica.simulado_build import pagina_simulado
from concursos.pratica.tabelas import topico_do_erro
from concursos.topicos import NAO_MAPEADO, chave_de_palavras

FORA_DO_EDITAL = 'fora_do_edital'
MAXIMO_SIMULADO = 40
MAXIMO_SIMULADO_POR_TOPICO = 10
MAXIMO_REPETIDOS = 20


def questoes_do_simulado(
    erros: list[dict], aliases: dict[str, str | None], fracos: pd.DataFrame | None
) -> tuple[list[dict], bool]:
    """Os erros dos tópicos fracos, na ordem dos fracos e dos mais repetidos; sem cruzamento, os mais repetidos.
    Devolve também se o cruzamento com os tópicos fracos achou algum erro."""
    por_repeticao = sorted(erros, key=lambda e: (-(e.get('v') or 1), e['id']))
    por_topico: dict[str, list[dict]] = {}
    for e in por_repeticao:
        topico = topico_do_erro(e.get('ass'), aliases)
        if topico not in (NAO_MAPEADO, FORA_DO_EDITAL):
            por_topico.setdefault(chave_de_palavras(topico), []).append(e)
    escolhidos: list[dict] = []
    for fraco in fracos.itertuples() if fracos is not None else []:
        do_topico = por_topico.get(chave_de_palavras(str(fraco.topico)), [])
        escolhidos += do_topico[: min(MAXIMO_SIMULADO_POR_TOPICO, MAXIMO_SIMULADO - len(escolhidos))]
        if len(escolhidos) >= MAXIMO_SIMULADO:
            break
    if escolhidos:
        return escolhidos, True
    return por_repeticao[:MAXIMO_REPETIDOS], False


def simulado_html(erros: list[dict], aliases: dict[str, str | None], fracos: pd.DataFrame | None) -> str:
    """Uma página para refazer as questões erradas, com as respostas só no fim."""
    questoes, cruzou = questoes_do_simulado(erros, aliases, fracos)
    explicacao = (
        'As questões que você errou no TEC nos seus tópicos mais fracos da prova, das mais repetidas para as menos.'
        if cruzou
        else 'Nenhum erro do TEC caiu nos tópicos fracos da prova; estas são as questões que você mais errou.'
    )
    return pagina_simulado(questoes, explicacao)
