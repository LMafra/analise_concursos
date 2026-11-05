import logging

import pandas as pd
from nicegui import run, ui

from concursos.aplicacao import analise
from concursos.aplicacao.resultados import Resultados, abrir_no_navegador, resultados
from concursos.exportacao import FormatoExportacao
from concursos.gui.componentes.relatorio import relatorio
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro, rotulo

logger = logging.getLogger('concursos')

LINHAS_POR_PAGINA = 15
SEM_RELATORIO = 'Ainda não há relatório. Clique em "Analisar" para corrigir as provas e gerar o relatório.'
SEM_RECOMENDACOES = (
    'Sem recomendações ainda. Elas aparecem depois da análise quando o projeto tem uma biblioteca de '
    'estudo (biblioteca.yaml) ou a legislação ligada; os tópicos fracos estão no relatório.'
)
SEM_PRATICA = (
    'Sem prática no TEC ainda. Instale a captura do TEC (em Integrações), exporte os seus erros e solte o '
    'arquivo em Integrações, Prática no TEC; a análise seguinte junta a prática ao relatório.'
)
DESCRICAO_DOS_FORMATOS = {
    FormatoExportacao.CSV: 'CSV (Excel, planilhas)',
    FormatoExportacao.PARQUET: 'Parquet (pandas, análise de dados)',
    FormatoExportacao.MD: 'Markdown (texto)',
}


def pagina() -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full gap-3'):
        seletor_do_candidato()
        try:
            achados = resultados(ESTADO.contexto())
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        with ui.tabs().classes('w-full') as abas:
            aba_relatorio = ui.tab('Relatório', icon='insights')
            aba_recomendacoes = ui.tab('Recomendações', icon='menu_book')
            aba_pratica = ui.tab('Prática no TEC', icon='school')
            aba_exportar = ui.tab('Exportar', icon='download')
        with ui.tab_panels(abas, value=aba_relatorio).classes('w-full'):
            with ui.tab_panel(aba_relatorio):
                painel_do_relatorio(achados)
            with ui.tab_panel(aba_recomendacoes):
                markdown_ou_explicacao(achados.recomendacoes, SEM_RECOMENDACOES, 'recomendacoes')
            with ui.tab_panel(aba_pratica):
                painel_da_pratica(achados)
            with ui.tab_panel(aba_exportar):
                painel_de_exportacao()


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
        with ui.column().mark('sem-relatorio'):
            ui.label(SEM_RELATORIO)
            ui.button('Analisar', icon='play_arrow', on_click=analisar)
        return
    indice = achados.indice
    with ui.row():
        ui.button('Abrir no navegador', icon='open_in_new', on_click=lambda: abrir_no_navegador(indice)).mark(
            'abrir-navegador'
        )
    relatorio(indice)


def markdown_ou_explicacao(texto: str | None, explicacao: str, marca: str) -> None:
    if texto is None:
        ui.label(explicacao).classes('text-grey-8').mark(f'sem-{marca}')
        return
    ui.markdown(texto).classes('w-full').mark(marca)


def painel_da_pratica(achados: Resultados) -> None:
    markdown_ou_explicacao(achados.pratica, SEM_PRATICA, 'pratica')
    if achados.pratica is None:
        ui.button('Ir para a prática no TEC', on_click=lambda: ui.navigate.to('/integracoes?aba=tec')).props(
            'outline'
        )
    for titulo, caminho in achados.tabelas_pratica.items():
        with ui.expansion(titulo, icon='table_chart').classes('w-full'):
            tabela = pd.read_csv(caminho, keep_default_na=False)
            ui.table.from_pandas(tabela, pagination=LINHAS_POR_PAGINA).classes('w-full')


def painel_de_exportacao() -> None:
    ui.label('O consolidado tem uma linha por questão de todos os concursos analisados.')

    async def exportar(formato: FormatoExportacao) -> None:
        try:
            destino = await run.io_bound(analise.exportar, ESTADO.contexto(), formato)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha na exportação pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        saida.clear()
        with saida:
            ui.label(f'Exportado em {destino}').mark('exportado')
            with ui.row():
                ui.button('Baixar', icon='download', on_click=lambda: ui.download.file(destino)).props('flat')
                ui.button(
                    'Abrir a pasta', icon='folder_open', on_click=lambda: abrir_no_navegador(destino.parent)
                ).props('flat')

    with ui.row():
        for formato, descricao in DESCRICAO_DOS_FORMATOS.items():
            ui.button(descricao, on_click=lambda f=formato: exportar(f)).props('outline').mark(
                f'exportar-{formato.value}'
            )
    saida = ui.column()


def analisar() -> None:
    ESTADO.pedir_analise = True
    ui.navigate.to('/analise')
