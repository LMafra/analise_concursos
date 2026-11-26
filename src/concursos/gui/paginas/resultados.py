import logging
from pathlib import Path
from urllib.parse import quote

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
from concursos.gui.textos import mostrar_erro

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


def pagina(aba: str | None = None, concurso: str | None = None) -> None:
    if not exigir_projeto():
        return
    from concursos.relatorio_html_secoes import ARQUIVO_CONCURSOS, ARQUIVO_SIMULADOS, ARQUIVO_TEC

    resumo = _carregar_resumo()
    opcoes = _opcoes_do_filtro(resumo)
    escolhido = _concurso_escolhido(opcoes, concurso, resumo)
    abas_ref: list = []
    with ui.column().classes('w-full').style(tema.gap('lg')):
        def filtros() -> None:
            if opcoes or len(ESTADO.candidatos()) > 1:
                with ui.column().classes('ca-filtros').style(_largura_do_filtro(opcoes)):
                    seletor_do_concurso(opcoes, escolhido, abas_ref)
                    seletor_do_candidato()

        from concursos.gui.componentes.campo import cabecalho_da_pagina

        cabecalho_da_pagina(
            'Resultados',
            'Diagnóstico objetivo do seu desempenho e onde focar agora.',
            ao_lado=filtros,
        )
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
        abas_ref.append((abas, {**guias, 'topicos': aba_topicos, 'exportar': aba_exportar}))
        valor_inicial = guias[inicial]
        with ui.tab_panels(abas, value=valor_inicial).classes('w-full'):
            with ui.tab_panel(guias['concursos']):
                caminho = achados.pasta / ARQUIVO_CONCURSOS
                tem_resumo = _resumo_de_concursos(escolhido, resumo)
                if caminho.is_file():
                    painel_html_fonte(achados, caminho, marca='relatorio-concursos')
                elif not tem_resumo:
                    estado_vazio(
                        'insights',
                        'Ainda não há relatório',
                        SEM_RELATORIO,
                        acao='Analisar',
                        ao_clicar=analisar,
                        icone_da_acao='play_arrow',
                        marca='sem-concursos',
                    )
            with ui.tab_panel(guias['tec']):
                painel_tec(achados)
            with ui.tab_panel(guias['simulados']):
                painel_simulados(achados)
            with ui.tab_panel(aba_topicos):
                painel_topicos(escolhido, resumo, achados, abas, guias['concursos'])
            with ui.tab_panel(aba_exportar):
                painel_de_exportacao(escolhido)


def _carregar_resumo():
    from concursos.aplicacao.resultados import ResumoVisual, resumo_visual

    try:
        return resumo_visual(ESTADO.contexto())
    except Exception:  # noqa: BLE001
        logger.debug('resumo de concursos indisponível', exc_info=True)
        return ResumoVisual()


def _opcoes_do_filtro(resumo) -> dict[str, str]:
    """Pasta → nome mostrado. A prova mais recente vem primeiro; o resto segue o cadastro."""
    from concursos.aplicacao.nomes import opcoes_de_concurso, titulo_amigavel_da_pasta

    try:
        opcoes = dict(opcoes_de_concurso(ESTADO.contexto()))
    except Exception:  # noqa: BLE001
        logger.debug('nomes dos concursos indisponíveis', exc_info=True)
        opcoes = {}
    ordenadas: dict[str, str] = {}
    for ponto in sorted(resumo.pontos, key=lambda item: item.ordem, reverse=True):
        ordenadas[ponto.concurso] = opcoes.get(ponto.concurso) or titulo_amigavel_da_pasta(
            ponto.concurso
        )
    for chave, nome in opcoes.items():
        ordenadas.setdefault(chave, nome)
    return ordenadas


def _concurso_escolhido(opcoes: dict[str, str], pedido: str | None, resumo) -> str | None:
    from concursos.gui.componentes.resumo_visual import ultimo

    if pedido in opcoes:
        return pedido
    ponto = ultimo(resumo)
    if ponto is not None and ponto.concurso in opcoes:
        return ponto.concurso
    return next(iter(opcoes), None)


