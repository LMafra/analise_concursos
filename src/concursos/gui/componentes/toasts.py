"""Toasts tipados: sucesso efêmero, erro persistente, Undo estilo Gmail."""

from collections.abc import Callable

from nicegui import ui


def sucesso(mensagem: str, *, segundos: float = 5) -> None:
    # Quasar: role=alert implícito no notify; timeout curto = efêmero.
    ui.notify(mensagem, type='positive', timeout=int(segundos * 1000), close_button=True, position='top')


def erro(mensagem: str) -> None:
    # timeout=0: permanece até fechar (erro persistente).
    ui.notify(mensagem, type='negative', timeout=0, close_button=True, position='top')


def com_desfazer(mensagem: str, ao_desfazer: Callable[[], None], *, segundos: float = 8) -> None:
    """Exclusão imediata + Desfazer. O timeout confirma a exclusão; só o botão desfaz."""
    ui.notify(
        mensagem,
        type='warning',
        timeout=int(segundos * 1000),
        close_button=False,
        actions=[{'label': 'Desfazer', 'color': 'white', 'handler': ao_desfazer}],
    )


def sujo_ao_sair(esta_sujo: Callable[[], bool], destino: str) -> None:
    """Navegação com alterações não salvas: pede para continuar editando."""
    if not esta_sujo():
        ui.navigate.to(destino)
        return
    with ui.dialog() as dialogo, ui.card():
        ui.label('Há alterações que ainda não foram salvas.')
        with ui.row():
            ui.button('Continuar editando', on_click=dialogo.close).props('flat')
            ui.button(
                'Sair sem salvar',
                on_click=lambda: (dialogo.close(), ui.navigate.to(destino)),
            )
    dialogo.open()
