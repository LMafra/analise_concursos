from concursos.linhas import LinhaInvalidaError, ler_linhas
from concursos.modelo import Formato, ItemGabarito

MARCAS_ANULADA = frozenset({'X', '*'})


class GabaritoInvalidoError(ValueError):
    pass


def validar_contagem(itens: list[ItemGabarito], questoes: range, prova: str, arquivo: str) -> None:
    encontradas = {item.questao for item in itens}
    esperadas = set(questoes)
    if encontradas == esperadas:
        return
    detalhes = []
    if faltando := sorted(esperadas - encontradas):
        detalhes.append(f'faltando {_resumir(faltando)}')
    if sobrando := sorted(encontradas - esperadas):
        detalhes.append(f'fora da faixa {_resumir(sobrando)}')
    raise GabaritoInvalidoError(
        f'{arquivo}: prova {prova} espera questões {questoes.start}-{questoes.stop - 1} '
        f'({len(esperadas)} itens), gabarito tem {len(itens)} itens; ' + '; '.join(detalhes)
    )


def _resumir(numeros: list[int], limite: int = 10) -> str:
    texto = ', '.join(map(str, numeros[:limite]))
    return texto + (f' (+{len(numeros) - limite})' if len(numeros) > limite else '')


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
