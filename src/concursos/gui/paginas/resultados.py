import logging

from nicegui import run, ui

from concursos.aplicacao import analise, estudo
from concursos.aplicacao.resultados import (
    Resultados,
    abrir_no_navegador,
    relatorios_disponiveis,
    resultados,
)
from concursos.exportacao import FormatoExportacao
from concursos.gui import tema
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.relatorio import mostrar_relatorio, relatorio
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.estudar import endereco_da_pergunta
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro, rotulo

logger = logging.getLogger('concursos')

LINHAS_POR_PAGINA = 15
SEM_RELATORIO = 'Analise as provas para corrigir e gerar o relatório com as suas notas e os tópicos fracos.'
SEM_RECOMENDACOES = (
    'As indicações de leitura aparecem depois da análise, quando há livros em Estudar ou a legislação ligada; '
    'os tópicos fracos estão no relatório.'
)
DESCRICAO_DOS_FORMATOS = {
    FormatoExportacao.CSV: 'Planilha (abre no Excel)',
    FormatoExportacao.PARQUET: 'Para programadores (Parquet)',
    FormatoExportacao.MD: 'Texto',
}


def pagina() -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full').style(tema.gap('md')):
        seletor_do_candidato()
        try:
            achados = resultados(ESTADO.contexto())
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        with ui.tabs().classes('w-full') as abas:
            aba_relatorio = ui.tab('Relatório', icon='insights')
            aba_recomendacoes = ui.tab('Tópicos', icon='menu_book')
        with ui.tab_panels(abas, value=aba_relatorio).classes('w-full'):
            with ui.tab_panel(aba_relatorio):
                painel_do_relatorio(achados)
            with ui.tab_panel(aba_recomendacoes):
                procurar_nos_livros()
                if achados.recomendacoes is None:
                    estado_vazio(
                        'menu_book',
                        'Sem recomendações ainda',
                        SEM_RECOMENDACOES,
                        acao='Ver o relatório',
                        ao_clicar=lambda: abas.set_value(aba_relatorio),
                        marca='sem-recomendacoes',
                    )
                else:
                    ui.markdown(achados.recomendacoes).classes('w-full').mark('recomendacoes')


def seletor_do_candidato() -> None:
    candidatos = ESTADO.candidatos()
    if len(candidatos) <= 1:
        return
    escolhido = ESTADO.candidato or ESTADO.contexto().candidato
    if escolhido not in candidatos:
        escolhido = candidatos[0]
    ESTADO.candidato = escolhido

    def trocar(evento) -> None:
        ESTADO.candidato = evento.value
        ui.navigate.to('/resultados')

    rotulo(ui.select(candidatos, label='Candidato', value=escolhido, on_change=trocar), 'candidato').mark(
        'candidato-resultados'
    )


def painel_do_relatorio(achados: Resultados) -> None:
    if achados.indice is None:
        estado_vazio(
            'insights',
            'Ainda não há relatório',
            SEM_RELATORIO,
            acao='Analisar',
            ao_clicar=analisar,
            icone_da_acao='play_arrow',
            marca='sem-relatorio',
        )
        return
    indice = achados.indice
    saida_export = ui.column().classes('w-full')

    async def exportar(formato: FormatoExportacao) -> None:
        try:
            destino = await run.io_bound(analise.exportar, ESTADO.contexto(), formato)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha na exportação pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        saida_export.clear()
        with saida_export:
            ui.label(f'Exportado em {destino}').mark('exportado')
            with ui.row().style(tema.gap('sm')):
                ui.button('Baixar', icon='download', on_click=lambda: ui.download.file(destino)).props('flat')
                ui.button(
                    'Abrir a pasta', icon='folder_open', on_click=lambda: abrir_no_navegador(destino.parent)
                ).props('flat')

    opcoes = relatorios_disponiveis(ESTADO.contexto())
    escolhido = {'caminho': indice}
    quadro_ref: list = []

    def abrir_escolhido() -> None:
        abrir_no_navegador(escolhido['caminho'])

    with ui.row().classes('items-center flex-wrap').style(tema.gap('sm')):
        if len(opcoes) > 1:
            rotulos = {o.rotulo: o.caminho for o in opcoes}

            def trocar_concurso(evento) -> None:
                caminho = rotulos[evento.value]
                escolhido['caminho'] = caminho
                mostrar_relatorio(quadro_ref[0], caminho, raiz=achados.pasta)

            rotulo(
                ui.select(
                    list(rotulos),
                    label='Concurso analisado',
                    value=opcoes[0].rotulo,
                    on_change=trocar_concurso,
                )
                .props('dense options-dense')
                .classes('min-w-48'),
                'concurso analisado',
            ).mark('seletor-concurso-relatorio')
        ui.button('Abrir no navegador', icon='open_in_new', on_click=abrir_escolhido).mark(
            'abrir-navegador'
        )
        with (
            ui.button(icon='download')
            .props('flat round aria-label="Exportar"')
            .classes('ca-alvo')
            .mark('exportar'),
            ui.menu(),
        ):
            for formato, descricao in DESCRICAO_DOS_FORMATOS.items():
                ui.menu_item(descricao, on_click=lambda f=formato: exportar(f)).mark(
                    f'exportar-{formato.value}'
                )
        ui.button(
            'Simulado e prática',
            icon='quiz',
            on_click=lambda: ui.navigate.to('/estudar?aba=simulado'),
        ).props('flat').mark('ir-estudar-simulado')
    quadro_ref.append(relatorio(indice, raiz=achados.pasta))


def procurar_nos_livros() -> None:
    """Um botão por tópico fraco que abre Estudar > Perguntar com a consulta pronta."""
    linha = ui.row().classes('w-full items-center').style(tema.gap('sm'))

    async def carregar() -> None:
        try:
            sugestoes = await run.io_bound(estudo.sugestoes_de_pergunta, ESTADO.contexto())
        except Exception:  # noqa: BLE001
            logger.debug('sugestões indisponíveis', exc_info=True)
            return
        if not sugestoes:
            return
        with linha:
            ui.label('Procurar nos meus livros:').classes('text-sm')
            for sugestao in sugestoes:
                ui.button(
                    sugestao.pergunta,
                    icon='search',
                    on_click=lambda s=sugestao: ui.navigate.to(endereco_da_pergunta(s.pergunta)),
                ).props('outline dense no-caps').mark('procurar-nos-livros')

    ui.timer(0.1, carregar, once=True)


def analisar() -> None:
    ESTADO.pedir_analise = True
    ui.navigate.to('/analise')
