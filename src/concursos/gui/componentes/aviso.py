from nicegui import ui

from concursos.gui import tema
from concursos.gui.tema import ICONE_DO_TOM, Tom


def aviso(titulo: str, texto: str | None = None, *, tom: Tom = Tom.INFO, icone: str | None = None) -> ui.card:
    """Um aviso com ícone e texto (nunca só a cor); use com `with` para acrescentar links e botões."""
    papel = 'alert' if tom in {Tom.ERRO, Tom.ALERTA} else 'status'
    with (
        ui.card()
        .classes(f'w-full ca-aviso ca-tom-{tom}')
        .style(tema.gap('xs'))
        .props(f'role={papel}') as elemento
    ):
        with ui.row().classes('items-center no-wrap').style(tema.gap('sm')):
            ui.icon(icone or ICONE_DO_TOM[tom], size='sm').classes('ca-icone-tom').props('aria-hidden=true')
            ui.label(titulo).classes('font-bold')
        if texto:
            ui.label(texto).classes('whitespace-pre-line')
    return elemento
