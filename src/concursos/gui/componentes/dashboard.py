"""Bloco de dashboard (3 fontes) no topo de Minhas Provas."""

from pathlib import Path

from nicegui import ui

from concursos.analytics.dashboard_fontes import (
    KpiItem,
    SubDashboard,
    kpis_concursos_resumo,
    kpis_simulados,
    kpis_tec,
)
from concursos.analytics.painel import Kpis, Tendencia
from concursos.gui import tema
from concursos.gui.estado import ESTADO
from concursos.pratica.constantes import PASTA_PRATICA


def _raiz_candidato() -> Path | None:
    try:
        ctx = ESTADO.contexto()
    except Exception:  # noqa: BLE001
        return None
    candidato = ESTADO.candidato or ctx.candidato
    if candidato:
        raiz = ctx.analises / candidato
        if raiz.is_dir():
            return raiz
    if ctx.analises.is_dir():
        filhos = sorted(p for p in ctx.analises.iterdir() if p.is_dir() and p.name != PASTA_PRATICA)
        return filhos[0] if filhos else ctx.analises
    return None


def _concursos(raiz: Path) -> SubDashboard:
    provas = [
        p
        for p in raiz.glob('*/relatorio.md')
        if p.parent.name not in {PASTA_PRATICA, 'consolidado', 'export'}
    ]
    n = len(provas)
    indicadores = Kpis(
        concursos=n,
        provas=n,
        acima=0,
        abaixo=0,
        no_limite=0,
        com_corte=0,
        melhor=None,
        mais_fraco=None,
        tendencia=Tendencia(
            'indefinida',
            'Ver resultados',
            '→',
            'Abra Resultados para o diagnóstico completo.',
        ),
    )
    sub = kpis_concursos_resumo(indicadores)
    return SubDashboard(
        sub.id,
        sub.titulo,
        [KpiItem(k.rotulo, k.valor, '/resultados', k.detalhe) for k in sub.kpis],
        sub.vazio,
        'Cadastrar primeira prova' if sub.vazio else None,
    )


def renderizar() -> None:
    raiz = _raiz_candidato()
    if raiz is None:
        return
    pratica = raiz / PASTA_PRATICA
    n_sim = len(list(pratica.glob('simulado*.html'))) if pratica.is_dir() else 0
    tec = kpis_tec(raiz)
    sim = kpis_simulados(n_sim)
    subs = [
        _concursos(raiz),
        SubDashboard(
            tec.id,
            tec.titulo,
            [KpiItem(k.rotulo, k.valor, '/estudar?aba=pratica', k.detalhe) for k in tec.kpis],
            tec.vazio,
            'Importar do TEC' if tec.vazio else None,
        ),
        SubDashboard(
            sim.id,
            sim.titulo,
            [KpiItem(k.rotulo, k.valor, '/estudar?aba=simulado', k.detalhe) for k in sim.kpis],
            sim.vazio,
            'Ver simulados' if sim.vazio else None,
        ),
    ]
    ctas = {'concursos': '/novo', 'tec': '/?aba=tec', 'simulados': '/estudar?aba=simulado'}
    with (
        ui.element('div')
        .classes('w-full')
        .style(
            'display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));'
            f'{tema.gap("md")}'
        )
        .mark('dashboard-home')
    ):
        for sub in subs:
            with ui.card().classes('w-full ca-borda').style('box-shadow: none'):
                ui.label(sub.titulo).classes('text-subtitle1 font-bold')
                if sub.vazio:
                    ui.label(sub.vazio).classes('text-sm ca-texto-suave')
                    if sub.cta:
                        ui.button(
                            sub.cta, on_click=lambda d=ctas[sub.id]: ui.navigate.to(d)
                        ).props('flat').classes('ca-alvo')
                else:
                    for kpi in sub.kpis:
                        with (
                            ui.button(on_click=lambda d=kpi.destino: ui.navigate.to(d))
                            .props('flat align=left')
                            .classes('w-full ca-alvo')
                            .style('height:auto;padding:8px')
                        ):
                            ui.label(kpi.rotulo).classes('text-caption ca-texto-suave')
                            ui.label(kpi.valor).classes('text-body1 font-bold')
