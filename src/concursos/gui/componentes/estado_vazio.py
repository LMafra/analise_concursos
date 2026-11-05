from collections.abc import Callable

from nicegui import ui

from concursos.gui import tema


def estado_vazio(
    icone: str,
    titulo: str,
    texto: str,
    *,
    acao: str | None = None,
    ao_clicar: Callable[[], object] | None = None,
    icone_da_acao: str = 'arrow_forward',
    marca: str,
) -> ui.card:
    """Tela sem conteúdo: diz o que falta e oferece o botão que resolve; o botão leva `<marca>-acao`."""
    with (
        ui.card()
        .classes('w-full max-w-4xl items-center text-center ca-borda')
        .style(f'{tema.gap("sm")}; padding: {tema.ESPACOS["xl"]}; box-shadow: none')
        .mark(marca) as elemento
    ):
        ui.icon(icone, size='xl').classes('ca-texto-suave').props('aria-hidden=true')
        ui.label(titulo).classes('text-lg font-bold')
        ui.label(texto).classes('ca-texto-suave')
        if acao:
            ui.button(acao, icon=icone_da_acao, on_click=ao_clicar).mark(f'{marca}-acao')
    return elemento
