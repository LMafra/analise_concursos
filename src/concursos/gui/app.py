import sys
from collections.abc import Callable
from pathlib import Path

from nicegui import app, native, ui

from concursos.aplicacao.resultados import abrir_no_navegador
from concursos.config.contexto import resolver_home
from concursos.gui.estado import ESTADO, projeto_inicial
from concursos.gui.paginas import (
    analise,
    concursos,
    configuracoes,
    inicio,
    integracoes,
    novo_concurso,
    projeto,
    respostas,
    resultados,
    sobre,
)

HOST = '127.0.0.1'
TAMANHO_JANELA = (1200, 820)

MENU: list[tuple[str, str, str]] = [
    ('/', 'Concursos', 'list'),
    ('/analise', 'Analisar', 'play_arrow'),
    ('/resultados', 'Resultados', 'insights'),
    ('/integracoes', 'Integrações', 'hub'),
    ('/configuracoes', 'Configurações', 'settings'),
    ('/sobre', 'Sobre', 'info'),
]

ROTAS: dict[str, Callable[..., None]] = {
    '/': concursos.pagina,
    '/inicio': inicio.pagina,
    '/novo': novo_concurso.pagina,
    '/respostas': respostas.pagina,
    '/analise': analise.pagina,
    '/resultados': resultados.pagina,
    '/integracoes': integracoes.pagina,
    '/projeto': projeto.pagina,
    '/configuracoes': configuracoes.pagina,
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
    """Janela nativa no Windows e no macOS; no Linux, o navegador (WebKitGTK e Qt variam demais).

    O navegador é aberto pelo `abrir_no_navegador` da CLI, que acha o do Windows no WSL."""
    return not navegador and sys.platform != 'linux'


def executar(pasta: Path | None = None, *, navegador: bool = False, porta: int | None = None) -> None:
    inicial = pasta or projeto_inicial(Path.cwd(), resolver_home() / 'config.toml')
    if inicial is not None:
        ESTADO.abrir_projeto(inicial)
    nativa = usar_janela_nativa(navegador)
    porta = porta or native.find_open_port()
    if not nativa:
        app.on_startup(lambda: abrir_no_navegador(f'http://{HOST}:{porta}/'))
    ui.run(
        raiz,
        host=HOST,
        port=porta,
        reload=False,
        native=nativa,
        show=False,
        title=titulo(),
        language='pt-BR',
        show_welcome_message=False,
        **({'window_size': TAMANHO_JANELA} if nativa else {}),
    )
