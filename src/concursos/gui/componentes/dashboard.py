"""Três cartões de resumo de Minhas Provas, na ordem do protótipo."""

from pathlib import Path

from nicegui import ui

from concursos.analytics.dashboard_fontes import (
    MetasDashboard,
    RegistroSimulado,
    kpis_tec,
    metas_do_toml,
    metas_padrao,
)
from concursos.config.contexto import ler_toml
from concursos.gui import tema
from concursos.gui.componentes.resumo_visual import cartao_metrica
from concursos.gui.estado import ESTADO
from concursos.gui.tema import Tom
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


def _regs_simulados(raiz: Path) -> list[RegistroSimulado]:
    regs = []
    pratica = raiz / PASTA_PRATICA
    if pratica.is_dir():
        for html in pratica.glob('simulado*.html'):
            regs.append(RegistroSimulado(html.stem, 'TEC', 0.0, ''))
    return regs


def renderizar() -> None:
    """Nota da última prova, acerto no TEC e simulados: um número por cartão."""
    from concursos.aplicacao.resultados import resumo_visual
    from concursos.gui.componentes.resumo_visual import ultimo

    try:
        ponto = ultimo(resumo_visual(ESTADO.contexto()))
    except Exception:  # noqa: BLE001
        ponto = None
    raiz = _raiz_candidato()
    tec = kpis_tec(raiz, _metas()) if raiz else None
    simulados = len(_regs_simulados(raiz)) if raiz else 0
    if ponto is None:
        nota, legenda_nota = 'Sem nota ainda', 'A última prova aparece aqui'
    else:
        nota = f'Nota {ponto.nota:.1f}%'.replace('.', ',')
        legenda_nota = f'{ponto.concurso} (última prova)'
    if tec is None or not tec.kpis:
        acerto, legenda_tec = 'Sem prática ainda', 'Importe o relatório na aba abaixo'
    else:
        acerto, legenda_tec = tec.kpis[0].valor, 'Questões recentes'
    feitos = 'realizado' if simulados == 1 else 'realizados'
    with (
        ui.element('div')
        .classes('w-full')
        .style(f'display:grid;grid-template-columns:repeat(auto-fit,minmax(14rem,1fr));{tema.gap("md")}')
        .mark('dashboard-home')
    ):
        cartao_metrica('Concursos', nota, legenda_nota, Tom.INFO)
        cartao_metrica('Prática no TEC', acerto, legenda_tec, Tom.ALERTA)
        cartao_metrica('Simulados', f'{simulados} {feitos}', 'Foco nos seus pontos fracos', Tom.SUCESSO)
