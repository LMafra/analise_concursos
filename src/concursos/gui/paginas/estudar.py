import logging
import shutil
from pathlib import Path, PureWindowsPath

from nicegui import events, run, ui

from concursos.aplicacao import cadastro, estudo
from concursos.aplicacao.opcoes import Opcoes
from concursos.datas import data_br
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.cartao import cartao
from concursos.gui.componentes.dialogo import Dialogo
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.situacao import situacao
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.livros.fila import Livro
from concursos.livros.validacao import EXTENSOES
from concursos.modelo import EstadoLivro

logger = logging.getLogger('concursos')

INTERVALO_TELA = 2.0
TEXTO_DUPLICADO = 'Este livro já está na sua biblioteca.'
TOM_DO_LIVRO = {
    EstadoLivro.NA_FILA: Tom.INFO,
    EstadoLivro.LENDO: Tom.INFO,
    EstadoLivro.LIDO: Tom.INFO,
    EstadoLivro.ENVIANDO: Tom.INFO,
    EstadoLivro.PRONTO: Tom.SUCESSO,
    EstadoLivro.ERRO: Tom.ERRO,
}
ICONE_DO_LIVRO = {
    EstadoLivro.NA_FILA: 'schedule',
    EstadoLivro.LENDO: 'auto_stories',
    EstadoLivro.LIDO: 'search',
    EstadoLivro.ENVIANDO: 'hourglass_top',
}
EM_LEITURA = {EstadoLivro.NA_FILA, EstadoLivro.LENDO}


def tamanho(bytes_: int) -> str:
    if bytes_ >= 1024 * 1024:
        return f'{bytes_ / (1024 * 1024):.1f} MB'.replace('.', ',')
    return f'{max(bytes_ // 1024, 1)} KB'


def assinatura(livros: list[Livro]) -> tuple:
    return tuple((livro.sha, livro.estado, livro.pagina, livro.disciplina) for livro in livros)


def pagina() -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full max-w-5xl').style(tema.gap('md')):
        ui.label('Estudar').classes('text-2xl font-bold')
        with ui.tabs().classes('w-full') as abas:
            aba_livros = ui.tab('Meus livros', icon='menu_book').mark('aba-livros')
        with ui.tab_panels(abas, value=aba_livros).classes('w-full'), ui.tab_panel(aba_livros):
            MeusLivros()


