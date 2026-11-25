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
from concursos.aplicacao.preferencias import aviso_webview2_dispensado, dispensar_aviso_webview2, tema_da_gui
from concursos.aplicacao.resultados import abrir_no_navegador
from concursos.config.contexto import resolver_home
from concursos.erros import avisar
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.marca import bloco_da_marca
from concursos.gui.estado import ESTADO, projeto_inicial
from concursos.gui.paginas import (
    analise,
    concursos,
    conferir,
    configuracoes,
    disciplinas_e_temas,
    estudar,
    inicio,
    novo_concurso,
    projeto,
    radar,
    respostas,
    resultados,
    sobre,
)
from concursos.gui.tema import Tom
from concursos.modelo import DecisaoJanela
from concursos.produto import NOME

HOST = '127.0.0.1'
TAMANHO_JANELA = (1200, 820)
NOME_DO_APP = NOME

logger = logging.getLogger('concursos')

MENU: list[tuple[str, str, str]] = [
    ('/', 'Minhas Provas', 'assignment'),
    ('/resultados', 'Resultados', 'insights'),
    ('/estudar', 'Estudar', 'menu_book'),
    ('/concursos', 'Concursos', 'travel_explore'),
]
UTILITARIO: list[tuple[str, str, str]] = [
    ('/configuracoes', 'Configurações', 'settings'),
    ('/sobre', 'Sobre', 'info'),
]
ENDERECOS_ANTIGOS = {
    'descobrir': '/concursos?aba=encontrar',
    'provas': '/concursos?aba=provas',
    'notebook': '/configuracoes?secao=avancado',
    'tec': '/?aba=tec',
}


def integracoes_antigas(aba: str | None = None) -> None:
    ui.navigate.to(ENDERECOS_ANTIGOS.get(aba or '', ENDERECOS_ANTIGOS['descobrir']))


def descobrir_antigo() -> None:
    ui.navigate.to(ENDERECOS_ANTIGOS['descobrir'])


def tec_antigo() -> None:
    ui.navigate.to('/?aba=tec')


ROTAS: dict[str, Callable[..., None]] = {
    '/': concursos.pagina,
    '/inicio': inicio.pagina,
    '/novo': novo_concurso.pagina,
    '/respostas': respostas.pagina,
    '/analise': analise.pagina,
    '/resultados': resultados.pagina,
    '/estudar': estudar.pagina,
    '/concursos': radar.pagina,
    '/tec': tec_antigo,
    '/integracoes': integracoes_antigas,
    '/descobrir': descobrir_antigo,
    '/projeto': projeto.pagina,
    '/configuracoes': configuracoes.pagina,
    '/conferir': conferir.pagina,
    '/disciplinas': disciplinas_e_temas.pagina,
    '/sobre': sobre.pagina,
}


def titulo() -> str:
    return f'{NOME_DO_APP} {sobre.versao()}'


