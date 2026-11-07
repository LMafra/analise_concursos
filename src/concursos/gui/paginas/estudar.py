import logging
import shutil
from collections.abc import Callable
from pathlib import Path, PureWindowsPath
from urllib.parse import quote

from nicegui import events, run, ui

from concursos.aplicacao import cadastro, estudo
from concursos.aplicacao.nomes import opcoes_de_concurso
from concursos.aplicacao.opcoes import Opcoes
from concursos.datas import data_br
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.cartao import cartao
from concursos.gui.componentes.consentimento import consentimento
from concursos.gui.componentes.dialogo import Dialogo
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.situacao import situacao
from concursos.gui.componentes.trecho import trecho
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.livros.fila import Livro
from concursos.livros.validacao import EXTENSOES
from concursos.modelo import EstadoLivro, OndeProcurar

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
TODAS = 'Todas'
OPCOES_DE_BUSCA = {
    OndeProcurar.LIVROS.value: 'Meus livros',
    OndeProcurar.ANALISES.value: 'Minhas análises',
    OndeProcurar.TUDO.value: 'Tudo',
}
SEM_IA = 'Para uma resposta escrita pela IA, ligue a IA em Configurações.'


def tamanho(bytes_: int) -> str:
    if bytes_ >= 1024 * 1024:
        return f'{bytes_ / (1024 * 1024):.1f} MB'.replace('.', ',')
    return f'{max(bytes_ // 1024, 1)} KB'


def assinatura(livros: list[Livro]) -> tuple:
    return tuple((livro.sha, livro.estado, livro.pagina, livro.disciplina) for livro in livros)


def endereco_da_pergunta(pergunta: str) -> str:
    return f'/estudar?aba=perguntar&pergunta={quote(pergunta)}'


def pagina(aba: str | None = None, pergunta: str | None = None) -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full max-w-5xl').style(tema.gap('md')):
        ui.label('Estudar').classes('text-2xl font-bold')
        with ui.tabs().classes('w-full') as abas:
            aba_livros = ui.tab('Meus livros', icon='menu_book').mark('aba-livros')
            aba_perguntar = ui.tab('Perguntar', icon='search').mark('aba-perguntar')
        inicial = aba_perguntar if aba == 'perguntar' or pergunta else aba_livros
        with ui.tab_panels(abas, value=inicial).classes('w-full'):
            with ui.tab_panel(aba_livros):
                MeusLivros()
            with ui.tab_panel(aba_perguntar):
                Perguntar(pergunta or '', ao_adicionar=lambda: abas.set_value(aba_livros))


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
                        opcoes_de_concurso(self.contexto),
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


class Perguntar:
    """A busca nos livros (e nas análises): trechos com arquivo e página e, com a IA consentida, a resposta."""

    def __init__(self, pergunta: str, ao_adicionar: Callable[[], None]) -> None:
        self.contexto = ESTADO.contexto()
        self.ao_adicionar = ao_adicionar
        with ui.column().classes('w-full').style(tema.gap('md')):
            with ui.row().classes('w-full items-center no-wrap').style(tema.gap('sm')):
                self.campo = rotulo(
                    ui.input(placeholder='o que cai sobre licitações?', value=pergunta).classes('flex-grow'),
                    'pergunta',
                ).mark('campo-pergunta')
                self.campo.on('keydown.enter', self.perguntar)
                ui.button('Perguntar', icon='search', on_click=self.perguntar).mark('perguntar')
            with ui.row().classes('w-full items-center').style(tema.gap('md')):
                ui.label('Procurar em:')
                self.onde = (
                    ui.radio(OPCOES_DE_BUSCA, value=OndeProcurar.LIVROS.value)
                    .props('inline')
                    .mark('onde-procurar')
                )
                self.disciplina = rotulo(
                    ui.select(
                        [TODAS, *sorted({livro.disciplina for livro in estudo.listar_livros(self.contexto)})],
                        value=TODAS,
                        label='Disciplina',
                    ).classes('min-w-48'),
                    'disciplina da busca',
                ).mark('filtro-disciplina')
            self.sugestoes = ui.row().classes('w-full items-center').style(tema.gap('sm'))
            self.ia = ui.column().classes('w-full')
            self.resultado = ui.column().classes('w-full').style(tema.gap('sm')).mark('resultado-pergunta')
        self.desenhar_ia()
        ui.timer(0.1, self.carregar_sugestoes, once=True)
        if pergunta:
            ui.timer(0.1, self.perguntar, once=True)

    def desenhar_ia(self) -> None:
        self.ia.clear()
        texto = estudo.texto_ia_livros(self.contexto)
        with self.ia:
            if texto is None:
                ui.label(SEM_IA).classes('text-sm ca-texto-suave').mark('sem-ia')
            elif estudo.ia_nos_livros(self.contexto) is None:
                with ui.expansion('Respostas escritas pela IA (opcional)', icon='smart_toy').classes(
                    'w-full'
                ):
                    consentimento(texto, 'ia-livros', self.ligar_ia)

    def ligar_ia(self) -> None:
        estudo.ligar_ia_nos_livros(self.contexto, True)
        ui.notify('A IA vai responder com base nos seus livros.', type='positive')
        self.desenhar_ia()

    async def carregar_sugestoes(self) -> None:
        try:
            sugestoes = await run.io_bound(estudo.sugestoes_de_pergunta, self.contexto)
        except Exception:  # noqa: BLE001
            logger.debug('sugestões indisponíveis', exc_info=True)
            return
        if not sugestoes:
            return
        with self.sugestoes:
            ui.label('Sugestões:').classes('text-sm')
            for sugestao in sugestoes:
                ui.button(sugestao.rotulo, on_click=lambda s=sugestao: self.usar_sugestao(s.pergunta)).props(
                    'outline dense rounded no-caps'
                ).mark('sugestao')

    async def usar_sugestao(self, pergunta: str) -> None:
        self.campo.value = pergunta
        await self.perguntar()

    async def perguntar(self) -> None:
        pergunta = (self.campo.value or '').strip()
        if not pergunta:
            return
        disciplina = None if self.disciplina.value == TODAS else self.disciplina.value
        self.resultado.clear()
        with self.resultado:
            ui.spinner(size='lg')
            try:
                resposta = await run.io_bound(
                    estudo.perguntar,
                    Opcoes(self.contexto),
                    pergunta,
                    onde=OndeProcurar(self.onde.value),
                    disciplina=disciplina,
                )
            except Exception as erro:  # noqa: BLE001
                logger.debug('falha ao perguntar pela GUI', exc_info=True)
                self.resultado.clear()
                mostrar_erro(erro)
                return
        self.resultado.clear()
        with self.resultado:
            self.mostrar(resposta)

    def mostrar(self, resposta: estudo.Resposta) -> None:
        for texto in resposta.avisos:
            if texto == estudo.TEXTO_NADA:
                with aviso('Nada encontrado', texto, icone='search_off').mark('nada-encontrado'):
                    ui.button('Adicionar livros', icon='upload_file', on_click=self.ao_adicionar).props(
                        'flat'
                    )
            else:
                aviso(texto, tom=Tom.ALERTA).mark('aviso-pergunta')
        if resposta.resposta_ia:
            with cartao(estudo.TITULO_IA, icone='smart_toy').mark('resposta-ia'):
                ui.markdown(resposta.resposta_ia)
                if resposta.livros_citados:
                    ui.label(f'Livros citados: {", ".join(resposta.livros_citados)}').classes('text-sm')
        if resposta.trechos:
            ui.label('Trechos encontrados').classes('text-lg font-bold')
            for achado in resposta.trechos:
                trecho(achado)
