from nicegui import ui

from concursos.gui import tema


class Dialogo(ui.dialog):
    """Título, `corpo` e `acoes` (alinhadas à direita); crie dentro de um elemento que continua na página."""

    def __init__(self, titulo: str, *, marca: str | None = None) -> None:
        super().__init__()
        with self:
            self.cartao = ui.card().classes('min-w-80 max-w-2xl').style(tema.gap('md'))
            self.cartao.props(f'role=dialog aria-label="{titulo}"')
            if marca:
                self.cartao.mark(marca)
            with self.cartao:
                ui.label(titulo).classes('text-lg font-bold')
                self.corpo = ui.column().classes('w-full').style(tema.gap('sm'))
                self.acoes = ui.row().classes('w-full justify-end').style(tema.gap('sm'))


def ver_texto(titulo: str, texto: str) -> None:
    """Um markdown longo num diálogo com "Fechar"."""
    with ui.dialog() as dialogo, ui.card().classes('w-full max-w-3xl'):
        ui.label(titulo).classes('text-lg font-bold')
        ui.markdown(texto).classes('w-full')
        ui.button('Fechar', on_click=dialogo.close).props('flat')
    dialogo.open()
