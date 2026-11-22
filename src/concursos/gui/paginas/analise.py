import logging
import threading

from nicegui import run, ui

from concursos.aplicacao import analise
from concursos.aplicacao.opcoes import Opcoes
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.navegacao import breadcrumb
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.progresso import Andamento, HandlerDoPainel
from concursos.gui.tema import Tom
from concursos.gui.textos import cartao_de_erro
from concursos.modelo import Etapa

logger = logging.getLogger('concursos')

ETAPAS_LEIGAS = {
    None: 'Preparando…',
    Etapa.LENDO_ARQUIVOS: 'Lendo gabarito e arquivos',
    Etapa.LENDO_FOLHA: 'Lendo a folha de respostas',
    Etapa.CORRIGINDO: 'Corrigindo as questões',
    Etapa.CLASSIFICANDO: 'Mapeando tópicos do edital',
    Etapa.GERANDO_RELATORIOS: 'Calculando distância do corte',
    Etapa.CONSOLIDANDO: 'Montando o diagnóstico',
}


def pagina() -> None:
    if not exigir_projeto():
        return
    breadcrumb(('Minhas Provas', '/'), ('Analisar', None))
    painel = PainelDeAnalise()
    if ESTADO.pedir_analise:
        ESTADO.pedir_analise = False
        ui.timer(0.1, painel.iniciar, once=True)


class PainelDeAnalise:
    def __init__(self) -> None:
        self.andamento = Andamento()
        self.cancelar = threading.Event()
        with ui.column().classes('w-full max-w-4xl').style(tema.gap('md')):
            self.titulo = (
                ui.label('Pronto para analisar o que mudou.')
                .classes('text-lg')
                .props('role=status aria-live=polite')
                .mark('titulo-analise')
            )
            ui.label(
                'A análise pode levar alguns minutos. Você pode cancelar; o que já tiver terminado fica.'
            ).classes('text-sm ca-texto-suave')
            self.barra = ui.linear_progress(value=0, show_value=False).props(
                'aria-label="andamento da análise"'
            )
            self.esqueleto = ui.skeleton().classes('w-full h-40').props('aria-hidden=true')
            self.esqueleto.set_visibility(False)
            self.resultado = ui.column().classes('w-full')
            with (
                ui.expansion('Ver detalhes técnicos de processamento', icon='list')
                .classes('w-full')
                .mark('painel-log')
            ):
                self.log = ui.log(max_lines=2000).classes('h-72 w-full').mark('log')
            with ui.row().style(tema.gap('sm')):
                self.botao = (
                    ui.button('Analisar', icon='play_arrow', on_click=self.iniciar)
                    .classes('ca-alvo')
                    .mark('iniciar')
                )
                self.parar = (
                    ui.button('Cancelar análise', icon='stop', on_click=self.cancelar_analise)
                    .props('flat')
                    .classes('ca-alvo')
                    .mark('cancelar-analise')
                )
                self.parar.set_visibility(False)
        ui.timer(0.2, self.atualizar)

    def cancelar_analise(self) -> None:
        """Pede o fim cooperativo; a etapa em curso termina e a pasta temporária é descartada."""
        self.cancelar.set()
        ui.notify(
            'Cancelando… a etapa em curso termina e o que já estava pronto fica.',
            type='info',
            timeout=5000,
            close_button=True,
        )

    async def iniciar(self) -> None:
        if ESTADO.ocupado:
            return
        ESTADO.ocupado = True
        self.cancelar.clear()
        self.botao.disable()
        self.parar.set_visibility(True)
        self.esqueleto.set_visibility(True)
        self.resultado.clear()
        self.barra.value = 0
        self.titulo.text = 'Analisando…'
        handler = HandlerDoPainel(self.andamento)
        logger.addHandler(handler)
        try:
            opcoes = Opcoes(
                ESTADO.contexto(),
                sim=True,
                abrir=False,
                todos=ESTADO.todos,
                forcar=ESTADO.forcar_proxima_analise,
                saida=self.andamento.escrever,
                ao_progresso=self.andamento.ao_progresso,
                ao_etapa=self.andamento.ao_etapa,
                cancelar=self.cancelar,
            )
            codigo = await run.io_bound(analise.analisar, opcoes)
            ESTADO.forcar_proxima_analise = False
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha na análise pela GUI', exc_info=True)
            self._mostrar_falha(erro)
        else:
            if self.cancelar.is_set():
                self._mostrar_cancelado()
            else:
                self._mostrar_fim(codigo)
        finally:
            logger.removeHandler(handler)
            ESTADO.ocupado = False
            self.botao.enable()
            self.parar.set_visibility(False)
            self.esqueleto.set_visibility(False)
            self.atualizar()

    def atualizar(self) -> None:
        for linha in self.andamento.retirar_linhas():
            self.log.push(linha)
        passo = self.andamento.passo
        if not ESTADO.ocupado:
            return
        etapa = self.andamento.etapa
        leiga = ETAPAS_LEIGAS.get(etapa, analise.TEXTO_DA_ETAPA.get(etapa, 'Analisando…'))
        if etapa is Etapa.CONSOLIDANDO:
            self.barra.value = 1
            self.titulo.text = leiga
        elif passo is not None:
            self.barra.value = passo.fracao
            self.titulo.text = f'{leiga} ({passo.indice} de {passo.total}: {passo.concurso})'

    def _mostrar_cancelado(self) -> None:
        self.barra.value = 1
        self.titulo.text = 'Análise cancelada.'
        with self.resultado:
            aviso(
                'A análise parou',
                'O que já tinha terminado ficou gravado. O concurso interrompido fica como estava.',
                tom=Tom.INFO,
            )
            ui.button(
                'Ver relatório agora', icon='insights', on_click=lambda: ui.navigate.to('/resultados')
            ).classes('ca-alvo')

    def _mostrar_fim(self, codigo: int) -> None:
        self.barra.value = 1
        if codigo == 0:
            self.titulo.text = 'Análise concluída.'
            ui.notify(
                'Análise finalizada! O diagnóstico está pronto.',
                type='positive',
                timeout=5000,
                close_button=True,
            )
            with self.resultado:
                ui.button(
                    'Ver relatório agora', icon='insights', on_click=lambda: ui.navigate.to('/resultados')
                ).classes('ca-alvo')
        else:
            self.titulo.text = 'A análise terminou com falhas em algum concurso.'
            with self.resultado:
                aviso(
                    'Algum concurso falhou',
                    'Abra os detalhes técnicos para ver qual concurso falhou e por quê.',
                    tom=Tom.ALERTA,
                )

    def _mostrar_falha(self, erro: Exception) -> None:
        self.titulo.text = 'A análise não rodou.'
        with self.resultado:
            cartao_de_erro(erro).mark('falha')
