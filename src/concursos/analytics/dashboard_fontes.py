"""Dashboard de entrada: ≤3 KPIs por fonte (concursos, TEC, simulados). Só agrega dados já gravados."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from concursos.analytics.painel import FAIXA_NO_LIMITE, Prova, StatusProva
from concursos.linguagem import numero, percentual, plural
from concursos.pratica.constantes import ARQUIVO_RESPOSTAS, PASTA_PRATICA

EMPTY_CONCURSOS = (
    'Cadastre sua primeira prova real para ativar o raio-X de notas de corte e pontos fracos.'
)
EMPTY_TEC = 'Importe seu histórico de respostas do TEC para mapear os assuntos com maior taxa de erro.'
EMPTY_SIMULADOS = (
    'Gere ou registre um simulado para acompanhar sua evolução de treino e ritmo de prova.'
)
CTA_CONCURSOS = 'Cadastrar Primeira Prova'
CTA_TEC = 'Importar Respostas do TEC'
CTA_SIMULADOS = 'Registrar Primeiro Simulado'


@dataclass(frozen=True)
class MetasDashboard:
    tec_alta: float = 0.80
    tec_media: float = 0.70
    simulado_alta: float = 0.75
    simulado_media: float = 0.65
    amostra_minima: int = 10
    banca_alvo: str = ''


@dataclass(frozen=True)
class SeloKpi:
    texto: str
    tom: str  # acima | limite | abaixo | info


@dataclass(frozen=True)
class KpiItem:
    rotulo: str
    valor: str
    destino: str
    detalhe: str = ''
    selo: SeloKpi | None = None


@dataclass(frozen=True)
class SubDashboard:
    id: str
    titulo: str
    kpis: list[KpiItem]
    vazio: str | None = None
    cta: str | None = None
    extras: list[KpiItem] | None = None  # <details>


def metas_padrao() -> MetasDashboard:
    return MetasDashboard()


def metas_do_toml(dados: dict) -> MetasDashboard:
    d = dados.get('dashboard') or {}
    base = metas_padrao()
    return MetasDashboard(
        tec_alta=float(d.get('tec_meta_alta', base.tec_alta)),
        tec_media=float(d.get('tec_meta_media', base.tec_media)),
        simulado_alta=float(d.get('simulado_meta_alta', base.simulado_alta)),
        simulado_media=float(d.get('simulado_meta_media', base.simulado_media)),
        amostra_minima=int(d.get('amostra_minima_assunto', base.amostra_minima)),
        banca_alvo=str(d.get('banca_alvo') or '').strip(),
    )


def _selo_por_taxa(taxa: float, alta: float, media: float, pct_texto: str) -> SeloKpi:
    if taxa >= alta:
        return SeloKpi(f'✓ {pct_texto} — Desempenho alto', 'acima')
    if taxa >= media:
        return SeloKpi(f'! {pct_texto} — Em evolução', 'limite')
    return SeloKpi(f'✗ {pct_texto} — Atenção necessária', 'abaixo')


def _selo_corte(gap: float | None, status: StatusProva) -> SeloKpi | None:
    if gap is None or status in (StatusProva.SEM_CORTE, StatusProva.NAO_CALCULAVEL):
        return SeloKpi('ℹ️ Sem corte calculável', 'info')
    sinal = f'+{numero(gap, 1)}' if gap > 0 else numero(gap, 1)
    if status is StatusProva.ACIMA:
        return SeloKpi(f'✓ {sinal} pts — Acima do corte', 'acima')
    if status is StatusProva.LIMITE:
        return SeloKpi(f'! {sinal} pts — Zona de risco', 'limite')
    return SeloKpi(f'✗ {sinal} pts — Abaixo do corte', 'abaixo')


def _taxa_df(df: pd.DataFrame) -> tuple[float, int, int]:
    respondidas = df[df['resultado'].isin(('acerto', 'erro'))]
    n = len(respondidas)
    if n == 0:
        return 0.0, 0, 0
    acertos = int((respondidas['resultado'] == 'acerto').sum())
    return acertos / n, acertos, n


def kpis_concursos(
    provas: list[Prova],
    *,
    destino_base: str = 'concursos.html',
) -> SubDashboard:
    if not provas:
        return SubDashboard(
            'concursos',
            'Concursos (Provas Reais)',
            [],
            vazio=EMPTY_CONCURSOS,
            cta=CTA_CONCURSOS,
        )
    ordenadas = sorted(
        provas,
        key=lambda p: (p.data or '', p.percentual),
        reverse=True,
    )
    ultima = ordenadas[0]
    selo = _selo_corte(ultima.gap, ultima.status)
    if ultima.gap is None:
        valor_corte = ultima.rotulo
    else:
        sinal = f'+{numero(ultima.gap, 1)}' if ultima.gap > 0 else numero(ultima.gap, 1)
        valor_corte = f'{sinal} pts · {ultima.rotulo}'
    kpis = [
        KpiItem(
            'Distância do corte (última prova)',
            valor_corte,
            f'{destino_base}#ultima-prova',
            selo=selo,
        )
    ]
    # Tendência: média das 3 últimas vs restante
    percents = [p.percentual for p in ordenadas]
    if len(percents) < 3:
        kpis.append(
            KpiItem(
                'Tendência de desempenho',
                'ℹ️ Amostra inicial (3+ provas necessárias)',
                f'{destino_base}#evolucao',
                selo=SeloKpi('ℹ️ Amostra inicial', 'info'),
            )
        )
    else:
        recentes = sum(percents[:3]) / 3
        anteriores = sum(percents[3:]) / len(percents[3:]) if len(percents) > 3 else percents[2]
        delta = recentes - anteriores
        if abs(delta) < 0.5:
            texto = f'→ Estável (±{numero(abs(delta), 1)}%)'
            tom = 'info'
        elif delta > 0:
            texto = f'↗ Em elevação (+{numero(delta, 1)}%)'
            tom = 'acima'
        else:
            texto = f'↘ Em queda ({numero(delta, 1)}%)'
            tom = 'abaixo'
        kpis.append(
            KpiItem(
                'Tendência de desempenho',
                texto,
                f'{destino_base}#evolucao',
                selo=SeloKpi(texto, tom),
            )
        )
    media = sum(p.percentual for p in provas) / len(provas)
    kpis.append(
        KpiItem(
            'Média de acertos em provas',
            percentual(media),
            f'{destino_base}#lista',
        )
    )
    melhor = max(provas, key=lambda p: p.percentual)
    extras = [
        KpiItem('Concursos prestados', plural(len({p.concurso for p in provas}), 'concurso'), destino_base),
        KpiItem('Melhor pontuação', f'{percentual(melhor.percentual)} · {melhor.rotulo}', destino_base),
    ]
    return SubDashboard('concursos', 'Concursos (Provas Reais)', kpis, extras=extras)


def kpis_tec(
    raiz_candidato: Path,
    metas: MetasDashboard | None = None,
    *,
    destino_base: str = 'tec.html',
) -> SubDashboard:
    metas = metas or metas_padrao()
    arquivo = raiz_candidato / PASTA_PRATICA / ARQUIVO_RESPOSTAS
    if not arquivo.is_file():
        return SubDashboard('tec', 'Prática no TEC', [], vazio=EMPTY_TEC, cta=CTA_TEC)
    df = pd.read_csv(arquivo, keep_default_na=False)
    if df.empty or 'resultado' not in df.columns:
        return SubDashboard('tec', 'Prática no TEC', [], vazio=EMPTY_TEC, cta=CTA_TEC)

    taxa, acertos, n = _taxa_df(df)
    pct = percentual(100.0 * taxa)
    kpis = [
        KpiItem(
            'Taxa geral de acertos (TEC)',
            f'{pct} ({plural(n, "questão")})',
            destino_base,
            selo=_selo_por_taxa(taxa, metas.tec_alta, metas.tec_media, pct),
        )
    ]

    # Gargalo: menor taxa com amostra mínima
    gargalo = None
    if {'mat', 'ass'}.issubset(df.columns):
        melhor_ruim = None
        for (mat, ass), g in df.groupby(['mat', 'ass'], dropna=False):
            t, _, nn = _taxa_df(g)
            if nn < metas.amostra_minima:
                continue
            if melhor_ruim is None or t < melhor_ruim[0]:
                melhor_ruim = (t, mat, ass, nn)
        if melhor_ruim:
            t, mat, ass, nn = melhor_ruim
            gargalo = KpiItem(
                'Maior gargalo de acertos',
                f'{mat} > {ass} ({percentual(100.0 * t)} acertos)',
                f'{destino_base}#gargalo',
                selo=SeloKpi('⚠️ Ponto fraco prioritário', 'abaixo'),
            )
    if gargalo:
        kpis.append(gargalo)
    else:
        kpis.append(
            KpiItem(
                'Maior gargalo de acertos',
                f'ℹ️ Precisa de ≥{metas.amostra_minima} questões por assunto',
                destino_base,
                selo=SeloKpi('ℹ️ Amostra insuficiente', 'info'),
            )
        )

    # Banca alvo
    banca = metas.banca_alvo
    if not banca and 'banca' in df.columns:
        freqs = df['banca'].replace('', pd.NA).dropna().value_counts()
        if not freqs.empty:
            banca = str(freqs.index[0])
    if banca and 'banca' in df.columns:
        sub = df[df['banca'].astype(str).str.contains(banca, case=False, na=False)]
        if not sub.empty:
            t, _, nn = _taxa_df(sub)
            kpis.append(
                KpiItem(
                    'Desempenho na banca alvo',
                    f'{percentual(100.0 * t)} em {banca}',
                    f'{destino_base}#banca',
                    selo=SeloKpi('ℹ️ Banca oficial', 'info'),
                )
            )
        else:
            kpis.append(
                KpiItem(
                    'Desempenho na banca alvo',
                    f'ℹ️ Sem questões de {banca}',
                    destino_base,
                    selo=SeloKpi('ℹ️ Banca oficial', 'info'),
                )
            )
    else:
        kpis.append(
            KpiItem(
                'Desempenho na banca alvo',
                'ℹ️ Defina a banca alvo em Configurações',
                destino_base,
                selo=SeloKpi('ℹ️ Banca oficial', 'info'),
            )
        )
    return SubDashboard('tec', 'Prática no TEC', kpis[:3])


@dataclass(frozen=True)
class RegistroSimulado:
    nome: str
    origem: str  # PCI | TEC
    percentual: float
    data: str = ''


def kpis_simulados(
    registros: list[RegistroSimulado],
    metas: MetasDashboard | None = None,
    *,
    destino_base: str = 'simulados.html',
) -> SubDashboard:
    metas = metas or metas_padrao()
    if not registros:
        return SubDashboard(
            'simulados',
            'Simulados (PCI + TEC)',
            [],
            vazio=EMPTY_SIMULADOS,
            cta=CTA_SIMULADOS,
        )
    ordenados = sorted(registros, key=lambda r: (r.data, r.percentual), reverse=True)
    ultimo = ordenados[0]
    taxa = ultimo.percentual / 100.0
    pct = percentual(ultimo.percentual)
    kpis = [
        KpiItem(
            'Resultado do último simulado',
            f'{pct} ({ultimo.origem} — {ultimo.nome})',
            f'{destino_base}#ultimo',
            selo=_selo_por_taxa(taxa, metas.simulado_alta, metas.simulado_media, pct),
        )
    ]
    if len(ordenados) < 2:
        kpis.append(
            KpiItem(
                'Evolução em simulados',
                'ℹ️ Primeiro simulado concluído',
                f'{destino_base}#evolucao',
                selo=SeloKpi('ℹ️ Primeiro simulado', 'info'),
            )
        )
    else:
        delta = ordenados[0].percentual - ordenados[1].percentual
        if abs(delta) < 0.05:
            texto = '→ Estável (±0,0%)'
            tom = 'info'
        elif delta > 0:
            texto = f'↗ +{numero(delta, 1)}% vs. simulado anterior'
            tom = 'acima'
        else:
            texto = f'↘ {numero(delta, 1)}% vs. simulado anterior'
            tom = 'abaixo'
        kpis.append(
            KpiItem(
                'Evolução em simulados',
                texto,
                f'{destino_base}#evolucao',
                selo=SeloKpi(texto, tom),
            )
        )
    kpis.append(
        KpiItem(
            'Gargalo nos simulados',
            'ℹ️ Detalhe por assunto no relatório',
            f'{destino_base}#gargalo',
            selo=SeloKpi('⚠️ Ponto fraco em prova', 'limite'),
        )
    )
    return SubDashboard('simulados', 'Simulados (PCI + TEC)', kpis[:3])


def html_dashboard(subs: list[SubDashboard]) -> str:
    from html import escape

    def _selo_html(selo: SeloKpi | None) -> str:
        if not selo:
            return ''
        cls = {
            'acima': 'selo-acima',
            'limite': 'selo-limite',
            'abaixo': 'selo-abaixo',
            'info': 'selo-neutro',
        }.get(selo.tom, 'selo-neutro')
        return f'<span class="selo {cls}">{escape(selo.texto)}</span>'

    blocos = []
    for sub in subs:
        if sub.vazio:
            corpo = (
                f'<p class="empty-msg">{escape(sub.vazio)}</p>'
                f'<p class="nota">{escape(sub.cta or "")}</p>'
            )
        else:
            itens = []
            for kpi in sub.kpis:
                dest = escape(kpi.destino)
                itens.append(
                    f'<a class="kpi" href="{dest}">'
                    f'<strong>{escape(kpi.rotulo)}</strong>'
                    f'<span class="kpi-valor">{escape(kpi.valor)}</span>'
                    f'{_selo_html(kpi.selo)}'
                    f'</a>'
                )
            corpo = '<div class="kpis">' + ''.join(itens) + '</div>'
            if sub.extras:
                extras = ''.join(
                    f'<li><strong>{escape(e.rotulo)}</strong>: {escape(e.valor)}</li>'
                    for e in sub.extras
                )
                corpo += f'<details class="dash-extras"><summary>Mais dados</summary><ul>{extras}</ul></details>'
        blocos.append(
            f'<section class="sub-dashboard" id="dash-{escape(sub.id)}">'
            f'<h3>{escape(sub.titulo)}</h3>{corpo}</section>'
        )
    return (
        '<section id="dashboard" class="dashboard" aria-label="Panorama de desempenho">'
        '<h1>Painel inicial — <strong>Panorama de desempenho</strong></h1>'
        f'<div class="dashboard-grade">{"".join(blocos)}</div></section>'
    )


# Compat com chamadas antigas dos testes F5
def kpis_concursos_resumo(indicadores) -> SubDashboard:
    """Adaptador: monta Provas mínimas a partir de Kpis legado ou devolve empty."""
    from concursos.analytics.painel import Kpis

    if not isinstance(indicadores, Kpis) or indicadores.provas == 0:
        return SubDashboard(
            'concursos',
            'Concursos (Provas Reais)',
            [],
            vazio=EMPTY_CONCURSOS,
            cta=CTA_CONCURSOS,
        )
    provas: list[Prova] = []
    if indicadores.melhor is not None:
        provas.append(indicadores.melhor)
    else:
        provas.append(Prova(concurso='—', titulo='—', percentual=0.0))
    return kpis_concursos(provas)
