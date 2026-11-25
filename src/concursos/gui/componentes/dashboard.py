"""Bloco de dashboard (3 fontes) no topo de Minhas Provas — paridade com index.html."""

from pathlib import Path

from nicegui import ui

from concursos.analytics.dashboard_fontes import (
    CTA_CONCURSOS,
    CTA_SIMULADOS,
    CTA_TEC,
    KpiItem,
    MetasDashboard,
    RegistroSimulado,
    SubDashboard,
    kpis_concursos,
    kpis_simulados,
    kpis_tec,
    metas_do_toml,
    metas_padrao,
)
from concursos.analytics.painel import Prova
from concursos.config.contexto import ler_toml
from concursos.gui import tema
from concursos.gui.estado import ESTADO
from concursos.pratica.constantes import PASTA_PRATICA


def _metas() -> MetasDashboard:
    try:
        cfg = ESTADO.contexto().config_projeto
        if cfg.is_file():
            return metas_do_toml(ler_toml(cfg))
    except Exception:  # noqa: BLE001
        pass
    return metas_padrao()


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


def _provas_leves(raiz: Path) -> list[Prova]:
    provas = []
    for md in raiz.glob('*/relatorio.md'):
        if md.parent.name in {PASTA_PRATICA, 'consolidado', 'export'}:
            continue
        provas.append(Prova(concurso=md.parent.name, titulo=md.parent.name, percentual=0.0))
    return provas


def _regs_simulados(raiz: Path) -> list[RegistroSimulado]:
    regs = []
    pratica = raiz / PASTA_PRATICA
    if pratica.is_dir():
        for html in pratica.glob('simulado*.html'):
            regs.append(RegistroSimulado(html.stem, 'TEC', 0.0, ''))
    return regs


def renderizar() -> None:
    raiz = _raiz_candidato()
    metas = _metas()
    provas = _provas_leves(raiz) if raiz else []
    # Preferir provas do painel se o index já tiver sido gerado — fallback leve
    conc = kpis_concursos(provas, destino_base='/resultados?aba=concursos')
    tec = (
        kpis_tec(raiz, metas, destino_base='/resultados?aba=tec')
        if raiz
        else SubDashboard('tec', 'Prática no TEC', [], vazio='…', cta=CTA_TEC)
    )
    sim = kpis_simulados(
        _regs_simulados(raiz) if raiz else [],
        metas,
        destino_base='/resultados?aba=simulados',
    )
    # Remap CTAs GUI
    ctas = {
        'concursos': ('/novo', CTA_CONCURSOS),
        'tec': ('/?aba=tec', CTA_TEC),
        'simulados': ('/estudar?aba=simulado', CTA_SIMULADOS),
    }
    subs = [
        SubDashboard(
            conc.id,
            conc.titulo,
            [KpiItem(k.rotulo, k.valor, '/resultados?aba=concursos', k.detalhe, k.selo) for k in conc.kpis],
            conc.vazio,
            conc.cta,
            conc.extras,
        ),
        SubDashboard(
            tec.id,
            tec.titulo,
            [KpiItem(k.rotulo, k.valor, '/resultados?aba=tec', k.detalhe, k.selo) for k in tec.kpis],
            tec.vazio,
            tec.cta,
        ),
        SubDashboard(
            sim.id,
            sim.titulo,
            [KpiItem(k.rotulo, k.valor, '/resultados?aba=simulados', k.detalhe, k.selo) for k in sim.kpis],
            sim.vazio,
            sim.cta,
        ),
    ]
    with (
        ui.element('div')
        .classes('w-full')
        .style(
            'display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));'
            f'{tema.gap("md")}'
        )
        .mark('dashboard-home')
    ):
        for sub in subs:
            with ui.card().classes('w-full ca-borda').style('box-shadow: none'):
                ui.label(sub.titulo).classes('text-subtitle1 font-bold')
                if sub.vazio:
                    ui.label(sub.vazio).classes('text-sm ca-texto-suave')
                    rota, rotulo = ctas[sub.id]
                    ui.button(rotulo, on_click=lambda d=rota: ui.navigate.to(d)).props('outline').classes(
                        'ca-alvo'
                    )
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
                            if kpi.selo:
                                ui.label(kpi.selo.texto).classes('text-caption')
                    if sub.extras:
                        with ui.expansion('Mais dados', icon='info').classes('w-full'):
                            for e in sub.extras:
                                ui.label(f'{e.rotulo}: {e.valor}').classes('text-sm')
