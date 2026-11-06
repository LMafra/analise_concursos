"""A biblioteca local (`~/.concurso/biblioteca/`): o catálogo dos livros, o estado de cada um e a
leitura em segundo plano, num processo à parte, retomável da última página lida.
"""

import hashlib
import json
import logging
import multiprocessing
import shutil
import sqlite3
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from concursos.livros import indice, leitura
from concursos.livros.validacao import validar
from concursos.modelo import EstadoLivro

logger = logging.getLogger(__name__)

DISCIPLINA_PADRAO = 'Geral'
TENTATIVAS_LEITURA = 2
MENSAGEM_ILEGIVEL = 'Não foi possível ler este arquivo.'

ESQUEMA = """
CREATE TABLE IF NOT EXISTS livros (
    sha TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    extensao TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    disciplina TEXT NOT NULL,
    concursos TEXT NOT NULL DEFAULT '[]',
    estado TEXT NOT NULL,
    pagina INTEGER NOT NULL DEFAULT 0,
    paginas INTEGER NOT NULL DEFAULT 0,
    paginas_sem_texto INTEGER NOT NULL DEFAULT 0,
    erro TEXT NOT NULL DEFAULT '',
    adicionado_em TEXT NOT NULL,
    source_id TEXT NOT NULL DEFAULT '',
    notebook_id TEXT NOT NULL DEFAULT ''
);
"""
COLUNAS = (
    'sha',
    'nome',
    'extensao',
    'tamanho',
    'disciplina',
    'concursos',
    'estado',
    'pagina',
    'paginas',
    'paginas_sem_texto',
    'erro',
    'adicionado_em',
    'source_id',
    'notebook_id',
)


@dataclass(frozen=True)
class PastasBiblioteca:
    base: Path

    @classmethod
    def do_home(cls, home: Path) -> 'PastasBiblioteca':
        return cls(home / 'biblioteca')

    @property
    def arquivos(self) -> Path:
        return self.base / 'arquivos'

    @property
    def banco(self) -> Path:
        return self.base / 'biblioteca.sqlite'


@dataclass(frozen=True)
class Livro:
    sha: str
    nome: str
    extensao: str
    tamanho: int
    disciplina: str
    concursos: tuple[str, ...]
    estado: EstadoLivro
    pagina: int = 0
    paginas: int = 0
    paginas_sem_texto: int = 0
    erro: str = ''
    adicionado_em: str = ''
    source_id: str = ''
    notebook_id: str = ''

    def arquivo(self, pastas: PastasBiblioteca) -> Path:
        return pastas.arquivos / f'{self.sha}{self.extensao}'


@dataclass(frozen=True)
class Adicao:
    livro: Livro
    novo: bool


def conectar(pastas: PastasBiblioteca) -> sqlite3.Connection:
    conexao = indice.abrir(pastas.banco)
    conexao.executescript(ESQUEMA)
    return conexao


def _livro(linha: tuple) -> Livro:
    dados = dict(zip(COLUNAS, linha, strict=True))
    dados['concursos'] = tuple(json.loads(dados['concursos']))
    dados['estado'] = EstadoLivro(dados['estado'])
    return Livro(**dados)


def sha256(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open('rb') as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b''):
            resumo.update(bloco)
    return resumo.hexdigest()


def obter(conexao: sqlite3.Connection, sha: str) -> Livro | None:
    linha = conexao.execute(f'SELECT {", ".join(COLUNAS)} FROM livros WHERE sha = ?', (sha,)).fetchone()
    return _livro(linha) if linha else None


def listar(conexao: sqlite3.Connection) -> list[Livro]:
    linhas = conexao.execute(
        f'SELECT {", ".join(COLUNAS)} FROM livros ORDER BY adicionado_em, nome'
    ).fetchall()
    return [_livro(linha) for linha in linhas]


def atualizar(conexao: sqlite3.Connection, sha: str, **campos) -> None:
    if 'estado' in campos:
        campos['estado'] = EstadoLivro(campos['estado']).value
    if 'concursos' in campos:
        campos['concursos'] = json.dumps(sorted(campos['concursos']), ensure_ascii=False)
    atribuicoes = ', '.join(f'{nome} = ?' for nome in campos)
    with conexao:
        conexao.execute(f'UPDATE livros SET {atribuicoes} WHERE sha = ?', (*campos.values(), sha))