class MeusLivros:
    """Os livros do usuário: a preparação do open-notebook, o envio de arquivos e a lista com a situação."""

    def __init__(self) -> None:
        self.contexto = ESTADO.contexto()
        self.preparando: tuple[str, float] | None = None
        self.vista: tuple | None = None
        with ui.column().classes('w-full').style(tema.gap('md')) as self.raiz:
            self.preparo = ui.column().classes('w-full')
            self.envio()
            self.lista = ui.column().classes('w-full').style(tema.gap('sm'))
        self.desenhar_preparo()
        self.atualizar()
        estudo.iniciar_trabalho(self.contexto)
        ui.timer(INTERVALO_TELA, self.conferir)

    # preparar o open-notebook

    def desenhar_preparo(self) -> None:
        self.preparo.clear()
        situacao_estudo = estudo.situacao_do_estudo(self.contexto)
        with self.preparo:
            if not situacao_estudo.disponivel_no_sistema:
                aviso('Perguntas aos livros indisponíveis', situacao_estudo.mensagem, tom=Tom.ALERTA).mark(
                    'estudo-indisponivel'
                )
            elif self.preparando is not None:
                texto, fracao = self.preparando
                with cartao('Preparando a biblioteca', icone='download').mark('estudo-preparando'):
                    ui.label(texto)
                    ui.linear_progress(value=fracao, show_value=False)
            elif not situacao_estudo.preparado:
                with cartao('Prepare a biblioteca uma vez', icone='download').mark('estudo-preparar'):
                    ui.label(situacao_estudo.mensagem)
                    ui.label('Enquanto isso, você já pode adicionar livros e buscar neles.').classes(
                        'text-sm ca-texto-suave'
                    )
                    ui.button('Preparar agora', icon='download', on_click=self.preparar).mark(
                        'preparar-estudo'
                    )
            elif situacao_estudo.fora_do_ar:
                aviso('A biblioteca não abriu agora', situacao_estudo.mensagem, tom=Tom.ALERTA).mark(
                    'estudo-fora'
                )

    async def preparar(self) -> None:
        self.preparando = ('Começando…', 0.0)
        self.desenhar_preparo()

        def progresso(texto: str, fracao: float) -> None:
            self.preparando = (texto, fracao)

        with self.preparo:
            try:
                await run.io_bound(
                    estudo.preparar_estudo, Opcoes(self.contexto), consentiu=True, progresso=progresso
                )
            except Exception as erro:  # noqa: BLE001
                logger.debug('falha ao preparar o estudo pela GUI', exc_info=True)
                mostrar_erro(erro)
            else:
                ui.notify('Biblioteca pronta. Os livros seguem para as perguntas sozinhos.', type='positive')
                estudo.iniciar_trabalho(self.contexto)
            finally:
                self.preparando = None
                self.desenhar_preparo()

    # enviar livros

    def envio(self) -> None:
        with cartao('Adicionar livros', icone='upload_file'):
            ui.label('PDF, EPUB, Word (DOCX) ou TXT, até 300 MB cada.').classes('text-sm')
            with ui.row().classes('w-full items-end').style(tema.gap('md')):
                self.concursos = rotulo(
                    ui.select(
                        estudo.concursos_do_projeto(self.contexto),
                        multiple=True,
                        label='Concurso (opcional)',
                        value=[],
                    ).classes('min-w-64'),
                    'concursos do livro',
                ).mark('livro-concurso')
                self.disciplina = rotulo(
                    ui.select(
                        estudo.disciplinas_sugeridas(self.contexto),
                        label='Disciplina',
                        value='Geral',
                        with_input=True,
                        new_value_mode='add-unique',
                    ).classes('min-w-64'),
                    'disciplina do livro',
                ).mark('livro-disciplina')
            self.upload = (
                ui.upload(
                    multiple=True,
                    auto_upload=True,
                    label='Soltar os livros aqui ou clicar para escolher',
                    on_multi_upload=self.receber,
                )
                .props(f'accept="{",".join(EXTENSOES)}"')
                .classes('w-full')
                .mark('soltar-livros')
            )

    async def receber(self, evento: events.MultiUploadEventArguments) -> None:
        pasta = cadastro.nova_pasta_de_envio(self.contexto)
        try:
            caminhos = []
            for arquivo in evento.files:
                caminho = pasta / Path(PureWindowsPath(arquivo.name).name).name
                await arquivo.save(caminho)
                caminhos.append(caminho)
            resultados = await run.io_bound(
                estudo.adicionar_livros,
                Opcoes(self.contexto),
                caminhos,
                disciplina=self.disciplina.value or None,
                concursos=list(self.concursos.value or []),
            )
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha ao adicionar livros pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
            self.upload.reset()
        for resultado in resultados:
            if resultado.erro:
                ui.notify(f'{resultado.nome}: {resultado.erro}', type='negative', multi_line=True)
            elif not resultado.novo:
                ui.notify(f'{resultado.nome}: {TEXTO_DUPLICADO}', type='info')
        novos = sum(1 for r in resultados if r.novo)
        if novos:
            ui.notify(f'{novos} livro(s) na fila de leitura.', type='positive')
        self.atualizar()

    # lista

    def conferir(self) -> None:
        if self.preparando is not None:
            self.desenhar_preparo()
        if assinatura(estudo.listar_livros(self.contexto)) != self.vista:
            self.atualizar()

    def atualizar(self) -> None:
        livros = estudo.listar_livros(self.contexto)
        self.vista = assinatura(livros)
        preparado = estudo.situacao_do_estudo(self.contexto).preparado
        self.lista.clear()
        with self.lista:
            if not livros:
                estado_vazio(
                    'menu_book',
                    'Sua biblioteca está vazia',
                    'Adicione um livro e o app lê página por página; dá para buscar nas páginas já lidas.',
                    acao='Adicionar meu primeiro livro',
                    ao_clicar=lambda: self.upload.run_method('pickFiles'),
                    icone_da_acao='upload_file',
                    marca='biblioteca-vazia',
                )
                return
            lendo = [livro for livro in livros if livro.estado in EM_LEITURA]
            if lendo:
                with cartao('Preparando', icone='auto_stories').mark('livros-preparando'):
                    for livro in lendo:
                        texto = estudo.situacao_do_livro(livro, preparado)
                        if livro.paginas:
                            texto += ' (já dá para buscar nas lidas)'
                        ui.label(f'{livro.nome}: {texto}').classes('text-sm')
                        ui.linear_progress(
                            value=livro.pagina / livro.paginas if livro.paginas else 0, show_value=False
                        )
            for livro in livros:
                self.linha(livro, preparado)

    def linha(self, livro: Livro, preparado: bool) -> None:
        with (
            ui.card()
            .classes('w-full ca-borda')
            .style(f'{tema.gap("xs")}; box-shadow: none')
            .mark(f'livro-{livro.sha[:12]}')
        ):
            with ui.row().classes('w-full items-center justify-between no-wrap').style(tema.gap('sm')):
                ui.label(livro.nome).classes('font-bold')
                ui.button('Remover', icon='delete', on_click=lambda: self.confirmar_remocao(livro)).props(
                    'flat dense'
                ).mark(f'remover-{livro.sha[:12]}')
            with ui.row().classes('w-full items-center').style(tema.gap('md')):
                ui.label(tamanho(livro.tamanho)).classes('text-sm ca-texto-suave')
                ui.label(f'Adicionado em {data_br(livro.adicionado_em)}').classes('text-sm ca-texto-suave')
                rotulo(
                    ui.select(
                        sorted({*estudo.disciplinas_sugeridas(self.contexto), livro.disciplina}),
                        value=livro.disciplina,
                        with_input=True,
                        new_value_mode='add-unique',
                        on_change=lambda e: self.mudar_disciplina(livro, e.value),
                    )
                    .props('dense')
                    .classes('min-w-48'),
                    f'disciplina de {livro.nome}',
                ).mark(f'disciplina-{livro.sha[:12]}')
                situacao(
                    estudo.situacao_do_livro(livro, preparado),
                    TOM_DO_LIVRO[livro.estado],
                    icone=ICONE_DO_LIVRO.get(livro.estado),
                ).mark(f'situacao-{livro.sha[:12]}')

    async def mudar_disciplina(self, livro: Livro, disciplina: str | None) -> None:
        if not disciplina or disciplina == livro.disciplina:
            return
        with self.raiz:
            try:
                await run.io_bound(estudo.mudar_disciplina, self.contexto, livro.sha, disciplina)
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
            self.atualizar()

    def confirmar_remocao(self, livro: Livro) -> None:
        with self.raiz, Dialogo(f'Remover "{livro.nome}"?', marca='confirmar-remocao') as dialogo:
            with dialogo.corpo:
                ui.label(
                    'O livro sai da biblioteca e das perguntas. O arquivo original continua onde estava.'
                )
            with dialogo.acoes:
                ui.button('Cancelar', on_click=dialogo.close).props('flat')
                ui.button('Remover', icon='delete', on_click=lambda: self.remover(livro, dialogo)).mark(
                    'confirmar-remover'
                )
        dialogo.open()

    async def remover(self, livro: Livro, dialogo: Dialogo) -> None:
        dialogo.close()
        with self.raiz:
            try:
                await run.io_bound(estudo.remover_livro, self.contexto, livro.sha)
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
            else:
                ui.notify(f'{livro.nome} saiu da biblioteca.')
            self.atualizar()
