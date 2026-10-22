from collections.abc import Iterable

from concursos.linhas import LinhaInvalidaError, ler_linhas
from concursos.modelo import Estado, Formato, Origem, RespostaMarcada


class RespostasInvalidasError(ValueError):
    pass


def ler_respostas_txt(
    texto: str, formato: Formato, questoes: Iterable[int], arquivo: str, alternativas: int | None = None
) -> list[RespostaMarcada]:
    """Converte o respostas.txt em uma resposta por questão esperada; omitidas viram branco."""
    esperadas = sorted(set(questoes))
    try:
        linhas = ler_linhas(texto)
    except LinhaInvalidaError as erro:
        raise RespostasInvalidasError(f'{arquivo}: {erro}') from erro

    marcadas: dict[int, str | None] = {}
    for linha in linhas:
        if linha.questao not in esperadas:
            raise RespostasInvalidasError(
                f'{arquivo}: linha {linha.numero_linha}: questão {linha.questao} fora das faixas configuradas'
            )
        letras = formato.letras(alternativas)
        if linha.valor is not None and linha.valor not in letras:
            validas = ', '.join(sorted(letras))
            raise RespostasInvalidasError(
                f'{arquivo}: linha {linha.numero_linha}: resposta {linha.valor!r} inválida (use {validas} ou -)'
            )
        marcadas[linha.questao] = linha.valor

    return [_resposta(questao, marcadas.get(questao), arquivo) for questao in esperadas]


def _resposta(questao: int, alternativa: str | None, arquivo: str) -> RespostaMarcada:
    estado = Estado.MARCADA if alternativa else Estado.BRANCO
    return RespostaMarcada(questao, alternativa, estado, 1.0, Origem.MANUAL, arquivo)