def raiz() -> None:
    ui.page_title(titulo())
    tema.aplicar_tema(tema_da_gui(resolver_home() / 'config.toml'))
    with (
        # value=False: no mobile o drawer começa fechado; show-if-above abre fixo no desktop.
        ui.left_drawer(value=False)
        .props('bordered show-if-above breakpoint=1023 width=240')
        .style('background: var(--ca-superficie)') as menu
    ):
        bloco_da_marca()
        for caminho, nome, icone in MENU:
            ui.button(nome, icon=icone, on_click=lambda c=caminho: ui.navigate.to(c)).props(
                'flat align=left'
            ).classes('w-full ca-alvo').mark(f'menu-{caminho.strip("/") or "provas"}')
        ui.separator().classes('q-my-sm')
        for caminho, nome, icone in UTILITARIO:
            ui.button(nome, icon=icone, on_click=lambda c=caminho: ui.navigate.to(c)).props(
                'flat align=left'
            ).classes('w-full ca-alvo').mark(f'menu-{caminho.strip("/")}')
        if ESTADO.no_navegador:
            ui.button('Fechar o app', icon='power_settings_new', on_click=fechar_app).props(
                'flat align=left'
            ).classes('w-full ca-alvo').mark('fechar-app')
    with ui.header().classes('items-center').style(tema.gap('sm')):
        ui.button(icon='menu', on_click=menu.toggle).props('flat round aria-label="Abrir menu"').classes(
            'ca-alvo'
        )
        ui.label(NOME_DO_APP).classes('text-lg font-bold')
        ui.space()
        campo_busca = (
            ui.input(placeholder='Buscar concurso ou tópico')
            .props('dense outlined clearable')
            .classes('w-64')
            .mark('busca-global')
        )
        resultados_busca = (
            ui.column()
            .classes('absolute z-10 shadow-md p-2 ca-borda')
            .style(
                'top: 3.5rem; right: 1rem; min-width: 16rem; display: none; background: var(--ca-superficie)'
            )
        )

        def ao_buscar() -> None:
            from concursos.aplicacao import busca

            resultados_busca.clear()
            termo = campo_busca.value or ''
            if ESTADO.projeto is None or not termo.strip():
                resultados_busca.style('display: none')
                return
            achados = busca.procurar(ESTADO.contexto(), termo)
            with resultados_busca:
                if not achados:
                    ui.label('Nada encontrado.').classes('text-sm')
                for item in achados:
                    ui.button(
                        f'{item.tipo}: {item.rotulo}',
                        on_click=lambda r=item.rota: ui.navigate.to(r),
                    ).props('flat dense').classes('w-full')
            resultados_busca.style('display: block')

        campo_busca.on('update:model-value', ao_buscar)
        ui.button(icon='new_releases', on_click=lambda: ui.navigate.to('/sobre')).props(
            'flat dense no-caps'
        ).bind_text_from(
            ESTADO, 'novidade', lambda n: f'Versão {n.versao} disponível' if n else ''
        ).bind_visibility_from(ESTADO, 'novidade', backward=bool).mark('chip-atualizacao')
    with ui.column().classes('w-full p-4').style(tema.gap('md')):
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
    with (
        aviso(janela.TITULO_AVISO, janela.TEXTO_AVISO, tom=Tom.ALERTA, icone='web_asset_off').mark(
            'aviso-janela'
        ) as cartao,
        ui.row().classes('items-center').style(tema.gap('sm')),
    ):
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
    ui.notify(f'O {NOME_DO_APP} foi fechado. Pode fechar esta aba.', type='positive', timeout=0)
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
    avisar(
        logger,
        'A janela do app não abriu; vou abrir no navegador.',
        detalhe=f'janela nativa falhou; reabrindo: {" ".join(comando)}',
    )
    subprocess.Popen(comando, env={**os.environ, janela.VARIAVEL_JANELA_FALHOU: '1'})  # noqa: S603


def executar(
    pasta: Path | None = None, *, navegador: bool = False, porta: int | None = None, abrir: bool = True
) -> None:
    """O navegador é aberto pelo `abrir_no_navegador` da CLI, que acha o do Windows no WSL."""
    from concursos.aplicacao.lixeira import esvaziar

    home = resolver_home()
    esvaziar(home)
    inicial = pasta or projeto_inicial(Path.cwd(), home / 'config.toml')
    if inicial is not None:
        ESTADO.abrir_projeto(inicial)
        esvaziar(ESTADO.contexto().projeto)
    decisao = decidir_janela(navegador)
    nativa = decisao is DecisaoJanela.NATIVA
    ESTADO.decisao_janela = decisao
    ESTADO.janela_falhou = os.environ.get(janela.VARIAVEL_JANELA_FALHOU) == '1'
    ESTADO.no_navegador = not nativa
    ESTADO.cliente_conectou = False
    ESTADO.janela_reaberta = False
    if decisao is DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2:
        avisar(
            logger,
            'Falta um componente do Windows para a janela do app; abri no navegador.',
            'instale o Microsoft Edge WebView2 ou reinstale o app, que já traz esse componente.',
            'WebView2 não encontrado',
        )
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
