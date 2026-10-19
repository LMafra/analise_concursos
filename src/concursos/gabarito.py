import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from concursos.linhas import LinhaInvalidaError, ler_linhas
from concursos.modelo import Formato, ItemGabarito
from concursos.texto import extrair_texto

MARCAS_ANULADA = frozenset({'X', '*'})
_PRELIMINAR = re.compile(r'gabaritos?\s+(oficia(l|is)\s+)?preliminar', re.IGNORECASE)
_DEFINITIVO = re.compile(r'gabaritos?\s+(oficia(l|is)\s+)?definitivos?', re.IGNORECASE)
_PADROES_STATUS = (('preliminar', _PRELIMINAR), ('definitivo', _DEFINITIVO))


class GabaritoInvalidoError(ValueError):
    pass


def detectar_status(texto: str) -> str | None:
    """Status pela primeira menção no texto (o título vem antes das instruções de recurso)."""
    mencoes = [(m.start(), status) for status, padrao in _PADROES_STATUS if (m := padrao.search(texto))]
    return min(mencoes)[1] if mencoes else None


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


@dataclass
class Secao:
    cargo: str
    tipo: str | None
    itens: list[ItemGabarito] = field(default_factory=list)


_CABECALHO_FGV = re.compile(
    r'^(?P<cargo>.+?)\s+-\s+(?:TIPO\s+)?(?P<tipo>\d+)(?:\s+-\s+Turno\b.*)?$', re.IGNORECASE
)
_CABECALHO_LISTA = re.compile(r'^\d{3}\s*-\s*\S.*$')
_PROVA_LISTA = re.compile(r'^PROVA\s+([A-Z])$', re.IGNORECASE)
_RESPOSTA_LISTA = re.compile(r'(\d{1,3}):\s*([A-EX*])(?=\s|$)')


def ler_secoes_fgv(texto: str, arquivo: str) -> list[Secao]:
    """Seções 'cargo - tipo [- Turno]' seguidas de pares de linhas números/respostas; * = anulada.

    Linhas que não são cabeçalho (títulos repetidos a cada página) não encerram a seção corrente.
    """
    secoes: list[Secao] = []
    numeros: list[int] | None = None
    for linha in texto.splitlines():
        tokens = linha.split()
        if not tokens:
            continue
        if all(token.isdigit() for token in tokens):
            if not secoes:
                raise GabaritoInvalidoError(
                    f'{arquivo}: linha de números antes de qualquer cabeçalho de cargo'
                )
            numeros = [int(token) for token in tokens]
            _validar_continuidade(secoes[-1], numeros[0], arquivo)
            continue
        if numeros is not None and len(tokens) == len(numeros):
            secoes[-1].itens.extend(_item(str(n), valor) for n, valor in zip(numeros, tokens, strict=True))
            numeros = None
            continue
        numeros = None
        if casamento := _CABECALHO_FGV.match(linha.strip()):
            secoes.append(Secao(casamento['cargo'].strip(), casamento['tipo']))
    return _nao_vazias(secoes, arquivo)


def ler_secoes_lista(texto: str, arquivo: str) -> list[Secao]:
    """Seções '<código> - <cargo>' opcionalmente divididas em 'PROVA A/B', com respostas 'NN: R'."""
    secoes: list[Secao] = []
    cargo: str | None = None
    for linha in texto.splitlines():
        limpa = linha.strip()
        if _CABECALHO_LISTA.match(limpa) and not _RESPOSTA_LISTA.search(limpa):
            cargo = limpa
            secoes.append(Secao(cargo, None))
        elif (prova := _PROVA_LISTA.match(limpa)) and cargo is not None:
            atual = secoes[-1]
            if atual.cargo == cargo and atual.tipo is None and not atual.itens:
                atual.tipo = prova[1].upper()
            else:
                secoes.append(Secao(cargo, prova[1].upper()))
        elif (respostas := _RESPOSTA_LISTA.findall(limpa)) and secoes:
            secoes[-1].itens.extend(_item(numero, valor) for numero, valor in respostas)
    return _nao_vazias(secoes, arquivo)


