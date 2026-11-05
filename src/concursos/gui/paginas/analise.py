import logging

from nicegui import run, ui

from concursos.aplicacao import analise
from concursos.aplicacao.opcoes import Opcoes
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.progresso import Andamento, HandlerDoPainel
from concursos.gui.textos import linhas_do_erro

logger = logging.getLogger('concursos')


def pagina() -> None:
    if not exigir_projeto():
        return
    painel = PainelDeAnalise()
    if ESTADO.pedir_analise:
        ESTADO.pedir_analise = False
        ui.timer(0.1, painel.iniciar, once=True)


class PainelDeAnalise:
    def __init__(self) -> None:
        self.andamento = Andamento()
        with ui.column().classes('w-full max-w-4xl gap-4'):
            self.titulo = (
                ui.label('Pronto para analisar o que mudou.').classes('text-lg').mark('titulo-analise')
            )
            self.barra = ui.linear_progress(value=0, show_value=False).props(
                'aria-label="andamento da análise"'
            )
            self.resultado = ui.column().classes('w-full')
            with ui.expansion('Log detalhado', icon='list').classes('w-full').mark('painel-log'):
                self.log = ui.log(max_lines=2000).classes('h-72 w-full').mark('log')
            with ui.row():
                self.botao = ui.button('Analisar', icon='play_arrow', on_click=self.iniciar).mark('iniciar')
        ui.timer(0.2, self.atualizar)

    async def iniciar(self) -> None:
        if ESTADO.ocupado:
            return
        ESTADO.ocupado = True
        self.botao.disable()
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
                saida=self.andamento.escrever,
                ao_progresso=self.andamento.ao_progresso,
            )
            codigo = await run.io_bound(analise.analisar, opcoes)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha na análise pela GUI', exc_info=True)
            self._mostrar_falha(*linhas_do_erro(erro))
        else:
            self._mostrar_fim(codigo)
        finally:
            logger.removeHandler(handler)
            ESTADO.ocupado = False
            self.botao.enable()
            self.atualizar()

    def atualizar(self) -> None:
        for linha in self.andamento.retirar_linhas():
            self.log.push(linha)
        passo = self.andamento.passo
        if passo is not None and ESTADO.ocupado:
            self.barra.value = passo.fracao
            self.titulo.text = f'Analisando {passo.concurso} ({passo.indice} de {passo.total})'

    def _mostrar_fim(self, codigo: int) -> None:
        self.barra.value = 1
        if codigo == 0:
            self.titulo.text = 'Análise concluída.'
            with self.resultado:
                ui.button('Ver resultados', icon='insights', on_click=lambda: ui.navigate.to('/resultados'))
        else:
            self.titulo.text = 'A análise terminou com falhas em algum concurso.'
            with self.resultado:
                ui.label('Abra o "Log detalhado" para ver qual concurso falhou e por quê.')

    def _mostrar_falha(self, causa: str, dica: str | None) -> None:
        self.titulo.text = 'A análise não rodou.'
        with self.resultado, ui.card().classes('bg-red-1 w-full').mark('falha'):
            ui.label(causa).classes('font-bold')
            if dica:
                ui.label(dica)
