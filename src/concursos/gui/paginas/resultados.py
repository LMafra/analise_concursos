import logging

import pandas as pd
from nicegui import run, ui

from concursos.aplicacao import analise, estudo
from concursos.aplicacao.resultados import Resultados, abrir_no_navegador, resultados
from concursos.exportacao import FormatoExportacao
from concursos.gui import tema
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.relatorio import relatorio
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
SEM_SIMULADO = (
    'Importe provas anteriores em Concursos > Provas anteriores: a análise junta as questões delas que caem '
    'nos seus tópicos mais fracos. Com a prática do TEC importada, aparece também o simulado com os seus erros.'
)
SEM_PRATICA = (
    'Solte a planilha que você exportou do TEC, ou os arquivos da captura, em Importar do TEC; a análise '
    'seguinte junta a prática ao relatório.'
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
            aba_recomendacoes = ui.tab('Tópicos para estudar', icon='menu_book')
            aba_simulado = ui.tab('Simulado focado', icon='quiz')
            aba_pratica = ui.tab('Prática no TEC', icon='school')
            aba_exportar = ui.tab('Exportar', icon='download')
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
            with ui.tab_panel(aba_simulado):
                painel_do_simulado(achados)
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
    with ui.row().style(tema.gap('sm')):
        ui.button('Abrir no navegador', icon='open_in_new', on_click=lambda: abrir_no_navegador(indice)).mark(
            'abrir-navegador'
        )
    relatorio(indice)


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


def painel_do_simulado(achados: Resultados) -> None:
    if achados.simulado_focado is None and achados.simulado_tec is None:
        estado_vazio(
            'quiz',
            'Sem simulado ainda',
            SEM_SIMULADO,
            acao='Ir para Provas anteriores',
            ao_clicar=lambda: ui.navigate.to('/?aba=provas'),
            marca='sem-simulado',
        )
        return
    if achados.simulado_tec is not None:
        simulado_tec = achados.simulado_tec
        ui.button(
            'Ver simulado com meus erros do TEC',
            icon='quiz',
            on_click=lambda: abrir_no_navegador(simulado_tec),
        ).props('outline').mark('abrir-simulado-tec')
    if achados.simulado_focado is not None:
        ui.markdown(achados.simulado_focado).classes('w-full').mark('simulado-focado-resultados')


def painel_da_pratica(achados: Resultados) -> None:
    if achados.pratica is None:
        estado_vazio(
            'school',
            'Sem prática no TEC ainda',
            SEM_PRATICA,
            acao='Ir para Importar do TEC',
            ao_clicar=lambda: ui.navigate.to('/tec'),
            marca='sem-pratica',
        )
    else:
        ui.markdown(achados.pratica).classes('w-full').mark('pratica')
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
            with ui.row().style(tema.gap('sm')):
                ui.button('Baixar', icon='download', on_click=lambda: ui.download.file(destino)).props('flat')
                ui.button(
                    'Abrir a pasta', icon='folder_open', on_click=lambda: abrir_no_navegador(destino.parent)
                ).props('flat')

    with ui.row().style(tema.gap('sm')):
        for formato, descricao in DESCRICAO_DOS_FORMATOS.items():
            ui.button(descricao, on_click=lambda f=formato: exportar(f)).props('outline').mark(
                f'exportar-{formato.value}'
            )
    saida = ui.column()


def analisar() -> None:
    ESTADO.pedir_analise = True
    ui.navigate.to('/analise')