def selecionar_secao(secoes: list[Secao], cargo: str | None, tipo: str | int | None, arquivo: str) -> Secao:
    alvo_cargo = _normalizar(cargo or '')
    alvo_tipo = _normalizar_tipo(tipo)
    for secao in secoes:
        if _normalizar(secao.cargo) == alvo_cargo and _normalizar_tipo(secao.tipo) == alvo_tipo:
            return secao
    disponiveis = '; '.join(f'{s.cargo} (tipo {s.tipo})' for s in secoes)
    raise GabaritoInvalidoError(
        f'{arquivo}: seção cargo={cargo!r} tipo={tipo!r} não encontrada; disponíveis: {disponiveis}'
    )


def _normalizar(texto: str) -> str:
    sem_acento = ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c))
    return ' '.join(sem_acento.replace('–', '-').casefold().split())


def _normalizar_tipo(tipo: str | int | None) -> str | None:
    if tipo is None:
        return None
    return re.sub(r'^(tipo|prova)\s*', '', _normalizar(str(tipo))) or None


def _validar_continuidade(secao: Secao, primeiro: int, arquivo: str) -> None:
    if primeiro != len(secao.itens) + 1:
        raise GabaritoInvalidoError(
            f'{arquivo}: seção {secao.cargo!r} (tipo {secao.tipo}) salta para a questão {primeiro} '
            f'após {len(secao.itens)} itens'
        )


def _nao_vazias(secoes: list[Secao], arquivo: str) -> list[Secao]:
    preenchidas = [s for s in secoes if s.itens]
    if not preenchidas:
        raise GabaritoInvalidoError(f'{arquivo}: nenhuma seção de gabarito encontrada')
    return preenchidas


def _item(numero: str, valor: str) -> ItemGabarito:
    if valor in MARCAS_ANULADA:
        return ItemGabarito(int(numero), None, anulada=True)
    return ItemGabarito(int(numero), valor)


@dataclass(frozen=True)
class GabaritoCarregado:
    itens: list[ItemGabarito]
    status_detectado: str | None


def carregar_gabarito(
    caminho: Path,
    formato: Formato,
    banca: str,
    cargo: str | None = None,
    tipo: str | int | None = None,
) -> GabaritoCarregado:
    """Lê o gabarito do arquivo: PDF pelo parser da banca, txt/csv pelo formato manual."""
    if caminho.suffix.lower() != '.pdf':
        return GabaritoCarregado(
            ler_gabarito_texto(caminho.read_text(encoding='utf-8'), formato, caminho.name), None
        )
    texto = extrair_texto(caminho)
    if banca == 'cebraspe':
        itens = ler_gabarito_cebraspe(texto, caminho.name)
    else:
        itens = selecionar_secao(_ler_secoes(texto, banca, caminho.name), cargo, tipo, caminho.name).itens
    _validar_alternativas(itens, formato, caminho.name)
    return GabaritoCarregado(itens, detectar_status(texto))


def listar_secoes(caminho: Path, banca: str) -> list[Secao]:
    """Seções (cargo, tipo) disponíveis num gabarito PDF com múltiplas seções."""
    return _ler_secoes(extrair_texto(caminho), banca, caminho.name)


def _ler_secoes(texto: str, banca: str, arquivo: str) -> list[Secao]:
    leitor = LEITORES_SECOES.get(banca)
    if leitor is None:
        raise GabaritoInvalidoError(f'{arquivo}: leitura de gabarito em PDF da banca {banca!r} não suportada')
    return leitor(texto, arquivo)


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


LEITORES_SECOES = {'fgv': ler_secoes_fgv, 'selecon': ler_secoes_lista, 'quadrix': ler_secoes_lista}
