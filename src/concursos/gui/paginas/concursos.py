import logging
from collections.abc import Callable

from nicegui import ui

from concursos import onboarding
from concursos.analytics.nome_concurso import NomeDoConcurso
from concursos.aplicacao import analise, cadastro, conferencia, nomes
from concursos.aplicacao.opcoes import Opcoes
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.situacao import situacao
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.encontrar import PainelEncontrar, PainelProvasAnteriores
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.status import Situacao

logger = logging.getLogger('concursos')

EXPLICACAO_GABARITO = (
    'preliminar: a banca ainda pode mudar respostas; definitivo: o gabarito final, depois dos recursos'
)
TOM_DA_SITUACAO = {Situacao.COMPLETO: Tom.SUCESSO, Situacao.INCOMPLETO: Tom.ALERTA}


ABAS = {'lista': 'Meus concursos', 'encontrar': 'Encontrar concursos', 'provas': 'Provas anteriores'}


def pagina(aba: str | None = None) -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full').style(tema.gap('md')):
        with ui.row().classes('items-center').style(tema.gap('sm')):
            ui.label(f'Projeto: {ESTADO.projeto}').classes('text-sm ca-texto-suave')
            ui.button('Trocar', on_click=lambda: ui.navigate.to('/projeto')).props('flat dense')
        with ui.tabs().classes('w-full') as abas:
            guias = {chave: ui.tab(titulo).mark(f'aba-{chave}') for chave, titulo in ABAS.items()}
        with ui.tab_panels(abas, value=guias.get(aba or '', guias['lista'])).classes('w-full'):
            with ui.tab_panel(guias['lista']):
                meus_concursos()
            with ui.tab_panel(guias['encontrar']):
                no_lugar(PainelEncontrar)
            with ui.tab_panel(guias['provas']):
                no_lugar(PainelProvasAnteriores)


def no_lugar(construir: Callable[[Callable[[], None]], object]) -> None:
    """Monta o painel numa caixa que ele mesmo refaz (ao ligar ou desligar o PCI): navegar para o mesmo endereço
    não remonta a aba."""
    caixa = ui.column().classes('w-full')

    def montar() -> None:
        caixa.clear()
        with caixa:
            try:
                construir(montar)
            except Exception as erro:  # noqa: BLE001
                logger.debug('falha ao montar o painel %s', construir.__name__, exc_info=True)
                mostrar_erro(erro)

    montar()


def meus_concursos() -> None:
    with ui.column().classes('w-full').style(tema.gap('md')):
        if onboarding.precisa_de_onboarding(ESTADO.contexto()):
            with (
                aviso(
                    'Primeira vez neste projeto?',
                    'Quatro passos e você vê um resultado, com um concurso de exemplo ou a sua prova.',
                    icone='waving_hand',
                )
                .classes('max-w-4xl')
                .mark('fazer-onboarding')
            ):
                ui.button('Começar', icon='arrow_forward', on_click=lambda: ui.navigate.to('/inicio'))
        seletor_de_candidato()
        if not lista_de_concursos():
            return
        with ui.row().style(tema.gap('sm')):
            ui.button('Novo concurso', icon='add', on_click=lambda: ui.navigate.to('/novo')).props(
                'outline'
            ).mark('novo-concurso')
            ui.button('Analisar', icon='play_arrow', on_click=pedir_analise).mark('analisar')


def seletor_de_candidato() -> None:
    candidatos = ESTADO.candidatos()
    if not candidatos:
        return
    escolhido = ESTADO.candidato or ESTADO.contexto().candidato
    if escolhido not in candidatos:
        escolhido = candidatos[0]
    ESTADO.candidato = escolhido
    if len(candidatos) == 1:
        return
    with ui.row().classes('items-center').style(tema.gap('md')):
        rotulo(
            ui.select(
                candidatos,
                label='Candidato',
                value=escolhido,
                on_change=lambda e: setattr(ESTADO, 'candidato', e.value),
            ),
            'candidato',
        ).mark('candidato')
        ui.checkbox(
            'todos (gera o comparativo)',
            value=ESTADO.todos,
            on_change=lambda e: setattr(ESTADO, 'todos', e.value),
        ).mark('todos')


