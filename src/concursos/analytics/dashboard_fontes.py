"""KPIs do dashboard inicial por fonte (concursos, TEC, simulados) — só agrega dados já gravados."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from concursos.analytics.painel import Kpis
from concursos.linguagem import percentual, plural
from concursos.pratica.constantes import ARQUIVO_RESPOSTAS, PASTA_PRATICA


@dataclass(frozen=True)
class KpiItem:
    rotulo: str
    valor: str
    destino: str
    detalhe: str = ''


@dataclass(frozen=True)
class SubDashboard:
    id: str
    titulo: str
    kpis: list[KpiItem]
    vazio: str | None = None
    cta: str | None = None


def kpis_concursos_resumo(indicadores: Kpis) -> SubDashboard:
    if indicadores.provas == 0:
        return SubDashboard(
            'concursos',
            'Concursos',
            [],
            vazio='Ainda não há provas analisadas.',
            cta='Analisar uma prova',
        )
    kpis: list[KpiItem] = []
    if indicadores.com_corte:
        kpis.append(
            KpiItem(
                'Acima do corte',
                f'{indicadores.acima} de {indicadores.com_corte}',
                '#como-estou-saindo',
            )
        )
    else:
        kpis.append(
            KpiItem('Provas', plural(indicadores.provas, 'prova'), '#como-estou-saindo')
        )
    if indicadores.melhor is not None:
        kpis.append(
            KpiItem(
                'Melhor desempenho',
                f'{indicadores.melhor.percentual:.0f}% · {indicadores.melhor.rotulo}',
                '#como-estou-saindo',
            )
        )
    kpis.append(
        KpiItem(
            'Tendência',
            f'{indicadores.tendencia.icone} {indicadores.tendencia.rotulo}',
            '#evolucao',
            indicadores.tendencia.frase,
        )
    )
    return SubDashboard('concursos', 'Concursos', kpis[:3])


def kpis_tec(raiz_candidato: Path) -> SubDashboard:
    arquivo = raiz_candidato / PASTA_PRATICA / ARQUIVO_RESPOSTAS
    if not arquivo.is_file():
        return SubDashboard(
            'tec',
            'Prática no TEC',
            [],
            vazio='Ainda não há dados de prática no TEC.',
            cta='Importar do TEC',
        )
    df = pd.read_csv(arquivo, keep_default_na=False)
    if df.empty or 'resultado' not in df.columns:
        return SubDashboard(
            'tec',
            'Prática no TEC',
            [],
            vazio='Ainda não há dados de prática no TEC.',
            cta='Importar do TEC',
        )
    total = len(df)
    acertos = int((df['resultado'] == 'acerto').sum())
    taxa = percentual(100.0 * acertos / total) if total else '—'
    kpis = [
        KpiItem('Taxa geral', f'{taxa} ({acertos} de {total})', 'tec.html', ''),
    ]
    if 'ass' in df.columns:
        erros = df[df['resultado'] == 'erro']
        if not erros.empty:
            contagem = erros.groupby(['mat', 'ass'], dropna=False).size().sort_values(ascending=False)
            top = []
            for (mat, ass), n in contagem.head(3).items():
                top.append(f'{ass} ({mat}): {n}')
            kpis.append(KpiItem('Top assuntos com erro', '; '.join(top), 'tec.html'))
    if 'banca' in df.columns and df['banca'].astype(str).str.strip().any():
        por_banca = []
        for banca, grupo in df.groupby(df['banca'].replace('', '(sem banca)')):
            a = int((grupo['resultado'] == 'acerto').sum())
            por_banca.append(f'{banca}: {percentual(100.0 * a / len(grupo))} (n={len(grupo)})')
        kpis.append(KpiItem('Por banca', '; '.join(por_banca[:5]), 'tec.html'))
    return SubDashboard('tec', 'Prática no TEC', kpis[:3])


def kpis_simulados(n_simulados: int, ultimo_rotulo: str | None = None) -> SubDashboard:
    if n_simulados <= 0:
        return SubDashboard(
            'simulados',
            'Simulados',
            [],
            vazio='Ainda não há simulados importados.',
            cta='Ver simulados',
        )
    kpis = [
        KpiItem('Simulados', plural(n_simulados, 'simulado'), '#simulados'),
    ]
    if ultimo_rotulo:
        kpis.append(KpiItem('Último', ultimo_rotulo, '#simulados'))
    return SubDashboard('simulados', 'Simulados', kpis[:3])


def html_dashboard(subs: list[SubDashboard]) -> str:
    """Fragmento HTML da 1ª dobra; CSS do relatório já carrega tokens."""
    from html import escape

    blocos = []
    for sub in subs:
        if sub.vazio:
            cta = f'<p class="nota">{escape(sub.cta or "")}</p>' if sub.cta else ''
            corpo = f'<p>{escape(sub.vazio)}</p>{cta}'
        else:
            itens = []
            for kpi in sub.kpis:
                dest = escape(kpi.destino)
                detalhe = f'<span class="nota">{escape(kpi.detalhe)}</span>' if kpi.detalhe else ''
                itens.append(
                    f'<a class="kpi" href="{dest}"><strong>{escape(kpi.rotulo)}</strong>'
                    f'<span>{escape(kpi.valor)}</span>{detalhe}</a>'
                )
            corpo = '<div class="kpis">' + ''.join(itens) + '</div>'
        blocos.append(
            f'<section class="sub-dashboard" id="dash-{escape(sub.id)}">'
            f'<h3>{escape(sub.titulo)}</h3>{corpo}</section>'
        )
    return (
        '<section id="dashboard" class="dashboard" aria-label="Resumo por fonte">'
        '<h2>Como você está agora</h2>'
        f'<div class="dashboard-grade">{"".join(blocos)}</div></section>'
    )
