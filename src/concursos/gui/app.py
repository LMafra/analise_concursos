import logging
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from nicegui import app, native, run, ui

from concursos import janela
from concursos.aplicacao import atualizador as atualizacao
from concursos.aplicacao.preferencias import aviso_webview2_dispensado, dispensar_aviso_webview2
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
from concursos.modelo import DecisaoJanela

HOST = '127.0.0.1'
TAMANHO_JANELA = (1200, 820)

logger = logging.getLogger('concursos')

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
        ui.space()
        ui.button(icon='new_releases', on_click=lambda: ui.navigate.to('/sobre')).props(
            'flat dense no-caps color=white'
        ).bind_text_from(
            ESTADO, 'novidade', lambda n: f'Versão {n.versao} disponível' if n else ''
        ).bind_visibility_from(ESTADO, 'novidade', backward=bool).mark('chip-atualizacao')
        if ESTADO.no_navegador:
            ui.button('Fechar o app', icon='power_settings_new', on_click=fechar_app).props(
                'flat color=white'
            ).mark('fechar-app')
    with ui.column().classes('w-full p-4'):
        aviso_de_janela()
        ui.sub_pages(ROTAS).classes('w-full')


def aviso_de_janela() -> None:
    """Abrir no navegador quando a janela era esperada nunca acontece em silêncio."""
    if ESTADO.decisao_janela is None:
        return
    config_global = resolver_home() / 'config.toml'
    if not janela.mostrar_aviso(
        ESTADO.decisao_janela,
        dispensado=aviso_webview2_dispensado(config_global),
        janela_falhou=ESTADO.janela_falhou,
    ):
        return
    with ui.card().classes('w-full').props('role=alert').mark('aviso-janela') as cartao:
        with ui.row().classes('items-center no-wrap'):
            ui.icon('web_asset_off', size='md').props('aria-hidden=true')
            ui.label(janela.TITULO_AVISO).classes('text-bold')
        ui.label(janela.TEXTO_AVISO)
        with ui.row().classes('items-center'):
            ui.link('Baixar o WebView2 (Microsoft)', janela.URL_WEBVIEW2, new_tab=True).mark('link-webview2')

            def entendi() -> None:
                dispensar_aviso_webview2(config_global)
                cartao.set_visibility(False)

            ui.button('Entendi', on_click=entendi).props('flat').mark('dispensar-aviso-janela')


def fechar_app() -> None:
    """No navegador, fechar a aba não encerra o servidor: sem este botão, ele ficaria rodando escondido."""
    if ESTADO.ocupado:
        ui.notify('Espere a análise terminar para fechar o app.', type='warning')
        return
    ui.notify('O concurso-analise foi fechado. Pode fechar esta aba.', type='positive', timeout=0)
    ui.timer(0.5, app.shutdown, once=True)


def decidir_janela(navegador: bool) -> DecisaoJanela:
    return janela.decidir_janela(sys.platform, navegador=navegador)


async def verificar_ao_abrir() -> None:
    home = resolver_home()
    ESTADO.novidade = await run.io_bound(
        atualizacao.verificar_ao_abrir,
        home / 'config.toml',
        home / atualizacao.ARQUIVO_ESTADO,
        agora=datetime.now(UTC),
    )


def marcar_conexao() -> None:
    ESTADO.cliente_conectou = True


def ao_encerrar_a_janela() -> None:
    """O NiceGUI encerra com `os._exit` quando o processo da janela morre, e nada depois do `ui.run` roda;
    por isso a queda é percebida no `on_shutdown`."""
    if not ESTADO.cliente_conectou:
        reabrir_no_navegador()


def reabrir_no_navegador() -> None:
    """A janela nativa roda noutro processo; quando ela morre sem nunca ter carregado a página, o servidor
    sai sem que o usuário veja nada. Um processo novo, no navegador, mostra o aviso."""
    if ESTADO.janela_reaberta:
        return
    ESTADO.janela_reaberta = True
    comando = janela.comando_para_reabrir(
        congelado=bool(getattr(sys, 'frozen', False)), executavel=sys.executable, projeto=ESTADO.projeto
    )
    logger.warning('a janela nativa não abriu; reabrindo no navegador: %s', ' '.join(comando))
    subprocess.Popen(comando, env={**os.environ, janela.VARIAVEL_JANELA_FALHOU: '1'})  # noqa: S603


def executar(
    pasta: Path | None = None, *, navegador: bool = False, porta: int | None = None, abrir: bool = True
) -> None:
    """O navegador é aberto pelo `abrir_no_navegador` da CLI, que acha o do Windows no WSL."""
    inicial = pasta or projeto_inicial(Path.cwd(), resolver_home() / 'config.toml')
    if inicial is not None:
        ESTADO.abrir_projeto(inicial)
    decisao = decidir_janela(navegador)
    nativa = decisao is DecisaoJanela.NATIVA
    ESTADO.decisao_janela = decisao
    ESTADO.janela_falhou = os.environ.get(janela.VARIAVEL_JANELA_FALHOU) == '1'
    ESTADO.no_navegador = not nativa
    ESTADO.cliente_conectou = False
    ESTADO.janela_reaberta = False
    if decisao is DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2:
        logger.warning('WebView2 não encontrado: a GUI abre no navegador')
    porta = porta or native.find_open_port()
    if not nativa and abrir:
        app.on_startup(lambda: abrir_no_navegador(f'http://{HOST}:{porta}/'))
    if abrir and atualizacao.no_executavel():
        app.on_startup(verificar_ao_abrir)
    if nativa and abrir:
        app.on_connect(marcar_conexao)
        app.on_shutdown(ao_encerrar_a_janela)
    try:
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
    except Exception:
        if not nativa:
            raise
        logger.debug('falha ao abrir a janela nativa', exc_info=True)
        reabrir_no_navegador()