def lista_de_concursos() -> bool:
    """A lista, ou o estado vazio com o caminho para o primeiro concurso; devolve se havia concursos."""
    try:
        provas = ESTADO.contexto().provas
        situacoes = analise.situacoes(provas, ESTADO.candidato) if provas.is_dir() else []
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
        situacoes = []
    if not situacoes:
        estado_vazio(
            'library_add',
            'Nenhum concurso ainda',
            'Crie um concurso e solte os arquivos da prova: edital, caderno, gabarito e a sua folha.',
            acao='Novo concurso',
            ao_clicar=lambda: ui.navigate.to('/novo'),
            icone_da_acao='add',
            marca='sem-concursos',
        )
        return False
    with ui.list().props('bordered separator').classes('w-full max-w-4xl'):
        for item in situacoes:
            nome = nome_mostrado(item)
            with ui.item():
                with ui.item_section():
                    with ui.row().classes('items-center').style(tema.gap('sm')):
                        ui.item_label(nome.titulo if nome else item.nome).classes('font-bold').mark(
                            f'nome-{item.nome}'
                        )
                        if nome and nome.a_confirmar:
                            with situacao('a confirmar', Tom.ALERTA, icone='help').mark(
                                f'a-confirmar-{item.nome}'
                            ):
                                ui.tooltip(f'Nome {nome.origem}. Use "Corrigir nome" se não estiver certo.')
                    if nome and nome.subtitulo:
                        ui.item_label(nome.subtitulo).props('caption')
                    with ui.row().classes('items-center').style(tema.gap('sm')):
                        situacao(item.situacao.value, TOM_DA_SITUACAO.get(item.situacao, Tom.INFO))
                        with ui.label(f'gabarito: {item.gabarito}').classes('text-sm'):
                            ui.tooltip(EXPLICACAO_GABARITO)
                with ui.item_section().props('side'):
                    if item.motivos:
                        with ui.expansion('Resolver').props('dense').classes('max-w-md'):
                            for motivo in item.motivos:
                                ui.label(motivo).classes('text-sm')
                            acoes_do_concurso(item.nome, nome, sem_edital(item))
                    else:
                        acoes_do_concurso(item.nome, nome, sem_edital(item))
    return True


def sem_edital(item) -> bool:
    return item.config is None or item.config.edital is None


def nome_mostrado(item) -> NomeDoConcurso | None:
    try:
        if item.config is None:
            return nomes.nome_sem_cadastro(ESTADO.contexto().provas / item.nome)
        return nomes.nome_no_projeto(ESTADO.contexto(), item.config)
    except Exception:  # noqa: BLE001
        logger.debug('falha ao montar o nome do concurso', exc_info=True)
        return None


def corrigir_nome(concurso: str, atual: str) -> None:
    with ui.dialog() as dialogo, ui.card().classes('w-96'):
        ui.label('Corrigir nome').classes('text-lg font-bold')
        ui.label(
            'O nome que você escrever vale no lugar do que veio do edital. Vazio, volta ao do edital.'
        ).classes('text-sm')
        campo = (
            rotulo(ui.input('Nome do concurso', value=atual), 'nome do concurso')
            .classes('w-full')
            .mark('novo-nome')
        )

        def salvar() -> None:
            try:
                cadastro.corrigir_titulo(Opcoes(ESTADO.contexto()), concurso, campo.value or '')
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            dialogo.close()
            ui.navigate.to('/')

        with ui.row().style(tema.gap('sm')):
            ui.button('Salvar', icon='check', on_click=salvar).mark('salvar-nome')
            ui.button('Cancelar', on_click=dialogo.close).props('flat')
    dialogo.open()


def acoes_do_concurso(nome: str, mostrado: NomeDoConcurso | None = None, falta_edital: bool = False) -> None:
    try:
        pendentes = conferencia.pendencias(ESTADO.contexto(), nome).total
    except Exception:  # noqa: BLE001
        pendentes = 0
    with ui.row().style(tema.gap('xs')):
        ui.button(
            f'Conferir ({pendentes})' if pendentes else 'Conferir',
            icon='fact_check',
            on_click=lambda: ui.navigate.to(f'/conferir?concurso={nome}'),
        ).props('flat dense').mark(f'conferir-{nome}')
        ui.button(
            'Adicionar o edital e a prova' if falta_edital else 'Acrescentar arquivos',
            icon='upload_file',
            on_click=lambda: ui.navigate.to(f'/novo?concurso={nome}'),
        ).props('flat dense').mark(f'acrescentar-{nome}')
        ui.button(
            'Digitar respostas', icon='edit', on_click=lambda: ui.navigate.to(f'/respostas?concurso={nome}')
        ).props('flat dense').mark(f'digitar-{nome}')
        ui.button(
            'Corrigir nome',
            icon='badge',
            on_click=lambda: corrigir_nome(nome, mostrado.titulo if mostrado else nome),
        ).props('flat dense').mark(f'corrigir-nome-{nome}')


def pedir_analise() -> None:
    ESTADO.pedir_analise = True
    ui.navigate.to('/analise')
