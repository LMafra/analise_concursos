import logging

from nicegui import run, ui

from concursos.aplicacao import cadastro
from concursos.aplicacao.opcoes import Opcoes
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.status import listar_concursos

logger = logging.getLogger('concursos')


def pagina(concurso: str | None = None) -> None:
    if not exigir_projeto():
        return
    FormularioDeRespostas(concurso)


class FormularioDeRespostas:
    """As respostas digitadas viram o `respostas.csv` do candidato, sem precisar ler a folha."""

    def __init__(self, concurso: str | None) -> None:
        self.contexto = ESTADO.contexto()
        provas = self.contexto.provas
        nomes = [p.name for p in listar_concursos(provas)] if provas.is_dir() else []
        self.marcadas: dict[int, ui.toggle] = {}
        with ui.column().classes('w-full max-w-4xl gap-4'):
            ui.label('Digitar as suas respostas').classes('text-2xl font-bold')
            ui.label('Marque a alternativa de cada questão; deixe sem marcar a que ficou em branco.').classes(
                'text-sm'
            )
            if not nomes:
                ui.label('Nenhum concurso cadastrado ainda.').mark('sem-concursos')
                return
            self.concurso = rotulo(
                ui.select(
                    nomes,
                    label='Concurso',
                    value=concurso if concurso in nomes else nomes[0],
                    on_change=lambda: self.questoes.refresh(),
                ),
                'concurso',
            ).mark('concurso')
            self.candidato = (
                rotulo(
                    ui.input(
                        'Seu nome',
                        value=ESTADO.candidato or self.contexto.candidato or '',
                        autocomplete=ESTADO.candidatos(),
                    ),
                    'nome do candidato',
                )
                .classes('w-full')
                .mark('candidato-respostas')
            )
            self.questoes()
            self.botao = ui.button('Gravar respostas', icon='save', on_click=self.gravar).mark('gravar')
            self.resultado = ui.column().classes('w-full')

    @ui.refreshable_method
    def questoes(self) -> None:
        self.marcadas = {}
        try:
            folha = cadastro.folha_manual(self.contexto, self.concurso.value)
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        with ui.grid(columns=3).classes('w-full gap-x-6 gap-y-1'):
            for questao in folha.questoes:
                with ui.row().classes('items-center gap-2 no-wrap'):
                    ui.label(f'{questao}').classes('w-8 text-right font-mono')
                    self.marcadas[questao] = rotulo(
                        ui.toggle(folha.alternativas, clearable=True).props('dense'),
                        f'questão {questao}',
                    ).mark(f'q{questao}')

    async def gravar(self) -> None:
        respostas = {questao: marcada.value or '' for questao, marcada in self.marcadas.items()}
        self.botao.disable()
        try:
            destino = await run.io_bound(
                cadastro.gravar_respostas_digitadas,
                Opcoes(self.contexto),
                self.concurso.value,
                (self.candidato.value or '').strip(),
                respostas,
            )
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha ao gravar as respostas digitadas', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            self.botao.enable()
        self.resultado.clear()
        with self.resultado:
            ui.label(f'Respostas gravadas em {destino.relative_to(self.contexto.raiz)}.').mark('gravado')
            ui.button('Analisar', icon='play_arrow', on_click=analisar)


def analisar() -> None:
    ESTADO.pedir_analise = True
    ui.navigate.to('/analise')
