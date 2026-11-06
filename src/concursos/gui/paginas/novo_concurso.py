import logging
import shutil
from pathlib import Path, PureWindowsPath

from nicegui import events, run, ui

from concursos.aplicacao import cadastro
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import ocr_disponivel
from concursos.deteccao import ArquivoDetectado, Papel
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.estado import ESTADO
from concursos.gui.interacao import InteracaoCanceladaError, InteracaoGui
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.progresso import Andamento
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo

logger = logging.getLogger('concursos')

NOME_DO_PAPEL = {
    Papel.EDITAL: 'edital',
    Papel.PROVA: 'caderno de prova',
    Papel.GABARITO: 'gabarito',
    Papel.RESULTADO: 'resultado oficial',
    Papel.FOLHA: 'sua folha de respostas',
    Papel.RESPOSTAS: 'suas respostas digitadas',
    Papel.IGNORADO: 'ignorar',
    Papel.DESCONHECIDO: 'não reconhecido (o app pergunta)',
}
AVISO_SEM_OCR = (
    'O Tesseract não está instalado: PDFs escaneados (sem texto) não são lidos, e o concurso segue em modo '
    'mínimo. A folha de respostas é lida sem ele; se ela não for lida, digite as suas respostas.'
)


def pagina(concurso: str | None = None) -> None:
    if not exigir_projeto():
        return
    TelaDeEnvio(concurso)


class TelaDeEnvio:
    """Soltar os arquivos, conferir o papel que o app detectou para cada um e cadastrar."""

    def __init__(self, concurso: str | None) -> None:
        self.contexto = ESTADO.contexto()
        self.envio: Path | None = None
        self.papeis: dict[Path, Papel] = {}
        self.andamento = Andamento()
        with ui.column().classes('w-full max-w-3xl').style(tema.gap('md')) as self.recipiente:
            ui.label(f'Acrescentar arquivos a {concurso}' if concurso else 'Novo concurso').classes(
                'text-2xl font-bold'
            )
            self.nome = (
                rotulo(
                    ui.input('Nome do concurso', value=concurso or '', placeholder='ex.: tcu_2025'),
                    'nome do concurso',
                )
                .classes('w-full')
                .mark('nome-concurso')
            )
            if concurso:
                self.nome.disable()
            ui.label(
                'Solte aqui o edital, o gabarito, o caderno de prova e as suas respostas (ou a foto/PDF da folha).'
            )
            self.upload = (
                ui.upload(
                    multiple=True,
                    auto_upload=True,
                    label='Soltar arquivos ou clicar para escolher',
                    on_multi_upload=self.receber,
                )
                .props('accept=".pdf,.txt,.csv,.png,.jpg,.jpeg"')
                .classes('w-full')
                .mark('soltar')
            )
            self.tabela = ui.column().classes('w-full').style(tema.gap('xs'))
            self.candidato = (
                rotulo(
                    ui.input(
                        'De quem são as respostas (seu nome)',
                        value=ESTADO.candidato or self.contexto.candidato or '',
                        autocomplete=ESTADO.candidatos(),
                    ),
                    'nome do candidato',
                )
                .classes('w-full')
                .mark('candidato-envio')
            )
            if not ocr_disponivel():
                aviso('Leitura de PDF escaneado indisponível', AVISO_SEM_OCR, tom=Tom.ALERTA).mark(
                    'sem-tesseract'
                )
            with ui.expansion('Mensagens do cadastro', icon='list').classes('w-full'):
                self.mensagens = ui.log(max_lines=500).classes('h-40 w-full').mark('mensagens')
            with ui.row():
                self.botao = ui.button('Cadastrar', icon='check', on_click=self.cadastrar).mark('cadastrar')
                ui.button('Cancelar', on_click=self.cancelar).props('flat')
            self.resultado = ui.column().classes('w-full')
        ui.timer(0.2, self.atualizar)

    def atualizar(self) -> None:
        for linha in self.andamento.retirar_linhas():
            self.mensagens.push(linha)

    async def receber(self, evento: events.MultiUploadEventArguments) -> None:
        if self.envio is None:
            self.envio = cadastro.nova_pasta_de_envio(self.contexto)
        for arquivo in evento.files:
            await arquivo.save(self.envio / Path(PureWindowsPath(arquivo.name).name).name)
        self.upload.reset()
        detectados = await run.io_bound(cadastro.detectar_envio, self.envio)
        self.papeis = {d.caminho: self.papeis.get(d.caminho, d.papel) for d in detectados}
        self.mostrar_tabela(detectados)

    def mostrar_tabela(self, detectados: list[ArquivoDetectado]) -> None:
        self.tabela.clear()
        opcoes = {papel.value: texto for papel, texto in NOME_DO_PAPEL.items()}
        with self.tabela:
            for detectado in detectados:
                caminho = detectado.caminho
                with ui.row().classes('items-center w-full').style(tema.gap('md')):
                    ui.label(caminho.name).classes('font-mono min-w-48')
                    ui.label(f'Detectamos: {NOME_DO_PAPEL[detectado.papel]}. Confirma?').classes('text-sm')
                    rotulo(
                        ui.select(
                            opcoes,
                            value=self.papeis[caminho].value,
                            on_change=lambda e, c=caminho: self.papeis.__setitem__(c, Papel(e.value)),
                        ),
                        f'papel de {caminho.name}',
                    ).classes('min-w-56').mark(f'papel-{caminho.name}')
                    if detectado.banca:
                        ui.badge(detectado.banca)

    async def cadastrar(self) -> None:
        if ESTADO.ocupado:
            return
        if not self.papeis:
            ui.notify('Solte pelo menos o gabarito antes de cadastrar.', type='warning')
            return
        if not (self.nome.value or '').strip():
            ui.notify('Dê um nome ao concurso antes de cadastrar (ex.: tcu_2025).', type='warning')
            return
        ESTADO.ocupado = True
        self.botao.disable()
        self.resultado.clear()
        opcoes = Opcoes(
            self.contexto,
            interacao=InteracaoGui(self.recipiente, self.andamento.escrever),
            saida=self.andamento.escrever,
        )
        try:
            pasta = await run.io_bound(
                cadastro.cadastrar_envio,
                opcoes,
                self.nome.value or '',
                dict(self.papeis),
                (self.candidato.value or '').strip() or None,
            )
        except InteracaoCanceladaError:
            ui.notify('Cadastro cancelado; nada foi gravado.')
            return
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha no cadastro pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            ESTADO.ocupado = False
            self.botao.enable()
            self.atualizar()
        if pasta is None:
            ui.notify('Nada foi gravado.')
            return
        self.descartar_envio()
        self.mostrar_cadastrado(pasta)

    def mostrar_cadastrado(self, pasta: Path) -> None:
        self.tabela.clear()
        with (
            self.resultado,
            aviso(f'Concurso {pasta.name} cadastrado.', tom=Tom.SUCESSO).mark('cadastrado'),
            ui.row().style(tema.gap('sm')),
        ):
            ui.button('Ver concursos', on_click=lambda: ui.navigate.to('/'))
            ui.button(
                'Digitar respostas', on_click=lambda: ui.navigate.to(f'/respostas?concurso={pasta.name}')
            ).props('outline')

    def descartar_envio(self) -> None:
        if self.envio is not None:
            shutil.rmtree(self.envio, ignore_errors=True)
        self.envio = None
        self.papeis = {}

    def cancelar(self) -> None:
        self.descartar_envio()
        ui.navigate.to('/')
