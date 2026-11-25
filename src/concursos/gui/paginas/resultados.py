import logging
from pathlib import Path

from nicegui import run, ui

from concursos.aplicacao import analise, estudo
from concursos.aplicacao.resultados import (
    Resultados,
    abrir_no_navegador,
    resultados,
)
from concursos.exportacao import FormatoExportacao
from concursos.gui import tema
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.relatorio import relatorio
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.estudar import endereco_da_pergunta
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro, rotulo

logger = logging.getLogger('concursos')

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


def pagina(aba: str | None = None) -> None:
    if not exigir_projeto():
        return
    from concursos.relatorio_html_secoes import ARQUIVO_CONCURSOS, ARQUIVO_SIMULADOS, ARQUIVO_TEC

    with ui.column().classes('w-full').style(tema.gap('md')):
        seletor_do_candidato()
        try:
            achados = resultados(ESTADO.contexto())
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        mapa = {
            'concursos': ('Concursos', ARQUIVO_CONCURSOS, 'assignment'),
            'tec': ('TEC', ARQUIVO_TEC, 'quiz'),
            'simulados': ('Simulados', ARQUIVO_SIMULADOS, 'sports_esports'),
        }
        inicial = aba if aba in mapa else 'concursos'
        with ui.tabs().classes('w-full') as abas:
            guias = {
                chave: ui.tab(titulo, icon=icone).mark(f'aba-resultado-{chave}')
                for chave, (titulo, _, icone) in mapa.items()
            }
            aba_topicos = ui.tab('Tópicos', icon='menu_book')
            aba_exportar = ui.tab('Exportar', icon='download').mark('exportar')
        valor_inicial = guias[inicial]
        with ui.tab_panels(abas, value=valor_inicial).classes('w-full'):
            for chave, (_, arquivo, _) in mapa.items():
                with ui.tab_panel(guias[chave]):
                    caminho = achados.pasta / arquivo
                    if not caminho.is_file():
                        estado_vazio(
                            'insights',
                            'Ainda não há relatório',
                            SEM_RELATORIO,
                            acao='Analisar',
                            ao_clicar=analisar,
                            icone_da_acao='play_arrow',
                            marca=f'sem-{chave}',
                        )
                    else:
                        painel_html_fonte(achados, caminho, marca=f'relatorio-{chave}')
            with ui.tab_panel(aba_topicos):
                procurar_nos_livros()
                if achados.recomendacoes is None:
                    estado_vazio(
                        'menu_book',
                        'Sem recomendações ainda',
                        SEM_RECOMENDACOES,
                        acao='Ver Concursos',
                        ao_clicar=lambda: abas.set_value(guias['concursos']),
                        marca='sem-recomendacoes',
                    )
                else:
                    ui.markdown(achados.recomendacoes).classes('w-full').mark('recomendacoes')
            with ui.tab_panel(aba_exportar):
                painel_de_exportacao()


def painel_html_fonte(achados: Resultados, caminho: Path, *, marca: str = 'relatorio') -> None:
    with ui.row().classes('items-center flex-wrap').style(tema.gap('sm')):
        ui.button(
            'Abrir no navegador',
            icon='open_in_new',
            on_click=lambda: abrir_no_navegador(caminho),
        ).classes('ca-alvo').mark('abrir-navegador')
        ui.button(
            'Painel inicial',
            icon='dashboard',
            on_click=lambda: ui.navigate.to('/'),
        ).props('flat').classes('ca-alvo')
    relatorio(caminho, raiz=achados.pasta).mark(marca)


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
                    'Abrir a pasta',
                    icon='folder_open',
                    on_click=lambda: abrir_no_navegador(destino.parent),
                ).props('flat')

    with ui.row():
        for formato, descricao in DESCRICAO_DOS_FORMATOS.items():
            ui.button(descricao, on_click=lambda f=formato: exportar(f)).props('outline').mark(
                f'exportar-{formato.value}'
            )
    saida = ui.column()


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
