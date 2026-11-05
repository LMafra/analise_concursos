import sys
from collections.abc import Callable
from pathlib import Path

from nicegui import native, ui

from concursos.config.contexto import resolver_home
from concursos.gui.estado import ESTADO, projeto_inicial
from concursos.gui.paginas import analise, concursos, inicio, novo_concurso, projeto, respostas, sobre

HOST = '127.0.0.1'
TAMANHO_JANELA = (1200, 820)

MENU: list[tuple[str, str, str]] = [
    ('/', 'Concursos', 'list'),
    ('/analise', 'Analisar', 'play_arrow'),
    ('/projeto', 'Projeto', 'folder'),
    ('/sobre', 'Sobre', 'info'),
]

ROTAS: dict[str, Callable[..., None]] = {
    '/': concursos.pagina,
    '/inicio': inicio.pagina,
    '/novo': novo_concurso.pagina,
    '/respostas': respostas.pagina,
    '/analise': analise.pagina,
    '/projeto': projeto.pagina,
    '/sobre': sobre.pagina,
}


def titulo() -> str:
    return f'concurso-analise {sobre.versao()}'


def raiz() -> None:
    ui.page_title(titulo())
    with ui.header().classes('items-center gap-1 flex-wrap'):
        ui.label('concurso-analise').classes('text-lg font-bold mr-4')
        for caminho, nome, icone in MENU:
            ui.button(nome, icon=icone, on_click=lambda c=caminho: ui.navigate.to(c)).props(
                'flat color=white'
            )
    with ui.column().classes('w-full p-4'):
        ui.sub_pages(ROTAS).classes('w-full')


def usar_janela_nativa(navegador: bool = False) -> bool:
    """Janela nativa no Windows e no macOS; no Linux, o navegador (WebKitGTK e Qt variam demais)."""
    return not navegador and sys.platform != 'linux'


def executar(pasta: Path | None = None, *, navegador: bool = False, porta: int | None = None) -> None:
    inicial = pasta or projeto_inicial(Path.cwd(), resolver_home() / 'config.toml')
    if inicial is not None:
        ESTADO.abrir_projeto(inicial)
    nativa = usar_janela_nativa(navegador)
    ui.run(
        raiz,
        host=HOST,
        port=porta or native.find_open_port(),
        reload=False,
        native=nativa,
        title=titulo(),
        show_welcome_message=False,
        **({'window_size': TAMANHO_JANELA} if nativa else {}),
    )
