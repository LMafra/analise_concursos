from concursos.linhas import LinhaInvalidaError, ler_linhas
from concursos.modelo import Formato, ItemGabarito

MARCAS_ANULADA = frozenset({'X', '*'})


class GabaritoInvalidoError(ValueError):
    pass


def ler_gabarito_texto(texto: str, formato: Formato, arquivo: str) -> list[ItemGabarito]:
    """Lê o gabarito manual (txt/csv) no mesmo formato de linhas do respostas.txt; X ou * = anulada."""
    try:
        linhas = ler_linhas(texto)
    except LinhaInvalidaError as erro:
        raise GabaritoInvalidoError(f'{arquivo}: {erro}') from erro

    itens = []
    for linha in linhas:
        if linha.valor in MARCAS_ANULADA:
            itens.append(ItemGabarito(linha.questao, None, anulada=True))
        elif linha.valor in formato.alternativas:
            itens.append(ItemGabarito(linha.questao, linha.valor))
        else:
            raise GabaritoInvalidoError(
                f'{arquivo}: linha {linha.numero_linha}: gabarito {linha.valor!r} inválido para {formato}'
            )
    return itens
