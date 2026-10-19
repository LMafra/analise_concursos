import re
from dataclasses import dataclass

_LINHA = re.compile(r'^\s*(\d+)\s*(?:[:;,.\-]\s*|\s+|$)([A-Za-z*\-]?)\s*$')
_CABECALHO = re.compile(r'^\s*quest[aã]o\b', re.IGNORECASE)


class LinhaInvalidaError(ValueError):
    def __init__(self, numero_linha: int, conteudo: str, motivo: str):
        super().__init__(f'linha {numero_linha}: {motivo}: {conteudo.strip()!r}')
        self.numero_linha = numero_linha


@dataclass(frozen=True)
class LinhaQuestao:
    numero_linha: int
    questao: int
    valor: str | None


def ler_linhas(texto: str) -> list[LinhaQuestao]:
    """Lê linhas no formato 'número separador valor' ('1 A', '01: A', '1-C', '1,A').

    Linhas vazias e comentários (#) são ignorados; '-' ou valor ausente viram None.
    Um cabeçalho 'questao,...' na primeira linha útil é tolerado.
    """
    linhas: list[LinhaQuestao] = []
    vistas: set[int] = set()
    for numero_linha, conteudo in enumerate(texto.splitlines(), start=1):
        limpo = conteudo.strip()
        if not limpo or limpo.startswith('#'):
            continue
        if not linhas and _CABECALHO.match(limpo):
            continue
        casamento = _LINHA.match(limpo)
        if not casamento:
            raise LinhaInvalidaError(numero_linha, conteudo, 'formato não reconhecido')
        questao = int(casamento.group(1))
        if questao in vistas:
            raise LinhaInvalidaError(numero_linha, conteudo, f'questão {questao} duplicada')
        vistas.add(questao)
        valor = casamento.group(2).upper() or None
        linhas.append(LinhaQuestao(numero_linha, questao, None if valor == '-' else valor))
    return linhas
