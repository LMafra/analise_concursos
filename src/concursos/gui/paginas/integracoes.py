import logging

from nicegui import run, ui

from concursos.aplicacao import integracoes
from concursos.aplicacao.opcoes import Opcoes
from concursos.gui import tema
from concursos.gui.componentes.consentimento import texto_do_aviso
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.descobrir import PainelDescobrir, PainelProvasAnteriores
from concursos.gui.paginas.pratica_tec import PainelTec
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro, rotulo

logger = logging.getLogger('concursos')

ABAS = {
    'descobrir': 'Descobrir concursos',
    'provas': 'Provas anteriores',
    'notebook': 'open-notebook',
    'tec': 'Prática no TEC',
}


def pagina(aba: str | None = None) -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full max-w-4xl').style(tema.gap('md')):
        ui.label('Integrações').classes('text-2xl font-bold')
        ui.label(
            'Cada integração fica desligada até você ligar, e a tela mostra antes o que sai do computador.'
        ).classes('text-sm')
        with ui.tabs().classes('w-full') as abas:
            guias = {chave: ui.tab(titulo) for chave, titulo in ABAS.items()}
        with ui.tab_panels(abas, value=guias.get(aba or '', guias['descobrir'])).classes('w-full'):
            for chave, montar in (
                ('descobrir', lambda: PainelDescobrir('descobrir')),
                ('provas', lambda: PainelProvasAnteriores('provas')),
                ('notebook', PainelNotebook),
                ('tec', PainelTec),
            ):
                with ui.tab_panel(guias[chave]):
                    try:
                        montar()
                    except Exception as erro:  # noqa: BLE001
                        logger.debug('falha ao montar a aba %s', chave, exc_info=True)
                        mostrar_erro(erro)


class PainelNotebook:
    def __init__(self) -> None:
        contexto = ESTADO.contexto()
        configuracao = integracoes.configuracao_open_notebook(contexto)
        self.situacao = ui.label().mark('estado-notebook')
        self.descrever()
        if not configuracao.ativa:
            with ui.card().classes('w-full'):
                url = (
                    rotulo(ui.input('Endereço do open-notebook', value=configuracao.url), 'endereço')
                    .classes('w-full')
                    .mark('url-notebook')
                )
                aviso = texto_do_aviso(integracoes.aviso_open_notebook(url.value, configuracao), 'notebook')
                url.on_value_change(
                    lambda e: aviso.set_text(integracoes.aviso_open_notebook(e.value or '', configuracao))
                )
                ui.button('Concordo e ligar', icon='check', on_click=lambda: self.ligar(url.value)).mark(
                    'ligar-notebook'
                )
            return
        ui.label(
            'A sincronização também roda sozinha depois de cada análise; use o botão para mandar agora.'
        ).classes('text-sm')
        with ui.row():
            self.botao = ui.button('Sincronizar agora', icon='sync', on_click=self.sincronizar).mark(
                'sincronizar-notebook'
            )
            ui.button('Desligar', on_click=self.desligar).props('flat').mark('desligar-notebook')
        self.saida = ui.column().classes('w-full')

    def descrever(self) -> None:
        estado = integracoes.estado_open_notebook(ESTADO.contexto())
        if not estado.ligado:
            texto = 'Desligado: nada vai para o open-notebook.'
        elif estado.ultima_sincronizacao is None:
            texto = f'Ligado: {estado.url}; ainda não sincronizado.'
        else:
            texto = (
                f'Ligado: {estado.url}; última sincronização em {estado.ultima_sincronizacao:%d/%m/%Y %H:%M}.'
            )
        self.situacao.set_text(texto)

    def ligar(self, url: str | None) -> None:
        url = (url or '').strip()
        if not url:
            ui.notify('Informe o endereço do open-notebook.', type='warning')
            return
        try:
            integracoes.ligar_open_notebook(ESTADO.contexto(), url)
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        ui.navigate.to('/integracoes?aba=notebook')

    def desligar(self) -> None:
        try:
            integracoes.desligar_open_notebook(ESTADO.contexto())
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        ui.navigate.to('/integracoes?aba=notebook')

    async def sincronizar(self) -> None:
        if ESTADO.ocupado:
            return
        ESTADO.ocupado = True
        self.botao.disable()
        try:
            relatorio = await run.io_bound(
                integracoes.sincronizar, Opcoes(ESTADO.contexto(), todos=ESTADO.todos), todos=ESTADO.todos
            )
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha na sincronização pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            ESTADO.ocupado = False
            self.botao.enable()
        self.saida.clear()
        with self.saida:
            ui.label(relatorio.formatar()).classes('text-sm whitespace-pre-line').mark('sincronizado')
        self.descrever()
