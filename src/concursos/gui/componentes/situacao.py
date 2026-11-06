from nicegui import ui

from concursos.gui import tema
from concursos.gui.tema import ICONE_DO_TOM, Tom


def situacao(texto: str, tom: Tom, *, icone: str | None = None) -> ui.row:
    """Um status com ícone e texto, para quem não distingue as cores."""
    with ui.row().classes(f'items-center no-wrap ca-tom-{tom} ca-situacao').style(tema.gap('xs')) as linha:
        ui.icon(icone or ICONE_DO_TOM[tom], size='xs').classes('ca-icone-tom').props('aria-hidden=true')
        ui.label(texto)
    return linha
