"""Tela Concursos: prospecção PCI e provas anteriores (fora de Minhas Provas)."""

from collections.abc import Callable

from nicegui import ui

from concursos.gui import tema
from concursos.gui.paginas.encontrar import PainelEncontrar, PainelProvasAnteriores
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro

ABAS = {
    'encontrar': ('Encontrar concursos', 'travel_explore'),
    'provas': ('Provas anteriores', 'history'),
}


def pagina(aba: str | None = None) -> None:
    if not exigir_projeto():
        return
    from concursos.gui.componentes.campo import cabecalho_da_pagina

    with ui.column().classes('w-full').style(tema.gap('lg')):
        cabecalho_da_pagina(
            'Concursos',
            'Editais abertos compatíveis com seu objetivo e provas anteriores para treinar.',
        )
        with ui.tabs().classes('w-full') as abas:
            guias = {
                chave: ui.tab(titulo, icon=icone).mark(f'aba-{chave}')
                for chave, (titulo, icone) in ABAS.items()
            }
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
