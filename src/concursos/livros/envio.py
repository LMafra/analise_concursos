"""O envio dos livros lidos ao open-notebook gerenciado: um source de texto com as marcas `[p. N]` no
notebook `Biblioteca — <disciplina>`, compartilhado entre os projetos.
"""

import logging
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field

from concursos.integracoes.open_notebook import ClienteOpenNotebook, OpenNotebookIndisponivelError
from concursos.livros import fila, indice
from concursos.livros.fila import Livro, PastasBiblioteca
from concursos.modelo import EstadoLivro

logger = logging.getLogger(__name__)

PREFIXO_BIBLIOTECA = 'Biblioteca — '
DESCRICAO = 'livros enviados pelo concurso-analise'
MENSAGEM_FALHA = 'O open-notebook não conseguiu preparar este livro para perguntas.'

ESQUEMA = """
CREATE TABLE IF NOT EXISTS notebooks_biblioteca (disciplina TEXT PRIMARY KEY, notebook_id TEXT NOT NULL);
"""


def nome_do_notebook(disciplina: str) -> str:
    return f'{PREFIXO_BIBLIOTECA}{disciplina}'


def texto_com_paginas(paginas: Iterable[tuple[int, str]]) -> str:
    return '\n\n'.join(f'[p. {numero}]\n{texto}' for numero, texto in paginas if texto.strip())


@dataclass
class RelatorioEnvio:
    enviados: list[str] = field(default_factory=list)
    prontos: list[str] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)


def _conexao(pastas: PastasBiblioteca) -> sqlite3.Connection:
    conexao = fila.conectar(pastas)
    conexao.executescript(ESQUEMA)
    return conexao


def notebook_da_disciplina(cliente: ClienteOpenNotebook, conexao: sqlite3.Connection, disciplina: str) -> str:
    """O notebook da disciplina pelo ID guardado; sem ele, pelo nome (é compartilhado entre os projetos)."""
    linha = conexao.execute(
        'SELECT notebook_id FROM notebooks_biblioteca WHERE disciplina = ?', (disciplina,)
    ).fetchone()
    if linha and cliente.obter_notebook(linha[0]) is not None:
        return linha[0]
    nome = nome_do_notebook(disciplina)
    existente = cliente.buscar_notebook_por_nome(nome)
    notebook_id = existente['id'] if existente else cliente.criar_notebook(nome, DESCRICAO)['id']
    with conexao:
        conexao.execute(
            'INSERT OR REPLACE INTO notebooks_biblioteca (disciplina, notebook_id) VALUES (?, ?)',
            (disciplina, notebook_id),
        )
    return notebook_id


def _source_existe(cliente: ClienteOpenNotebook, source_id: str) -> bool:
    if not source_id:
        return False
    try:
        cliente.status_source(source_id)
    except OpenNotebookIndisponivelError as erro:
        if erro.status == 404:
            return False
        raise
    return True


def enviar_livro(cliente: ClienteOpenNotebook, pastas: PastasBiblioteca, livro: Livro) -> Livro:
    """Garante o source do livro no notebook da disciplina; trocar a disciplina só move o vínculo."""
    conexao = _conexao(pastas)
    try:
        notebook_id = notebook_da_disciplina(cliente, conexao, livro.disciplina)
        if _source_existe(cliente, livro.source_id):
            if livro.notebook_id != notebook_id:
                cliente.vincular_source(notebook_id, livro.source_id)
                if livro.notebook_id:
                    try:
                        cliente.desvincular_source(livro.notebook_id, livro.source_id)
                    except OpenNotebookIndisponivelError as erro:
                        if erro.status != 404:
                            raise
                fila.atualizar(conexao, livro.sha, notebook_id=notebook_id)
            return fila.obter(conexao, livro.sha)  # type: ignore[return-value]
        texto = texto_com_paginas(indice.paginas_do_livro(conexao, livro.sha))
        source = cliente.adicionar_source_texto(notebook_id, livro.nome, texto, embed=True, assincrono=True)
        fila.atualizar(
            conexao, livro.sha, source_id=source['id'], notebook_id=notebook_id, estado=EstadoLivro.ENVIANDO
        )
        return fila.obter(conexao, livro.sha)  # type: ignore[return-value]
    finally:
        conexao.close()


