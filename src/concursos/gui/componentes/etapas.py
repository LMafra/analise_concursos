from collections.abc import Sequence

from nicegui import ui

from concursos.gui import tema


def etapas(nomes: Sequence[str], atual: int) -> ui.element:
    """O indicador de passos: feito, atual e por fazer, cada um com ícone e texto."""
    with (
        ui.element('ol')
        .classes('flex flex-wrap items-center list-none p-0 m-0')
        .style(tema.gap('md'))
        .props('aria-label="passos"')
        .mark('etapas') as lista
    ):
        for indice, nome in enumerate(nomes):
            if indice < atual:
                classe, icone = 'ca-etapa-feita', 'check_circle'
            elif indice == atual:
                classe, icone = 'ca-etapa-atual', 'radio_button_checked'
            else:
                classe, icone = 'ca-etapa', 'radio_button_unchecked'
            item = ui.element('li').classes(f'flex items-center {classe}').style(tema.gap('xs'))
            if indice == atual:
                item.props('aria-current=step')
            with item:
                ui.icon(icone, size='xs').props('aria-hidden=true')
                ui.label(f'{indice + 1}. {nome}')
    return lista
