from nicegui import ui

from concursos import onboarding
from concursos.aplicacao import analise
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.status import Situacao

EXPLICACAO_GABARITO = (
    'preliminar: a banca ainda pode mudar respostas; definitivo: o gabarito final, depois dos recursos'
)
COR_DA_SITUACAO = {Situacao.COMPLETO: 'positive', Situacao.INCOMPLETO: 'warning'}


def pagina() -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full gap-4'):
        with ui.row().classes('items-center gap-2'):
            ui.label(f'Projeto: {ESTADO.projeto}').classes('text-sm text-grey-8')
            ui.button('Trocar', on_click=lambda: ui.navigate.to('/projeto')).props('flat dense')
        if onboarding.precisa_de_onboarding(ESTADO.contexto()):
            with ui.card().classes('bg-blue-1 w-full max-w-4xl').mark('fazer-onboarding'):
                ui.label('Primeira vez neste projeto? Responda a algumas perguntas para começar.')
                ui.button('Começar', icon='waving_hand', on_click=lambda: ui.navigate.to('/inicio'))
        seletor_de_candidato()
        lista_de_concursos()
        with ui.row():
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
    with ui.row().classes('items-center gap-4'):
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


def lista_de_concursos() -> None:
    try:
        provas = ESTADO.contexto().provas
        situacoes = analise.situacoes(provas, ESTADO.candidato) if provas.is_dir() else []
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
        situacoes = []
    if not situacoes:
        ui.label('Nenhum concurso ainda. Crie um concurso e solte os arquivos da prova.').mark(
            'sem-concursos'
        )
        return
    with ui.list().props('bordered separator').classes('w-full max-w-4xl'):
        for item in situacoes:
            with ui.item():
                with ui.item_section():
                    ui.item_label(item.nome).classes('font-bold')
                    with ui.row().classes('items-center gap-2'):
                        ui.badge(item.situacao.value, color=COR_DA_SITUACAO.get(item.situacao, 'grey'))
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


def acoes_do_concurso(nome: str) -> None:
    with ui.row().classes('gap-1'):
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
