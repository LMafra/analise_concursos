import re
from collections.abc import Iterator
from itertools import groupby
from pathlib import Path
from typing import NamedTuple, TypedDict

import pdfplumber

from concursos.arquivos import lido_uma_vez
from concursos.concurso_config import FaixaDisciplina
from concursos.edital import titulo_legivel

TAMANHO_MINIMO_TITULO = 10.5
TAMANHO_MAXIMO_NUMERO = 13
MARGEM_VERTICAL = 0.06
SALTO_MAXIMO = 3
_NUMERO_QUESTAO = re.compile(r'^(\d{1,3})\.?$')


class Palavra(TypedDict):
    """O que o caderno usa de uma palavra do `extract_words` do pdfplumber."""

    text: str
    size: float
    fontname: str
    top: float
    x0: float


class Titulo(NamedTuple):
    nome: str


class Questao(NamedTuple):
    numero: int


Pagina = tuple[float, float, list[Palavra]]
Evento = Titulo | Questao


@lido_uma_vez
def faixas_do_caderno(caminho: Path, inicio: int) -> list[FaixaDisciplina]:
    with pdfplumber.open(caminho) as pdf:
        paginas = [
            (pagina.width, pagina.height, pagina.extract_words(extra_attrs=['size', 'fontname']))
            for pagina in pdf.pages
        ]
    return faixas_por_cabecalho(paginas, inicio)


def faixas_por_cabecalho(paginas: list[Pagina], inicio: int) -> list[FaixaDisciplina]:
    """Faixas de questões por disciplina a partir dos títulos em negrito dos cadernos FGV e SELECON.

    Cada coluna é lida de cima para baixo e a questão pertence ao último título visto. Um título
    'Conhecimentos ...' vale como disciplina até aparecer um subtítulo.
    """
    eventos = list(_eventos(paginas))
    partidas = [
        i for i, evento in enumerate(eventos) if isinstance(evento, Questao) and evento.numero == inicio
    ]
    if not partidas:
        return []
    melhor = max(reversed(partidas), key=lambda partida: len(_atribuir(eventos, partida, inicio)))
    disciplina_por_questao = _atribuir(eventos, melhor, inicio)
    faixas = []
    for nome, grupo in groupby(sorted(disciplina_por_questao.items()), key=lambda par: par[1]):
        questoes = [questao for questao, _ in grupo]
        faixas.append(FaixaDisciplina(questoes[0], questoes[-1], nome))
    return faixas


def _atribuir(eventos: list[Evento], partida: int, inicio: int) -> dict[int, str]:
    """Questões em sequência a partir de `partida` (capas e instruções também têm números em negrito)."""
    titulos = [evento.nome for evento in eventos[:partida] if isinstance(evento, Titulo)]
    disciplina = titulos[-1] if titulos else None
    atribuidas: dict[int, str] = {}
    ultima = inicio - 1
    for evento in eventos[partida:]:
        match evento:
            case Titulo(nome):
                disciplina = nome
            case Questao(numero) if ultima < numero <= ultima + SALTO_MAXIMO:
                ultima = numero
                if disciplina is not None:
                    atribuidas[numero] = disciplina
    return atribuidas


def _eventos(paginas: list[Pagina]) -> Iterator[Evento]:
    for largura, altura, palavras in paginas:
        negritos = [
            p
            for p in palavras
            if 'bold' in p['fontname'].lower()
            and altura * MARGEM_VERTICAL <= p['top'] <= altura * (1 - MARGEM_VERTICAL)
        ]
        for direita in (False, True):
            coluna = sorted(
                (p for p in negritos if (p['x0'] >= largura / 2) == direita),
                key=lambda p: (round(p['top']), p['x0']),
            )
            yield from _eventos_da_coluna(coluna)


def _eventos_da_coluna(palavras: list[Palavra]) -> Iterator[Evento]:
    pendente: list[str] = []
    topo_anterior = tamanho_anterior = 0.0
    for topo, grupo in groupby(palavras, key=lambda p: round(p['top'])):
        linha = list(grupo)
        if numero := _numero_da_questao(linha[0]):
            if pendente:
                yield _titulo(pendente)
                pendente = []
            yield Questao(numero)
            continue
        palavras_titulo = _palavras_de_titulo(linha)
        if not palavras_titulo:
            continue
        texto = ' '.join(p['text'] for p in palavras_titulo)
        continua = (
            pendente
            and topo - topo_anterior <= 1.6 * tamanho_anterior
            and not _eh_conhecimento(pendente[0])
            and not _eh_conhecimento(texto)
        )
        if pendente and not continua:
            yield _titulo(pendente)
            pendente = []
        pendente.append(texto)
        topo_anterior, tamanho_anterior = topo, max(p['size'] for p in palavras_titulo)
    if pendente:
        yield _titulo(pendente)


def _numero_da_questao(palavra: Palavra) -> int | None:
    encontrado = _NUMERO_QUESTAO.match(palavra['text'])
    return int(encontrado.group(1)) if encontrado and palavra['size'] < TAMANHO_MAXIMO_NUMERO else None


def _palavras_de_titulo(linha: list[Palavra]) -> list[Palavra]:
    grandes = [p for p in linha if p['size'] >= TAMANHO_MINIMO_TITULO]
    while grandes and grandes[-1]['text'].isdigit():
        grandes.pop()
    return grandes if any(c.isalpha() for p in grandes for c in p['text']) else []


def _eh_conhecimento(texto: str) -> bool:
    return texto.upper().startswith('CONHECIMENTOS')


def _titulo(linhas: list[str]) -> Titulo:
    return Titulo(titulo_legivel(' '.join(linhas)))
