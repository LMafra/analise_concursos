from typing import TypeVar

from nicegui import ui

from concursos.erros import ErroDoUsuario
from concursos.gui.componentes.aviso import aviso
from concursos.gui.progresso import arquivo_de_log
from concursos.gui.tema import Tom
from concursos.linguagem import erro_para_a_tela

Elemento = TypeVar('Elemento', bound=ui.element)


def rotulo(elemento: Elemento, texto: str) -> Elemento:
    """`aria-label` para leitores de tela, em todo controle sem texto visível próprio."""
    elemento.props(f'aria-label="{texto}"')
    return elemento


def erro_da_tela(erro: BaseException) -> ErroDoUsuario:
    if isinstance(erro, ErroDoUsuario | ValueError | FileNotFoundError):
        return erro_para_a_tela(erro)
    log = arquivo_de_log()
    return ErroDoUsuario(
        'Algo deu errado e o app não terminou.', f'os detalhes estão em {log}.' if log else None
    )


def linhas_do_erro(erro: BaseException) -> tuple[str, str | None]:
    """O mesmo par `erro:` e `dica:` da CLI; o traceback fica só no arquivo de log."""
    traduzido = erro_da_tela(erro)
    return f'erro: {traduzido.causa}', f'dica: {traduzido.dica}' if traduzido.dica else None


def detalhes_tecnicos(detalhe: str | None) -> None:
    """Fechado: o leigo lê a causa e a dica, e o texto técnico fica a um clique."""
    if not detalhe:
        return
    with ui.expansion('Ver detalhes técnicos', icon='code').classes('w-full').mark('detalhes-tecnicos'):
        ui.label(detalhe).classes('text-sm font-mono whitespace-pre-line break-all')


def cartao_de_erro(erro: BaseException) -> ui.card:
    with aviso(*linhas_do_erro(erro), tom=Tom.ERRO) as cartao:
        detalhes_tecnicos(erro_da_tela(erro).detalhe)
    return cartao


def mostrar_erro(erro: BaseException) -> None:
    """Sem detalhe técnico, uma notificação; com ele, uma janela, porque a notificação não abre e fecha."""
    detalhe = erro_da_tela(erro).detalhe
    if not detalhe:
        causa, dica = linhas_do_erro(erro)
        ui.notify(
            f'{causa}\n{dica}' if dica else causa, type='negative', multi_line=True, close_button='Fechar'
        )
        return
    with ui.dialog(value=True) as janela, ui.card().classes('w-full').mark('janela-erro'):
        cartao_de_erro(erro)
        ui.button('Fechar', on_click=janela.delete).props('flat').mark('fechar-erro')