def _largura_do_filtro(opcoes: dict[str, str]) -> str:
    """A caixa acompanha o nome mais longo, com o mínimo do protótipo, e quebra na tela estreita."""
    maior = max((len(nome) for nome in opcoes.values()), default=0)
    pixels = min(576, max(260, round(maior * 8.2) + 56))
    return f'width: {pixels}px; max-width: 100%'


def seletor_do_concurso(opcoes: dict[str, str], escolhido: str | None, abas_ref: list) -> None:
    if not opcoes or escolhido is None:
        return

    def trocar(evento) -> None:
        if not evento.value or evento.value == escolhido:
            return
        aba = 'concursos'
        if abas_ref:
            abas, guias = abas_ref[0]
            aba = next((chave for chave, guia in guias.items() if guia == abas.value), aba)
        ui.navigate.to(f'/resultados?aba={quote(aba)}&concurso={quote(str(evento.value))}')

    from concursos.gui.componentes.campo import campo

    campo(
        'Concurso selecionado',
        ui.select(opcoes, value=escolhido, on_change=trocar).props(
            'popup-content-class=ca-seletor-lista'
        ),
        marca='concurso-resultados',
    )


def _resumo_de_concursos(concurso: str | None = None, resumo=None) -> bool:
    from concursos.aplicacao.resultados import resumo_visual
    from concursos.gui.componentes.resumo_visual import (
        acoes,
        atalhos_de_pratica,
        grafico,
        hero,
        metricas_do_ponto,
        ultimo,
    )

    if resumo is None:
        try:
            resumo = resumo_visual(ESTADO.contexto())
        except Exception as erro:  # noqa: BLE001
            logger.debug('resumo de concursos indisponível', exc_info=True)
            mostrar_erro(erro)
            return False
    ponto = None
    if concurso:
        ponto = next((item for item in resumo.pontos if item.concurso == concurso), None)
    if ponto is None and concurso:
        return False
    if ponto is None:
        ponto = ultimo(resumo)
    if ponto is None:
        return False
    hero(
        ponto,
        rotulo_atalho='Montar simulado dos pontos fracos',
        destino='/estudar?aba=simulado',
    )
    metricas_do_ponto(ponto, resumo.pontos)
    acoes(resumo.fracos)
    grafico(resumo.pontos, atual=ponto.concurso)
    atalhos_de_pratica()
    return True


def painel_html_fonte(achados: Resultados, caminho: Path, *, marca: str = 'relatorio') -> None:
    with ui.row().classes('w-full items-center').style(tema.gap('sm')):
        ui.button(
            'Abrir no navegador',
            icon='open_in_new',
            on_click=lambda: abrir_no_navegador(caminho),
        ).props('outline no-caps').classes('ca-alvo').mark('abrir-navegador')
    with ui.card().classes('w-full'):
        relatorio(caminho, raiz=achados.pasta).mark(marca)