def conferir_envio(cliente: ClienteOpenNotebook, pastas: PastasBiblioteca, livro: Livro) -> Livro:
    status = cliente.status_source(livro.source_id).get('status')
    conexao = _conexao(pastas)
    try:
        if status == 'completed':
            fila.atualizar(conexao, livro.sha, estado=EstadoLivro.PRONTO, erro='')
        elif status == 'failed':
            fila.atualizar(conexao, livro.sha, estado=EstadoLivro.ERRO, erro=MENSAGEM_FALHA)
        return fila.obter(conexao, livro.sha)  # type: ignore[return-value]
    finally:
        conexao.close()


def processar_envios(cliente: ClienteOpenNotebook, pastas: PastasBiblioteca) -> RelatorioEnvio:
    """Envia os livros lidos e confere os que estão sendo preparados; uma falha num livro não para os outros."""
    relatorio = RelatorioEnvio()
    conexao = _conexao(pastas)
    try:
        livros = fila.listar(conexao)
    finally:
        conexao.close()
    for livro in livros:
        try:
            if livro.estado is EstadoLivro.LIDO:
                livro = enviar_livro(cliente, pastas, livro)
                relatorio.enviados.append(livro.nome)
            enviando = livro.estado is EstadoLivro.ENVIANDO
            if enviando and conferir_envio(cliente, pastas, livro).estado is EstadoLivro.PRONTO:
                relatorio.prontos.append(livro.nome)
        except OpenNotebookIndisponivelError as erro:
            logger.warning('livro %s: %s', livro.nome, erro.causa)
            relatorio.falhas.append(livro.nome)
    return relatorio


def mudar_disciplina(
    cliente: ClienteOpenNotebook | None, pastas: PastasBiblioteca, sha: str, disciplina: str
) -> Livro | None:
    conexao = _conexao(pastas)
    try:
        fila.atualizar(conexao, sha, disciplina=disciplina)
        livro = fila.obter(conexao, sha)
    finally:
        conexao.close()
    if livro is not None and cliente is not None and livro.source_id:
        return enviar_livro(cliente, pastas, livro)
    return livro


def remover_livro(cliente: ClienteOpenNotebook | None, pastas: PastasBiblioteca, sha: str) -> Livro | None:
    """Apaga o source no open-notebook (quando aberto), as linhas do índice e o arquivo."""
    conexao = _conexao(pastas)
    try:
        livro = fila.obter(conexao, sha)
    finally:
        conexao.close()
    if livro is None:
        return None
    if cliente is not None and livro.source_id:
        try:
            cliente.apagar_source(livro.source_id)
        except OpenNotebookIndisponivelError as erro:
            if erro.status != 404:
                raise
    return fila.remover(pastas, sha)


def sources_por_concurso(pastas: PastasBiblioteca) -> dict[str, set[str]]:
    """Concurso → sources dos livros associados a ele, para vincular ao notebook do concurso."""
    if not pastas.banco.exists():
        return {}
    conexao = _conexao(pastas)
    try:
        livros = fila.listar(conexao)
    finally:
        conexao.close()
    mapa: dict[str, set[str]] = {}
    for livro in livros:
        if livro.source_id:
            for concurso in livro.concursos:
                mapa.setdefault(concurso, set()).add(livro.source_id)
    return mapa


def livros_por_source(pastas: PastasBiblioteca) -> dict[str, Livro]:
    if not pastas.banco.exists():
        return {}
    conexao = _conexao(pastas)
    try:
        return {livro.source_id: livro for livro in fila.listar(conexao) if livro.source_id}
    finally:
        conexao.close()
