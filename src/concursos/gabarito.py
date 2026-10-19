import re
from dataclasses import dataclass
from pathlib import Path

from concursos.linhas import LinhaInvalidaError, ler_linhas
from concursos.modelo import Formato, ItemGabarito
from concursos.texto import extrair_texto

MARCAS_ANULADA = frozenset({'X', '*'})
_PRELIMINAR = re.compile(r'gabaritos?\s+(oficia(l|is)\s+)?preliminar', re.IGNORECASE)
_DEFINITIVO = re.compile(r'gabaritos?\s+(oficia(l|is)\s+)?definitivos?', re.IGNORECASE)


class GabaritoInvalidoError(ValueError):
    pass


def detectar_status(texto: str) -> str | None:
    if _DEFINITIVO.search(texto):
        return 'definitivo'
    if _PRELIMINAR.search(texto):
        return 'preliminar'
    return None


def ler_gabarito_cebraspe(texto: str, arquivo: str) -> list[ItemGabarito]:
    """Lê a grade 'Item ... / Gabarito ...' da Cebraspe; X = anulado, zeros são preenchimento."""
    itens: list[ItemGabarito] = []
    numeros: list[str] | None = None
    for linha in texto.splitlines():
        tokens = linha.split()
        if not tokens:
            continue
        if tokens[0] == 'Item':
            numeros = tokens[1:]
        elif tokens[0] == 'Gabarito' and numeros is not None:
            valores = tokens[1:]
            if len(valores) != len(numeros):
                raise GabaritoInvalidoError(f'{arquivo}: linha Item/Gabarito desalinhada: {linha!r}')
            itens.extend(
                _item(numero, valor) for numero, valor in zip(numeros, valores, strict=True) if numero != '0'
            )
            numeros = None
    if not itens:
        raise GabaritoInvalidoError(f'{arquivo}: nenhuma linha Item/Gabarito encontrada')
    return itens


def _item(numero: str, valor: str) -> ItemGabarito:
    if valor in MARCAS_ANULADA:
        return ItemGabarito(int(numero), None, anulada=True)
    return ItemGabarito(int(numero), valor)


@dataclass(frozen=True)
class GabaritoCarregado:
    itens: list[ItemGabarito]
    status_detectado: str | None


def carregar_gabarito(caminho: Path, formato: Formato, banca: str) -> GabaritoCarregado:
    """Lê o gabarito do arquivo: PDF pelo parser da banca, txt/csv pelo formato manual."""
    if caminho.suffix.lower() != '.pdf':
        return GabaritoCarregado(
            ler_gabarito_texto(caminho.read_text(encoding='utf-8'), formato, caminho.name), None
        )
    texto = extrair_texto(caminho)
    if banca != 'cebraspe':
        raise GabaritoInvalidoError(
            f'{caminho.name}: leitura de gabarito em PDF da banca {banca!r} não suportada'
        )
    itens = ler_gabarito_cebraspe(texto, caminho.name)
    _validar_alternativas(itens, formato, caminho.name)
    return GabaritoCarregado(itens, detectar_status(texto))


def _validar_alternativas(itens: list[ItemGabarito], formato: Formato, arquivo: str) -> None:
    invalidos = [i for i in itens if not i.anulada and i.resposta not in formato.alternativas]
    if invalidos:
        exemplos = ', '.join(f'{i.questao}={i.resposta}' for i in invalidos[:5])
        raise GabaritoInvalidoError(f'{arquivo}: respostas incompatíveis com {formato}: {exemplos}')


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
