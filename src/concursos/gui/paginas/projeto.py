from pathlib import Path

from nicegui import ui

from concursos.gui.componentes.seletor_pasta import escolher_pasta
from concursos.gui.estado import ESTADO, pasta_padrao
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.onboarding import precisa_de_onboarding


def pagina() -> None:
    with ui.column().classes('w-full max-w-2xl gap-4'):
        ui.label('Pasta do projeto').classes('text-2xl font-bold')
        ui.label(
            'É nesta pasta que ficam as provas (provas/), as análises (analises/) e a configuração (.concurso/). '
            'Nada sai do seu computador.'
        )
        if ESTADO.projeto is not None:
            ui.label(f'Pasta atual: {ESTADO.projeto}').mark('pasta-atual')
        campo = rotulo(
            ui.input('Pasta', value=str(ESTADO.projeto or pasta_padrao())).classes('w-full'),
            'pasta do projeto',
        ).mark('campo-pasta')

        async def procurar() -> None:
            escolhida = await escolher_pasta(Path(campo.value).expanduser())
            if escolhida is not None:
                campo.value = str(escolhida)

        def usar() -> None:
            try:
                ESTADO.abrir_projeto(Path(campo.value))
                novo = precisa_de_onboarding(ESTADO.contexto())
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            ui.navigate.to('/inicio' if novo else '/')

        with ui.row():
            ui.button('Escolher pasta…', icon='folder_open', on_click=procurar).props('outline')
            ui.button('Usar esta pasta', icon='check', on_click=usar).mark('usar-projeto')


def exigir_projeto() -> bool:
    """Sem projeto escolhido, a tela vira a escolha da pasta."""
    if ESTADO.projeto is None:
        pagina()
        return False
    return True
