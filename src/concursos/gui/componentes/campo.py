"""Campo com o nome acima da caixa, no formato do protótipo."""

from collections.abc import Callable
from typing import TypeVar

from nicegui import ui

from concursos.gui import tema
from concursos.gui.textos import rotulo

Elemento = TypeVar('Elemento', bound=ui.element)


def campo(nome: str, elemento: Elemento, *, marca: str | None = None) -> Elemento:
    """Rótulo acima + caixa outlined sem o nome flutuante do Quasar."""
    with ui.column().classes('ca-campo w-full'):
        ui.label(nome).classes('ca-rotulo-campo')
        marcado = rotulo(
            elemento.props('outlined dense').classes('w-full ca-seletor'),
            nome.lower(),
        )
        if marca:
            marcado.mark(marca)
        return marcado


def titulo_da_pagina(texto: str) -> ui.label:
    return ui.label(texto).classes('ca-titulo-pagina')


def frase_da_pagina(texto: str) -> ui.label:
    return ui.label(texto).classes('ca-texto-suave')


def cabecalho_da_pagina(
    titulo: str,
    frase: str,
    *,
    ao_lado: Callable[[], None] | None = None,
) -> None:
    with ui.row().classes('ca-cabecalho'):
        with ui.column().style(tema.gap('xs')):
            titulo_da_pagina(titulo)
            frase_da_pagina(frase)
        if ao_lado is not None:
            ao_lado()
