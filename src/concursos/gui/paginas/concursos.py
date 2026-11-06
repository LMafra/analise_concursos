from nicegui import ui

from concursos import onboarding
from concursos.aplicacao import analise
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.situacao import situacao
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.status import Situacao

EXPLICACAO_GABARITO = (
    'preliminar: a banca ainda pode mudar respostas; definitivo: o gabarito final, depois dos recursos'
)
TOM_DA_SITUACAO = {Situacao.COMPLETO: Tom.SUCESSO, Situacao.INCOMPLETO: Tom.ALERTA}


def pagina() -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full').style(tema.gap('md')):
        with ui.row().classes('items-center').style(tema.gap('sm')):
            ui.label(f'Projeto: {ESTADO.projeto}').classes('text-sm ca-texto-suave')
            ui.button('Trocar', on_click=lambda: ui.navigate.to('/projeto')).props('flat dense')
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
            with ui.item():
                with ui.item_section():
                    ui.item_label(item.nome).classes('font-bold')
                    with ui.row().classes('items-center').style(tema.gap('sm')):
                        situacao(item.situacao.value, TOM_DA_SITUACAO.get(item.situacao, Tom.INFO))
                        with ui.label(f'gabarito: {item.gabarito}').classes('text-sm'):
                            ui.tooltip(EXPLICACAO_GABARITO)
                with ui.item_section().props('side'):
                    if item.motivos:
                        with ui.expansion('Resolver').props('dense').classes('max-w-md'):
                            for motivo in item.motivos:
                                ui.label(motivo).classes('text-sm')
                            acoes_do_concurso(item.nome)
                    else:
                        acoes_do_concurso(item.nome)
    return True


def acoes_do_concurso(nome: str) -> None:
    with ui.row().style(tema.gap('xs')):
        ui.button(
            'Acrescentar arquivos',
            icon='upload_file',
            on_click=lambda: ui.navigate.to(f'/novo?concurso={nome}'),
        ).props('flat dense').mark(f'acrescentar-{nome}')
        ui.button(
            'Digitar respostas', icon='edit', on_click=lambda: ui.navigate.to(f'/respostas?concurso={nome}')
        ).props('flat dense').mark(f'digitar-{nome}')


def pedir_analise() -> None:
    ESTADO.pedir_analise = True
    ui.navigate.to('/analise')
