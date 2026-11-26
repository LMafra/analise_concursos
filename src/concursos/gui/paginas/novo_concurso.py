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
from concursos.gui.componentes.campo import cabecalho_da_pagina, campo
from concursos.gui.componentes.navegacao import voltar
from concursos.gui.componentes.situacao import situacao
from concursos.gui.estado import ESTADO
from concursos.gui.interacao import InteracaoCanceladaError, InteracaoGui
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.progresso import Andamento
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro
from concursos.linguagem import rotulo_do_arquivo

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
SEM_NOME_DETECTADO = (
    'O nome do concurso vem do edital. Sem ele, o nome fica a confirmar, e você pode corrigi-lo depois.'
)
AVISO_SEM_OCR = (
    'Falta o componente que lê PDF escaneado: edital e prova escaneados (sem texto) não são lidos, e o '
    'concurso segue sem o conteúdo do edital. A folha de respostas é lida sem ele; se ela não for lida, digite '
    'as suas respostas.'
)


def pagina(concurso: str | None = None) -> None:
    if not exigir_projeto():
        return
    voltar('Voltar para Minhas Provas', '/')
    TelaDeEnvio(concurso)


class TelaDeEnvio:
    """Soltar os arquivos, conferir o papel que o app detectou para cada um e cadastrar."""

    def __init__(self, concurso: str | None) -> None:
        self.contexto = ESTADO.contexto()
        self.envio: Path | None = None
        self.papeis: dict[Path, Papel] = {}
        self.concurso = concurso
        self.andamento = Andamento()
        with ui.column().classes('w-full max-w-3xl').style(tema.gap('lg')) as self.recipiente:
            cabecalho_da_pagina(
                f'Acrescentar arquivos a {concurso}' if concurso else 'Novo concurso',
                'Junte os arquivos da sua prova. O Gabarito Vivo identifica cada documento automaticamente.',
            )
            with ui.card().classes('w-full').style(tema.gap('md')):
                self.candidato = campo(
                    'De quem são as respostas (seu nome)',
                    ui.input(
                        value=ESTADO.candidato or self.contexto.candidato or '',
                        autocomplete=ESTADO.candidatos(),
                    ),
                    marca='candidato-envio',
                )
                self.upload = (
                    ui.upload(
                        multiple=True,
                        auto_upload=True,
                        label='Solte aqui Edital, Caderno de Questões, Gabarito e Folha de Respostas',
                        on_multi_upload=self.receber,
                    )
                    .props('accept=".pdf,.txt,.csv,.png,.jpg,.jpeg"')
                    .classes('w-full ca-soltar')
                    .mark('soltar')
                )
                ui.button(
                    'Preencher com arquivos de exemplo',
                    on_click=self.preencher_exemplo,
                ).props('outline no-caps').classes('ca-alvo').mark('arquivos-exemplo')
                ui.label('Arquivos identificados').classes('text-lg font-bold')
                self.tabela = ui.column().classes('w-full').style(tema.gap('xs'))
                self.vazio = (
                    ui.card()
                    .classes('w-full ca-metrica ca-tom-info')
                    .style(tema.gap('xs'))
                    .mark('sem-arquivos')
                )
                with self.vazio:
                    ui.label('Nenhum arquivo escolhido ainda.').classes('font-bold')
                    ui.label(
                        'Solte os PDFs da prova acima ou clique em "Preencher com arquivos de exemplo" '
                        'para testar agora.'
                    ).classes('text-sm ca-texto-suave')
                self.detectado = ui.column().classes('w-full').mark('nome-detectado')
                if not ocr_disponivel():
                    aviso('Leitura de PDF escaneado indisponível', AVISO_SEM_OCR, tom=Tom.ALERTA).mark(
                        'sem-tesseract'
                    )
                with ui.expansion('Mensagens do cadastro', icon='list').classes('w-full'):
                    self.mensagens = ui.log(max_lines=500).classes('h-40 w-full').mark('mensagens')
                with ui.row().classes('w-full justify-end').style(tema.gap('sm')):
                    ui.button('Cancelar', on_click=self.cancelar).props('outline no-caps').classes(
                        'ca-alvo'
                    )
                    self.botao = (
                        ui.button('Cadastrar e analisar agora', on_click=self.cadastrar)
                        .props('no-caps')
                        .classes('ca-alvo')
                        .mark('cadastrar')
                    )
            self.resultado = ui.column().classes('w-full')
        ui.timer(0.2, self.atualizar)

    def atualizar(self) -> None:
        for linha in self.andamento.retirar_linhas():
            self.mensagens.push(linha)

    async def preencher_exemplo(self) -> None:
        from concursos.exemplo import arquivos_do_exemplo

        if self.envio is None:
            self.envio = cadastro.nova_pasta_de_envio(self.contexto)
        for nome, conteudo in arquivos_do_exemplo().items():
            (self.envio / nome).write_text(conteudo, encoding='utf-8')
        detectados = await run.io_bound(cadastro.detectar_envio, self.envio)
        self.papeis = {item.caminho: self.papeis.get(item.caminho, item.papel) for item in detectados}
        self.mostrar_tabela(detectados)
        await self.detectar_nome()

    async def receber(self, evento: events.MultiUploadEventArguments) -> None:
        if self.envio is None:
            self.envio = cadastro.nova_pasta_de_envio(self.contexto)
        for arquivo in evento.files:
            await arquivo.save(self.envio / Path(PureWindowsPath(arquivo.name).name).name)
        self.upload.reset()
        detectados = await run.io_bound(cadastro.detectar_envio, self.envio)
        self.papeis = {d.caminho: self.papeis.get(d.caminho, d.papel) for d in detectados}
        self.mostrar_tabela(detectados)
        await self.detectar_nome()

    async def detectar_nome(self) -> None:
        if self.concurso:
            return
        detectado = await run.io_bound(cadastro.nome_detectado, dict(self.papeis))
        self.detectado.clear()
        with self.detectado:
            if detectado:
                situacao(f'Detectamos: {detectado.titulo} ({detectado.origem})', Tom.SUCESSO, icone='badge')
            else:
                situacao(SEM_NOME_DETECTADO, Tom.INFO, icone='badge')

    async def trocar_papel(self, caminho: Path, papel: Papel) -> None:
        self.papeis[caminho] = papel
        await self.detectar_nome()

    def mostrar_tabela(self, detectados: list[ArquivoDetectado]) -> None:
        self.tabela.clear()
        self.vazio.set_visibility(not detectados)
        opcoes = {papel.value: texto for papel, texto in NOME_DO_PAPEL.items()}
        with self.tabela:
            for detectado in detectados:
                caminho = detectado.caminho
                with (
                    ui.row()
                    .classes('items-center w-full flex-wrap')
                    .style(tema.gap('md'))
                    .mark(f'linha-{caminho.name}')
                ):
                    with ui.column().classes('col').style(tema.gap('xs')):
                        with ui.row().classes('items-center').style(tema.gap('sm')):
                            ui.label(rotulo_do_arquivo(caminho.name)).classes('font-bold break-all')
                            if detectado.banca:
                                ui.badge(detectado.banca)
                        ui.label('Identificado automaticamente').classes('text-sm ca-texto-suave')
                    campo(
                        'Papel reconhecido',
                        ui.select(
                            opcoes,
                            value=self.papeis[caminho].value,
                            on_change=lambda e, c=caminho: self.trocar_papel(c, Papel(e.value)),
                        ).classes('w-56'),
                        marca=f'papel-{caminho.name}',
                    )
                    situacao('Reconhecido', Tom.SUCESSO, icone='check')

    async def cadastrar(self) -> None:
        if ESTADO.ocupado:
            return
        if not self.papeis:
            ui.notify('Solte pelo menos o gabarito antes de cadastrar.', type='warning')
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
                self.concurso,
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
        self.vazio.set_visibility(False)
        with (
            self.resultado,
            aviso('Concurso cadastrado.', tom=Tom.SUCESSO).mark('cadastrado'),
            ui.row().style(tema.gap('sm')),
        ):
            def analisar_agora() -> None:
                ESTADO.pedir_analise = True
                ui.navigate.to('/analise')

            ui.button('Analisar agora', on_click=analisar_agora).props('no-caps').classes('ca-alvo')
            ui.button('Ver concursos', on_click=lambda: ui.navigate.to('/')).props('outline no-caps')
            ui.button(
                'Digitar respostas',
                on_click=lambda: ui.navigate.to(f'/respostas?concurso={pasta.name}'),
            ).props('outline no-caps')

    def descartar_envio(self) -> None:
        if self.envio is not None:
            shutil.rmtree(self.envio, ignore_errors=True)
        self.envio = None
        self.papeis = {}

    def cancelar(self) -> None:
        self.descartar_envio()
        ui.navigate.to('/')
