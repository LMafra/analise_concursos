import logging
from pathlib import Path, PureWindowsPath

from nicegui import events, run, ui

from concursos import doctor as diagnostico
from concursos.aplicacao import inicio, projeto
from concursos.aplicacao.cadastro import nova_pasta_de_envio
from concursos.aplicacao.opcoes import Opcoes
from concursos.calibracao import QUESTOES_CALIBRACAO
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro, rotulo

logger = logging.getLogger('concursos')


def pagina() -> None:
    if not exigir_projeto():
        return
    FormularioInicio()


class FormularioInicio:
    """As perguntas do `init`, com as respostas atuais como padrão."""

    def __init__(self) -> None:
        self.contexto = ESTADO.contexto()
        atuais = inicio.respostas_atuais(self.contexto)
        raiz = self.contexto.raiz
        self.folha: Path | None = None
        with ui.column().classes('w-full max-w-2xl gap-3'):
            ui.label('Bem-vindo ao concurso-analise').classes('text-2xl font-bold')
            ui.label(f'Projeto: {raiz}').classes('text-sm text-grey-8')
            self.nome = (
                rotulo(ui.input('Seu nome', value=atuais.nome or ''), 'seu nome')
                .classes('w-full')
                .mark('nome')
            )
            self.provas = (
                rotulo(
                    ui.input('Pasta das provas', value=inicio.pasta_no_formulario(atuais.provas, raiz)),
                    'pasta das provas',
                )
                .classes('w-full')
                .mark('pasta-provas')
            )
            self.analises = (
                rotulo(
                    ui.input('Pasta das análises', value=inicio.pasta_no_formulario(atuais.analises, raiz)),
                    'pasta das análises',
                )
                .classes('w-full')
                .mark('pasta-analises')
            )
            with ui.expansion('Calibrar a leitura da folha (opcional)', icon='tune').classes('w-full'):
                ui.label(
                    f'Envie uma folha de respostas já preenchida e digite as {QUESTOES_CALIBRACAO} primeiras '
                    'respostas dela (use - para branco). O app ajusta a leitura das suas folhas por ela.'
                ).classes('text-sm')
                ui.upload(label='Folha preenchida', auto_upload=True, on_upload=self.receber_folha).props(
                    'accept=".pdf,.png,.jpg,.jpeg"'
                ).classes('w-full')
                self.digitadas = rotulo(
                    ui.input(f'Respostas das {QUESTOES_CALIBRACAO} primeiras questões', placeholder='ABCD-'),
                    'respostas para a calibração',
                ).mark('calibracao')
            ui.label(
                'A leitura de editais por IA começa desligada; ligue em Configurações, se quiser.'
            ).classes('text-sm text-grey-8')
            self.doctor = ui.checkbox('Conferir o ambiente no fim', value=atuais.doctor).mark('doctor')
            self.botao = ui.button('Concluir', icon='check', on_click=self.concluir).mark('concluir')
            self.resultado = ui.column().classes('w-full')

    async def receber_folha(self, evento: events.UploadEventArguments) -> None:
        destino = nova_pasta_de_envio(self.contexto) / Path(PureWindowsPath(evento.file.name).name).name
        await evento.file.save(destino)
        self.folha = destino

    async def concluir(self) -> None:
        self.botao.disable()
        try:
            calibracao = None
            if self.folha is not None and (self.digitadas.value or '').strip():
                calibracao = await run.io_bound(inicio.calibrar_folha, self.folha, self.digitadas.value)
            respostas = inicio.respostas_do_formulario(
                self.contexto,
                self.nome.value or '',
                self.provas.value or '',
                self.analises.value or '',
                self.doctor.value,
                calibracao,
            )
            opcoes = await run.io_bound(inicio.concluir_onboarding, Opcoes(self.contexto), respostas)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha no onboarding pela GUI', exc_info=True)
            mostrar_erro(erro)
            self.botao.enable()
            return
        ESTADO.candidato = opcoes.contexto.candidato
        if not respostas.doctor:
            ui.navigate.to('/')
            return
        itens = await run.io_bound(projeto.diagnosticar, opcoes.contexto)
        with self.resultado:
            ui.label('Configuração gravada.').classes('text-lg').mark('gravado')
            ui.label(diagnostico.formatar(itens)).classes('whitespace-pre-line font-mono text-sm').mark(
                'diagnostico'
            )
            ui.button('Ir para os concursos', on_click=lambda: ui.navigate.to('/'))
