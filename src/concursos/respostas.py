import csv
import io
import unicodedata
from collections.abc import Iterable

from concursos.linhas import LinhaInvalidaError, ler_linhas
from concursos.modelo import Estado, Formato, Origem, RespostaMarcada

_SEM_RESPOSTA = frozenset({'', '-'})
_COLUNAS_ALTERNATIVA = ('alternativa', 'alternativa_marcada')


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


def ler_respostas_csv(
    conteudo: bytes,
    formato: Formato,
    questoes: Iterable[int],
    arquivo: str,
    alternativas: int | None = None,
    origem: Origem = Origem.MANUAL,
) -> list[RespostaMarcada]:
    """CSV `questao,alternativa` ou o `respostas_extraidas.csv` revisado (`alternativa_marcada`); omitidas viram
    branco. Aceita o que o Excel grava: `;` como separador, BOM e cp1252."""
    esperadas = set(questoes)
    texto = _decodificar(conteudo)
    leitor = csv.reader(io.StringIO(texto), delimiter=_separador(texto))
    cabecalho = [_normalizar(coluna) for coluna in next(leitor, [])]
    if 'questao' not in cabecalho:
        raise RespostasInvalidasError(
            f"{arquivo}: coluna 'questao' ausente (use as colunas questao,alternativa)"
        )
    coluna = next((c for c in _COLUNAS_ALTERNATIVA if c in cabecalho), None)
    if coluna is None:
        raise RespostasInvalidasError(
            f"{arquivo}: coluna 'alternativa' ausente (use as colunas questao,alternativa)"
        )
    indice_questao, indice_alternativa = cabecalho.index('questao'), cabecalho.index(coluna)
    indice_estado = cabecalho.index('estado') if 'estado' in cabecalho else None
    letras = formato.letras(alternativas)

    lidas: dict[int, RespostaMarcada] = {}
    for numero, campos in enumerate(leitor, start=2):
        celulas = [c.strip() for c in campos]
        if not any(celulas):
            continue
        celulas += [''] * (len(cabecalho) - len(celulas))
        bruto = celulas[indice_questao]
        if not bruto.isdigit():
            raise RespostasInvalidasError(f'{arquivo}: linha {numero}: questão {bruto!r} inválida')
        questao = int(bruto)
        if questao not in esperadas:
            raise RespostasInvalidasError(
                f'{arquivo}: linha {numero}: questão {questao} fora das faixas configuradas'
            )
        if questao in lidas:
            raise RespostasInvalidasError(f'{arquivo}: linha {numero}: questão {questao} repetida')
        valor = celulas[indice_alternativa].upper()
        if valor not in _SEM_RESPOSTA and valor not in letras:
            validas = ', '.join(sorted(letras))
            raise RespostasInvalidasError(
                f'{arquivo}: linha {numero}: resposta {valor!r} inválida (use {validas} ou -)'
            )
        alternativa = None if valor in _SEM_RESPOSTA else valor
        multipla = (
            alternativa is None and indice_estado is not None and celulas[indice_estado] == Estado.MULTIPLA
        )
        lidas[questao] = _resposta(
            questao, alternativa, arquivo, origem, Estado.MULTIPLA if multipla else None
        )

    return [lidas.get(questao) or _resposta(questao, None, arquivo, origem) for questao in sorted(esperadas)]


def _decodificar(conteudo: bytes) -> str:
    try:
        return conteudo.decode('utf-8-sig')
    except UnicodeDecodeError:
        return conteudo.decode('cp1252')


def _separador(texto: str) -> str:
    cabecalho = texto.partition('\n')[0]
    return max(',;\t', key=cabecalho.count)


def _normalizar(coluna: str) -> str:
    return unicodedata.normalize('NFKD', coluna).encode('ascii', 'ignore').decode().strip().lower()


def _resposta(
    questao: int,
    alternativa: str | None,
    arquivo: str,
    origem: Origem = Origem.MANUAL,
    estado: Estado | None = None,
) -> RespostaMarcada:
    estado = estado or (Estado.MARCADA if alternativa else Estado.BRANCO)
    return RespostaMarcada(questao, alternativa, estado, 1.0, origem, arquivo)
