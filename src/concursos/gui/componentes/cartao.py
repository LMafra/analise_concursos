from nicegui import ui

from concursos.gui import tema


def cartao(titulo: str | None = None, *, icone: str | None = None) -> ui.card:
    """Um cartão da largura da coluna; use com `with`, e o conteúdo vem depois do título."""
    with ui.card().classes('w-full').style(tema.gap('sm')) as elemento:
        if titulo:
            with ui.row().classes('items-center no-wrap').style(tema.gap('sm')):
                if icone:
                    ui.icon(icone).props('aria-hidden=true')
                ui.label(titulo).classes('text-lg font-bold')
    return elemento
