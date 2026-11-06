"""Índice local dos livros (SQLite FTS5): a busca quando o open-notebook está fora e o localizador
do trecho com página dentro dos livros que ele apontou.

A coluna `radicais` guarda os radicais (snowball, português) das palavras da página; a busca casa
o radical em `radicais` ou como prefixo em `texto`, para que o trecho destacado venha do texto.
"""

import re
import sqlite3
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

VERSAO_INDICE = 1
TAMANHO_TRECHO = 32
INICIO_DESTAQUE = '«'
FIM_DESTAQUE = '»'
PALAVRAS_VAZIAS = frozenset(
    [
        'a',
        'ao',
        'aos',
        'as',
        'até',
        'com',
        'como',
        'da',
        'das',
        'de',
        'do',
        'dos',
        'e',
        'é',
        'em',
        'entre',
        'era',
        'essa',
        'esse',
        'esta',
        'este',
        'eu',
        'foi',
        'há',
        'isso',
        'isto',
        'já',
        'la',
        'lhe',
        'mais',
        'mas',
        'me',
        'mesmo',
        'na',
        'nas',
        'nem',
        'no',
        'nos',
        'o',
        'os',
        'ou',
        'para',
        'pela',
        'pelas',
        'pelo',
        'pelos',
        'por',
        'qual',
        'quando',
        'que',
        'quem',
        'se',
        'sem',
        'ser',
        'seu',
        'sua',
        'são',
        'também',
        'te',
        'tem',
        'um',
        'uma',
        'umas',
        'uns',
        'você',
        'qual',
        'quais',
        'sobre',
        'onde',
        'porque',
    ]
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS busca USING fts5(
    sha UNINDEXED, pagina UNINDEXED, texto, radicais, tokenize='unicode61 remove_diacritics 2'
);
"""


@dataclass(frozen=True)
class Trecho:
    sha: str
    pagina: int
    trecho: str
    relevancia: float


def sem_acento(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c))


@cache
def _stemmer():  # noqa: ANN202
    import snowballstemmer

    return snowballstemmer.stemmer('portuguese')


def palavras(texto: str) -> list[str]:
    return re.findall(r'\w+', sem_acento(texto).lower())


def radicais(texto: str) -> str:
    return ' '.join(_stemmer().stemWords(palavras(texto)))


def abrir(banco: Path) -> sqlite3.Connection:
    banco.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(banco, timeout=30)
    conexao.execute('PRAGMA journal_mode=WAL')
    conexao.executescript(ESQUEMA)
    versao = conexao.execute("SELECT valor FROM meta WHERE chave = 'versao_indice'").fetchone()
    if versao is None or int(versao[0]) != VERSAO_INDICE:
        _refazer_radicais(conexao)
    return conexao


def _refazer_radicais(conexao: sqlite3.Connection) -> None:
    linhas = conexao.execute('SELECT rowid, texto FROM busca').fetchall()
    with conexao:
        for rowid, texto in linhas:
            conexao.execute('UPDATE busca SET radicais = ? WHERE rowid = ?', (radicais(texto), rowid))
        conexao.execute(
            "INSERT OR REPLACE INTO meta (chave, valor) VALUES ('versao_indice', ?)", (str(VERSAO_INDICE),)
        )


def indexar_pagina(conexao: sqlite3.Connection, sha: str, pagina: int, texto: str) -> None:
    with conexao:
        conexao.execute('DELETE FROM busca WHERE sha = ? AND pagina = ?', (sha, pagina))
        if texto.strip():
            conexao.execute(
                'INSERT INTO busca (sha, pagina, texto, radicais) VALUES (?, ?, ?, ?)',
                (sha, pagina, texto, radicais(texto)),
            )


def remover(conexao: sqlite3.Connection, sha: str) -> None:
    with conexao:
        conexao.execute('DELETE FROM busca WHERE sha = ?', (sha,))


def paginas_do_livro(conexao: sqlite3.Connection, sha: str) -> list[tuple[int, str]]:
    return conexao.execute(
        'SELECT pagina, texto FROM busca WHERE sha = ? ORDER BY CAST(pagina AS INTEGER)', (sha,)
    ).fetchall()


def expressao(consulta: str, termos_extra: Iterable[str] = ()) -> str | None:
    """A expressão FTS5 da consulta: cada radical (sem palavras vazias) em `radicais` ou como prefixo
    em `texto`, e cada termo extra como frase exata; tudo em OR, ordenado pelo bm25."""
    termos = [p for p in palavras(consulta) if p not in PALAVRAS_VAZIAS and len(p) > 1]
    partes = [
        f'radicais : "{radical}" OR texto : "{radical}"*'
        for radical in dict.fromkeys(_stemmer().stemWords(termos))
    ]
    for extra in termos_extra:
        frase = ' '.join(palavras(extra))
        if frase:
            partes.append(f'texto : "{frase}"')
    return ' OR '.join(f'({parte})' for parte in partes) or None


def buscar(
    conexao: sqlite3.Connection,
    consulta: str,
    shas: Iterable[str] | None = None,
    limite: int = 20,
    termos_extra: Iterable[str] = (),
) -> list[Trecho]:
    alvo = expressao(consulta, termos_extra)
    if alvo is None:
        return []
    sql = (
        f"SELECT sha, pagina, snippet(busca, 2, '{INICIO_DESTAQUE}', '{FIM_DESTAQUE}', '…', {TAMANHO_TRECHO}),"
        ' bm25(busca) FROM busca WHERE busca MATCH ?'
    )
    parametros: list = [alvo]
    if shas is not None:
        lista = list(shas)
        if not lista:
            return []
        sql += f' AND sha IN ({",".join("?" * len(lista))})'
        parametros.extend(lista)
    sql += ' ORDER BY bm25(busca) LIMIT ?'
    parametros.append(limite)
    return [
        Trecho(sha, int(pagina), trecho, -relevancia)
        for sha, pagina, trecho, relevancia in conexao.execute(sql, parametros)
    ]


def localizar_trechos(conexao: sqlite3.Connection, sha: str, consulta: str, limite: int = 3) -> list[Trecho]:
    return buscar(conexao, consulta, shas=[sha], limite=limite)
