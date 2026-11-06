from collections.abc import Callable

from nicegui import ui

from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.cartao import cartao
from concursos.gui.tema import Tom


def texto_do_aviso(texto: str, marca: str) -> ui.label:
    with aviso('O que sai do computador', tom=Tom.ALERTA):
        return ui.label(texto).classes('text-sm whitespace-pre-line').mark(f'aviso-{marca}')


def consentimento(texto: str, marca: str, ao_ligar: Callable[[], None]) -> None:
    """Integração desligada: o que sai do computador vem antes do botão de ligar."""
    with cartao('Desligada. Ao ligar:'):
        texto_do_aviso(texto, marca)
        ui.button('Concordo e ligar', icon='check', on_click=ao_ligar).mark(f'ligar-{marca}')
