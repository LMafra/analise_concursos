from collections.abc import Callable

from nicegui import ui


def texto_do_aviso(texto: str, marca: str) -> ui.label:
    return (
        ui.label(texto).classes('text-sm bg-amber-1 p-3 rounded whitespace-pre-line').mark(f'aviso-{marca}')
    )


def consentimento(texto: str, marca: str, ao_ligar: Callable[[], None]) -> None:
    """Integração desligada: o que sai do computador vem antes do botão de ligar."""
    with ui.card().classes('w-full'):
        ui.label('Desligada. Ao ligar:').classes('font-bold')
        texto_do_aviso(texto, marca)
        ui.button('Concordo e ligar', icon='check', on_click=ao_ligar).mark(f'ligar-{marca}')
