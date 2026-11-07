import logging

from nicegui import run, ui

from concursos.aplicacao import analise, conferencia
from concursos.aplicacao.opcoes import Opcoes
from concursos.gui import tema
from concursos.gui.estado import ESTADO
from concursos.gui.progresso import Andamento
from concursos.gui.textos import cartao_de_erro
from concursos.modelo import Etapa

logger = logging.getLogger('concursos')


class Reanalise:
    """Refaz a análise depois de uma conferência, com o andamento na própria tela."""

    def __init__(self) -> None:
        self.andamento = Andamento()
        with ui.column().classes('w-full').style(tema.gap('xs')) as self.raiz:
            self.titulo = ui.label('').props('role=status aria-live=polite').mark('reanalise-titulo')
            self.barra = ui.linear_progress(value=0, show_value=False).props(
                'aria-label="andamento da nova análise"'
            )
            self.resultado = ui.column().classes('w-full')
        self.raiz.set_visibility(False)
        ui.timer(0.3, self.atualizar)

    async def iniciar(self, concurso: str | None = None) -> None:
        if ESTADO.ocupado:
            with self.raiz:
                ui.notify('Uma análise já está rodando; a mudança vale na próxima.', type='warning')
            return
        ESTADO.ocupado = True
        self.raiz.set_visibility(True)
        self.resultado.clear()
        self.barra.value = 0
        self.titulo.text = 'Refazendo a análise com o que você conferiu…'
        try:
            opcoes = Opcoes(
                ESTADO.contexto(),
                saida=self.andamento.escrever,
                ao_progresso=self.andamento.ao_progresso,
                ao_etapa=self.andamento.ao_etapa,
            )
            codigo = await run.io_bound(conferencia.reanalisar_afetados, opcoes, concurso)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha na reanálise pela GUI', exc_info=True)
            self.titulo.text = 'A nova análise não rodou.'
            with self.resultado:
                cartao_de_erro(erro).mark('reanalise-falha')
        else:
            self.barra.value = 1
            if codigo == 0:
                self.titulo.text = 'Análise refeita.'
                with self.resultado:
                    ui.button(
                        'Ver resultados', icon='insights', on_click=lambda: ui.navigate.to('/resultados')
                    ).props('flat').mark('reanalise-resultados')
            else:
                self.titulo.text = 'A análise terminou com falhas em algum concurso.'
        finally:
            ESTADO.ocupado = False

    def atualizar(self) -> None:
        self.andamento.retirar_linhas()
        passo = self.andamento.passo
        if not ESTADO.ocupado or passo is None:
            return
        etapa = self.andamento.etapa
        if etapa is Etapa.CONSOLIDANDO:
            self.barra.value = 1
            self.titulo.text = analise.TEXTO_DA_ETAPA[etapa]
        else:
            self.barra.value = passo.fracao
            self.titulo.text = f'Refazendo {passo.concurso} ({passo.indice} de {passo.total})'