def painel_tec(achados: Resultados) -> None:
    from concursos.analytics.dashboard_fontes import kpis_tec
    from concursos.gui.componentes.dashboard import _metas, _raiz_candidato
    from concursos.relatorio_html_secoes import ARQUIVO_TEC

    raiz = _raiz_candidato()
    tec = kpis_tec(raiz, _metas()) if raiz else None
    with ui.card().classes('w-full').style(tema.gap('md')).mark('painel-tec-resumo'):
        with ui.row().classes('w-full items-center justify-between flex-wrap').style(tema.gap('md')):
            with ui.column().style(tema.gap('xs')):
                ui.label('Seu desempenho recente no TEC').classes('text-lg font-bold')
                if tec and tec.kpis:
                    ui.label(tec.kpis[0].valor).classes('ca-texto-suave')
                else:
                    ui.label(
                        'Traga o relatório do TEC para ver matérias, questões e taxa de acerto.'
                    ).classes('ca-texto-suave')
            ui.button(
                'Atualizar relatório do TEC',
                on_click=lambda: ui.navigate.to('/estudar?aba=pratica'),
            ).props('outline no-caps').classes('ca-alvo')
        if tec and tec.kpis:
            with ui.column().style(tema.gap('sm')):
                for item in tec.kpis:
                    with ui.row().classes('w-full items-center justify-between').style(tema.gap('sm')):
                        ui.label(item.rotulo).classes('font-bold')
                        ui.label(item.valor)
    caminho = achados.pasta / ARQUIVO_TEC
    if caminho.is_file():
        painel_html_fonte(achados, caminho, marca='relatorio-tec')
    elif not (tec and tec.kpis):
        estado_vazio(
            'quiz',
            'Ainda não há prática do TEC',
            'Importe o relatório na aba Prática no TEC em Estudar.',
            acao='Ir para importação',
            ao_clicar=lambda: ui.navigate.to('/estudar?aba=pratica'),
            marca='sem-tec',
        )


def painel_simulados(achados: Resultados) -> None:
    from concursos.gui.componentes.dashboard import _raiz_candidato, _regs_simulados
    from concursos.gui.componentes.situacao import situacao
    from concursos.gui.tema import Tom
    from concursos.relatorio_html_secoes import ARQUIVO_SIMULADOS

    raiz = _raiz_candidato()
    regs = _regs_simulados(raiz) if raiz else []
    with ui.card().classes('w-full').style(tema.gap('md')).mark('painel-simulados-resumo'):
        with ui.row().classes('w-full items-center justify-between flex-wrap').style(tema.gap('md')):
            with ui.column().style(tema.gap('xs')):
                ui.label(f'Simulados realizados ({len(regs)})').classes('text-lg font-bold')
                ui.label(
                    'Simulados curtos ajudam a testar exatamente os tópicos que faltaram na prova.'
                ).classes('ca-texto-suave')
            ui.button(
                'Fazer novo simulado',
                on_click=lambda: ui.navigate.to('/estudar?aba=simulado'),
            ).props('no-caps').classes('ca-alvo')
        if regs:
            with ui.column().classes('w-full').style(tema.gap('sm')):
                for reg in regs:
                    with (
                        ui.card().classes('w-full ca-metrica ca-tom-sucesso'),
                        ui.row().classes('w-full items-center justify-between').style(tema.gap('sm')),
                    ):
                        with ui.column().style(tema.gap('xs')):
                            ui.label(reg.nome).classes('font-bold')
                            ui.label(f'Origem: {reg.origem}').classes('text-sm ca-texto-suave')
                        situacao('Registrado', Tom.SUCESSO, icone='check')
    caminho = achados.pasta / ARQUIVO_SIMULADOS
    if caminho.is_file():
        painel_html_fonte(achados, caminho, marca='relatorio-simulados')
    elif not regs:
        estado_vazio(
            'sports_esports',
            'Ainda não há simulados',
            'Monte um simulado curto em Estudar a partir dos seus pontos fracos.',
            acao='Fazer novo simulado',
            ao_clicar=lambda: ui.navigate.to('/estudar?aba=simulado'),
            marca='sem-simulados',
        )


