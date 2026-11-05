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
WEBVIEW2 = r'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'

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
    ui.add_css('.nicegui-log .q-scrollarea__content { white-space: pre-wrap; overflow-wrap: anywhere; }')
    with ui.header().classes('items-center gap-1 flex-wrap'):
        ui.label('concurso-analise').classes('text-lg font-bold mr-4')
        for caminho, nome, icone in MENU:
            ui.button(nome, icon=icone, on_click=lambda c=caminho: ui.navigate.to(c)).props(
                'flat color=white'
            )
        if ESTADO.no_navegador:
            ui.space()
            ui.button('Fechar o app', icon='power_settings_new', on_click=fechar_app).props(
                'flat color=white'
            ).mark('fechar-app')
    with ui.column().classes('w-full p-4'):
        ui.sub_pages(ROTAS).classes('w-full')


def fechar_app() -> None:
    """No navegador, fechar a aba não encerra o servidor: sem este botão, ele ficaria rodando escondido."""
    if ESTADO.ocupado:
        ui.notify('Espere a análise terminar para fechar o app.', type='warning')
        return
    ui.notify('O concurso-analise foi fechado. Pode fechar esta aba.', type='positive', timeout=0)
    ui.timer(0.5, app.shutdown, once=True)


def webview2_instalado() -> bool:
    """O runtime do WebView2 registra a versão em `pv`, na máquina ou no usuário."""
    import winreg

    for raiz, chave in (
        (winreg.HKEY_LOCAL_MACHINE, rf'SOFTWARE\WOW6432Node\{WEBVIEW2}'),
        (winreg.HKEY_LOCAL_MACHINE, rf'SOFTWARE\{WEBVIEW2}'),
        (winreg.HKEY_CURRENT_USER, rf'Software\{WEBVIEW2}'),
    ):
        try:
            with winreg.OpenKey(raiz, chave) as aberta:
                versao, _ = winreg.QueryValueEx(aberta, 'pv')
        except OSError:
            continue
        if versao and versao != '0.0.0.0':
            return True
    return False


def usar_janela_nativa(navegador: bool = False) -> bool:
    """Janela nativa no Windows (com o WebView2) e no macOS; no Linux, o navegador (WebKitGTK e Qt variam
    demais).

    O navegador é aberto pelo `abrir_no_navegador` da CLI, que acha o do Windows no WSL."""
    if navegador or sys.platform == 'linux':
        return False
    return sys.platform != 'win32' or webview2_instalado()


def executar(
    pasta: Path | None = None, *, navegador: bool = False, porta: int | None = None, abrir: bool = True
) -> None:
    inicial = pasta or projeto_inicial(Path.cwd(), resolver_home() / 'config.toml')
    if inicial is not None:
        ESTADO.abrir_projeto(inicial)
    nativa = usar_janela_nativa(navegador)
    ESTADO.no_navegador = not nativa
    porta = porta or native.find_open_port()
    if not nativa and abrir:
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
