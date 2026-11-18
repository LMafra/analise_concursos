"""Breadcrumb e voltar para profundidade > 2."""

from nicegui import ui

from concursos.gui import tema


def breadcrumb(*passos: tuple[str, str | None]) -> None:
    """Cada passo é (rótulo, caminho ou None se for a página atual)."""
    with ui.row().classes('items-center flex-wrap').style(tema.gap('xs')):
        for indice, (rotulo, caminho) in enumerate(passos):
            if indice:
                ui.label('›').classes('ca-texto-suave')
            if caminho:
                ui.button(rotulo, on_click=lambda c=caminho: ui.navigate.to(c)).props(
                    'flat dense no-caps'
                ).classes('ca-alvo')
            else:
                ui.label(rotulo).classes('font-medium')


def voltar(rotulo: str, caminho: str) -> None:
    ui.button(f'← {rotulo}', icon=None, on_click=lambda: ui.navigate.to(caminho)).props(
        'flat dense no-caps'
    ).classes('ca-alvo').mark('voltar')