def painel_topicos(escolhido: str | None, resumo, achados: Resultados, abas, guia_concursos) -> None:
    from concursos.gui.componentes.campo import campo
    from concursos.gui.componentes.situacao import situacao
    from concursos.gui.tema import Tom
    from concursos.texto import abreviar

    fracos = list(resumo.fracos)
    titulo = escolhido or 'suas provas'
    with ui.card().classes('w-full').style(tema.gap('md')).mark('painel-topicos'):
        with ui.row().classes('w-full items-end justify-between flex-wrap').style(tema.gap('md')):
            with ui.column().style(tema.gap('xs')):
                ui.label(f'Todos os tópicos de {titulo}').classes('text-lg font-bold')
                ui.label('Clique em "Treinar" para abrir um simulado direto do assunto.').classes(
                    'text-sm ca-texto-suave'
                )
            filtro = campo(
                'Filtrar matéria ou tópico',
                ui.input(placeholder='Ex.: Administrativo'),
                marca='filtro-topicos',
            )
        lista = ui.column().classes('w-full').style(tema.gap('sm')).mark('lista-topicos')

        def redesenhar() -> None:
            lista.clear()
            termo = (filtro.value or '').casefold()
            linhas = [
                item
                for item in fracos
                if not termo
                or termo in item.topico.casefold()
                or termo in item.disciplina.casefold()
            ]
            with lista:
                if not linhas:
                    ui.label('Nenhum tópico com esse filtro.').classes('ca-texto-suave')
                    return
                for item in linhas:
                    with ui.row().classes('w-full items-center flex-wrap').style(tema.gap('sm')):
                        ui.label(item.disciplina).classes('font-bold').style('min-width: 10rem')
                        ui.label(abreviar(item.topico, 60)).classes('flex-grow')
                        situacao(f'{item.percentual:.0f}% de acerto', Tom.ALERTA)
                        ui.button(
                            'Treinar',
                            on_click=lambda t=item.topico: ui.navigate.to(
                                f'/estudar?aba=simulado&topico={quote(t)}'
                            ),
                        ).props('outline dense no-caps').classes('ca-alvo')

        filtro.on('update:model-value', redesenhar)
        redesenhar()
    procurar_nos_livros()
    if achados.recomendacoes is None:
        estado_vazio(
            'menu_book',
            'Sem recomendações ainda',
            SEM_RECOMENDACOES,
            acao='Ver Concursos',
            ao_clicar=lambda: abas.set_value(guia_concursos),
            marca='sem-recomendacoes',
        )
    else:
        ui.markdown(achados.recomendacoes).classes('w-full').mark('recomendacoes')


def painel_de_exportacao(escolhido: str | None = None) -> None:
    rotulo_prova = escolhido or 'todas as provas'

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
                ui.button('Baixar', icon='download', on_click=lambda: ui.download.file(destino)).props(
                    'flat'
                )
                ui.button(
                    'Abrir a pasta',
                    icon='folder_open',
                    on_click=lambda: abrir_no_navegador(destino.parent),
                ).props('flat')

    with ui.element('div').classes('ca-grade-cartoes'):
        with ui.card().classes('w-full').style(tema.gap('md')):
            ui.label('Salvar resumo em planilha').classes('text-lg font-bold')
            ui.label(
                f'Gera um arquivo simples para abrir no Excel ou LibreOffice com as matérias de '
                f'{rotulo_prova}.'
            ).classes('ca-texto-suave')
            ui.button(
                'Baixar planilha (.csv)',
                on_click=lambda: exportar(FormatoExportacao.CSV),
            ).props('no-caps').classes('ca-alvo').mark('exportar-csv')
        with ui.card().classes('w-full').style(tema.gap('md')):
            ui.label('Salvar plano de revisão em texto').classes('text-lg font-bold')
            ui.label(
                'Arquivo de texto leve com os tópicos prioritários do consolidado.'
            ).classes('ca-texto-suave')
            ui.button(
                'Baixar plano de revisão (.txt)',
                on_click=lambda: exportar(FormatoExportacao.MD),
            ).props('outline no-caps').classes('ca-alvo').mark('exportar-md')
        with ui.expansion('Outros formatos', icon='more_horiz').classes('w-full'):
            ui.button(
                DESCRICAO_DOS_FORMATOS[FormatoExportacao.PARQUET],
                on_click=lambda: exportar(FormatoExportacao.PARQUET),
            ).props('outline no-caps').mark('exportar-parquet')
    saida = ui.column()


def seletor_do_candidato() -> None:
    from concursos.gui.componentes.campo import campo

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

    campo(
        'Candidato',
        ui.select(candidatos, value=escolhido, on_change=trocar),
        marca='candidato-resultados',
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
