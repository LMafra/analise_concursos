from typing import TypeVar

from nicegui import ui

from concursos.erros import ErroDoUsuario
from concursos.gui.progresso import arquivo_de_log

Elemento = TypeVar('Elemento', bound=ui.element)


def rotulo(elemento: Elemento, texto: str) -> Elemento:
    """`aria-label` para leitores de tela, em todo controle sem texto visível próprio."""
    elemento.props(f'aria-label="{texto}"')
    return elemento


def linhas_do_erro(erro: BaseException) -> tuple[str, str | None]:
    """O mesmo par `erro:` e `dica:` da CLI; o traceback fica só no arquivo de log."""
    if isinstance(erro, ErroDoUsuario):
        return f'erro: {erro.causa}', f'dica: {erro.dica}' if erro.dica else None
    if isinstance(erro, ValueError | FileNotFoundError):
        return f'erro: {erro}', None
    log = arquivo_de_log()
    return 'erro: falha inesperada', f'dica: detalhes em {log}' if log else None


def mostrar_erro(erro: BaseException) -> None:
    causa, dica = linhas_do_erro(erro)
    ui.notify(f'{causa}\n{dica}' if dica else causa, type='negative', multi_line=True, close_button='Fechar')