def adicionar(
    pastas: PastasBiblioteca,
    caminho: Path,
    *,
    disciplina: str | None = None,
    concursos: Iterable[str] = (),
    agora: datetime | None = None,
) -> Adicao:
    """Copia o livro para a biblioteca e o põe na fila; o mesmo conteúdo (pelo SHA-256) atualiza só a
    disciplina e os concursos."""
    extensao = validar(caminho)
    sha = sha256(caminho)
    conexao = conectar(pastas)
    try:
        existente = obter(conexao, sha)
        if existente is not None:
            juntos = set(existente.concursos) | set(concursos)
            atualizar(conexao, sha, disciplina=disciplina or existente.disciplina, concursos=juntos)
            return Adicao(obter(conexao, sha), False)  # type: ignore[arg-type]
        pastas.arquivos.mkdir(parents=True, exist_ok=True)
        destino = pastas.arquivos / f'{sha}{extensao}'
        temporario = destino.with_suffix('.parcial')
        shutil.copyfile(caminho, temporario)
        temporario.replace(destino)
        quando = (agora or datetime.now()).isoformat(timespec='seconds')
        with conexao:
            conexao.execute(
                'INSERT INTO livros (sha, nome, extensao, tamanho, disciplina, concursos, estado, adicionado_em)'
                ' VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    sha,
                    caminho.stem,
                    extensao,
                    caminho.stat().st_size,
                    disciplina or DISCIPLINA_PADRAO,
                    json.dumps(sorted(set(concursos)), ensure_ascii=False),
                    EstadoLivro.NA_FILA.value,
                    quando,
                ),
            )
        return Adicao(obter(conexao, sha), True)  # type: ignore[arg-type]
    finally:
        conexao.close()


def remover(pastas: PastasBiblioteca, sha: str) -> Livro | None:
    """Tira o livro do catálogo, do índice e da pasta; o envio apaga a cópia do open-notebook antes."""
    conexao = conectar(pastas)
    try:
        livro = obter(conexao, sha)
        if livro is None:
            return None
        indice.remover(conexao, sha)
        with conexao:
            conexao.execute('DELETE FROM livros WHERE sha = ?', (sha,))
    finally:
        conexao.close()
    livro.arquivo(pastas).unlink(missing_ok=True)
    return livro


def ler_livro(banco: Path, arquivo: Path, sha: str, ocr: leitura.Ocr | None = leitura.ocr_da_pagina) -> None:
    """Lê o livro a partir da última página registrada, indexando página a página (roda no processo da fila)."""
    pastas = PastasBiblioteca(banco.parent)
    conexao = conectar(pastas)
    try:
        livro = obter(conexao, sha)
        if livro is None:
            return
        total = livro.paginas or leitura.contar_paginas(arquivo)
        sem_texto = livro.paginas_sem_texto
        atualizar(conexao, sha, estado=EstadoLivro.LENDO, paginas=total, erro='')
        for pagina in leitura.ler_paginas(arquivo, desde=livro.pagina + 1, ocr=ocr):
            indice.indexar_pagina(conexao, sha, pagina.numero, pagina.texto)
            sem_texto += not pagina.texto
            atualizar(conexao, sha, pagina=pagina.numero, paginas_sem_texto=sem_texto)
        atualizar(conexao, sha, estado=EstadoLivro.LIDO, pagina=total)
    finally:
        conexao.close()


def pendentes(conexao: sqlite3.Connection) -> list[Livro]:
    return [livro for livro in listar(conexao) if livro.estado in (EstadoLivro.NA_FILA, EstadoLivro.LENDO)]


AoMudar = Callable[[], None]


@dataclass
class Fila:
    """Lê os livros pendentes, um por vez, num processo à parte; um livro que derruba o processo
    duas vezes fica com erro, e a fila segue."""

    pastas: PastasBiblioteca
    ao_mudar: list[AoMudar] = field(default_factory=list)
    ler: Callable[..., None] = ler_livro
    _executor: ProcessPoolExecutor | None = None
    _trava: threading.Lock = field(default_factory=threading.Lock)
    _rodando: bool = False

    def _novo_executor(self) -> ProcessPoolExecutor:
        return ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context('spawn'))

    def _avisar(self) -> None:
        for chamada in self.ao_mudar:
            try:
                chamada()
            except Exception:
                logger.exception('falha ao avisar a mudança da fila')

    def processar(self) -> None:
        """Esvazia a fila (bloqueia); chamado em thread pela camada de aplicação."""
        with self._trava:
            if self._rodando:
                return
            self._rodando = True
        try:
            while True:
                conexao = conectar(self.pastas)
                try:
                    proximos = pendentes(conexao)
                finally:
                    conexao.close()
                if not proximos:
                    return
                self._ler(proximos[0])
                self._avisar()
        finally:
            with self._trava:
                self._rodando = False

    def _ler(self, livro: Livro) -> None:
        for tentativa in range(1, TENTATIVAS_LEITURA + 1):
            if self._executor is None:
                self._executor = self._novo_executor()
            try:
                self._executor.submit(
                    self.ler, self.pastas.banco, livro.arquivo(self.pastas), livro.sha
                ).result()
                return
            except BrokenProcessPool:
                logger.warning('a leitura de %s derrubou o processo (tentativa %d)', livro.nome, tentativa)
                self._executor = None
            except Exception:
                logger.exception('falha ao ler %s', livro.nome)
                break
        conexao = conectar(self.pastas)
        try:
            atualizar(conexao, livro.sha, estado=EstadoLivro.ERRO, erro=MENSAGEM_ILEGIVEL)
        finally:
            conexao.close()

    def encerrar(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
