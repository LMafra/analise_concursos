"""Tela Concursos: prospecção PCI e provas anteriores (fora de Minhas Provas)."""

from collections.abc import Callable

from nicegui import ui

from concursos.gui import tema
from concursos.gui.paginas.encontrar import PainelEncontrar, PainelProvasAnteriores
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro

ABAS = {'encontrar': 'Encontrar concursos', 'provas': 'Provas anteriores'}


def pagina(aba: str | None = None) -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full').style(tema.gap('md')):
        ui.label('Concursos').classes('text-2xl font-bold')
        ui.label('Editais abertos e provas anteriores para planejar o que vem.').classes('ca-texto-suave')
        with ui.tabs().classes('w-full') as abas:
            guias = {chave: ui.tab(titulo).mark(f'aba-{chave}') for chave, titulo in ABAS.items()}
        with ui.tab_panels(abas, value=guias.get(aba or '', guias['encontrar'])).classes('w-full'):
            with ui.tab_panel(guias['encontrar']):
                no_lugar(PainelEncontrar)
            with ui.tab_panel(guias['provas']):
                no_lugar(PainelProvasAnteriores)


def no_lugar(construir: Callable[[Callable[[], None]], object]) -> None:
    caixa = ui.column().classes('w-full')

    def montar() -> None:
        caixa.clear()
        with caixa:
            try:
                construir(montar)
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)

    montar()
