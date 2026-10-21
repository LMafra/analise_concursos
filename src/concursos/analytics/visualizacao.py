"""Apresentação para os notebooks; cada função recebe um DataFrame já calculado."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative
from plotly.subplots import make_subplots

OPACIDADE_AMOSTRA_INSUFICIENTE = 0.35
_METRICAS_DA_LINHA = (('percentual', 'percentual'), ('zscore', 'z-score'))
_COLUNAS_DO_HOVER = ['concurso', 'banca', 'n']


@dataclass(frozen=True)
class Resumo:
    """Tabela longa resumida para uma célula: o total, as primeiras linhas e, opcionalmente, contagens."""

    total: int
    primeiras: pd.DataFrame
    contagens: pd.Series | None = None

    def _repr_html_(self) -> str:
        partes = [f'<p>{self.total} linhas; mostrando {len(self.primeiras)}.</p>', self.primeiras.to_html()]
        if self.contagens is not None:
            partes.append(self.contagens.to_frame('n').to_html())
        return '\n'.join(partes)


@dataclass(frozen=True)
class Aviso:
    """Texto em markdown no topo de uma célula do notebook."""

    texto: str

    def _repr_markdown_(self) -> str:
        return self.texto


def aviso_modelos(modelos: list[str]) -> Aviso:
    """O aviso de `modelos_distintos`: comparar níveis entre modelos de correção distintos pede cautela."""
    if len(modelos) > 1:
        return Aviso(
            f'> **⚠ modelos de correção distintos** ({", ".join(modelos)}): compare níveis pelo ajustado ao '
            'acaso ou pelo z-score, nunca pelo bruto ou pelo corrigido.'
        )
    return Aviso(f'Um só modelo de correção na base ({", ".join(modelos)}).')


def painel_correcao(comparacao: pd.DataFrame) -> go.Figure:
    """Barras agrupadas de bruto, corrigido e ajustado por concurso (e variante), a partir da tabela de
    `comparar_bruto_vs_corrigido`, com modelo, fator e n no hover."""
    rotulos = [
        f'{concurso} ({variante})' if pd.notna(variante) else concurso
        for concurso, variante in zip(comparacao['concurso'], comparacao['variante'], strict=True)
    ]
    detalhes = comparacao[['modelo_correcao', 'fator_penalidade', 'n']].to_numpy()
    figura = go.Figure()
    for versao, nome in (('bruta', 'bruto'), ('corrigida', 'corrigido'), ('ajustada', 'ajustado')):
        figura.add_bar(
            name=nome,
            x=rotulos,
            y=comparacao[f'percentual_{versao}'],
            customdata=detalhes,
            hovertemplate=(
                f'%{{x}}<br>{nome}: %{{y:.1f}}%<br>'
                'modelo %{customdata[0]}, fator %{customdata[1]:g}<br>n = %{customdata[2]}<extra></extra>'
            ),
        )
    figura.update_layout(
        barmode='group',
        title='Percentual por concurso em cada versão da correção',
        yaxis_title='percentual (sem anuladas)',
        legend_title='versão',
    )
    return figura


def linha_evolucao(zscores: pd.DataFrame, estrato: str | None = None) -> go.Figure:
    """Percentual e z-score de cada disciplina ao longo da ordem, a partir de `zscore_por_disciplina`.

    Pontos com amostra insuficiente ficam soltos e transparentes, fora da linha contínua. Sem estrato, há
    uma série por disciplina com a banca como cor dos pontos; com `estrato='banca'`, uma linha por banca.
    Um menu filtra a disciplina, e o tamanho do ponto cresce com o n.
    """
    datadas = zscores[zscores['ordem'].notna()].sort_values('ordem').assign(rotulo=_rotulo_disciplina)
    cores = _cores_por_banca(datadas['banca'])
    figura = make_subplots(
        rows=2, cols=1, shared_xaxes=True, subplot_titles=[t for _, t in _METRICAS_DA_LINHA]
    )
    rotulos = sorted(datadas['rotulo'].unique())
    for rotulo in rotulos:
        disciplina = datadas[datadas['rotulo'] == rotulo]
        series = disciplina.groupby('banca') if estrato else [(rotulo, disciplina)]
        for nome, serie in series:
            for linha, (coluna, _) in enumerate(_METRICAS_DA_LINHA, start=1):
                for insuficiente, pontos in serie.groupby('amostra_insuficiente'):
                    figura.add_scatter(
                        **_pontos_da_linha(
                            pontos, coluna, cores, insuficiente, cor_da_linha=cores[nome] if estrato else None
                        ),
                        name=nome,
                        meta=rotulo,
                        legendgroup=nome,
                        showlegend=bool(estrato) and linha == 1 and not insuficiente,
                        visible=rotulo == rotulos[0],
                        row=linha,
                        col=1,
                    )
    figura.update_layout(
        title='Evolução por disciplina',
        updatemenus=[
            {
                'buttons': [
                    {
                        'label': rotulo,
                        'method': 'update',
                        'args': [{'visible': [t.meta == rotulo for t in figura.data]}],
                    }
                    for rotulo in rotulos
                ],
                'x': 1.0,
                'y': 1.15,
            }
        ],
    )
    figura.update_xaxes(title_text='ordem cronológica', row=2, col=1)
    return figura


def box_por_disciplina(zscores: pd.DataFrame, coluna: str = 'zscore') -> go.Figure:
    """Distribuição de cada disciplina entre concursos, com cada concurso como ponto sobreposto."""
    tabela = zscores.assign(rotulo=_rotulo_disciplina)
    figura = go.Figure()
    for rotulo, disciplina in tabela.groupby('rotulo', sort=True):
        figura.add_box(
            y=disciplina[coluna],
            name=rotulo,
            boxpoints='all',
            jitter=0.4,
            pointpos=0,
            customdata=disciplina[_COLUNAS_DO_HOVER].to_numpy(),
            hovertemplate=_hover('%{x}') + '<extra></extra>',
        )
    figura.update_layout(title=f'Distribuição por disciplina entre concursos ({coluna})', showlegend=False)
    return figura


def _pontos_da_linha(
    pontos: pd.DataFrame, coluna: str, cores: dict[str, str], insuficiente: bool, cor_da_linha: str | None
) -> dict:
    marcador = {
        'size': 6 + 2 * np.sqrt(pontos['n'].to_numpy()),
        'color': [cores[banca] for banca in pontos['banca']],
        'opacity': OPACIDADE_AMOSTRA_INSUFICIENTE if insuficiente else 1.0,
    }
    return {
        'x': pontos['ordem'].astype(int),
        'y': pontos[coluna],
        'mode': 'markers' if insuficiente else 'lines+markers',
        'marker': marcador,
        'line': {'color': cor_da_linha or 'gray'},
        'customdata': pontos[_COLUNAS_DO_HOVER].to_numpy(),
        'hovertemplate': _hover('ordem %{x}') + '<extra>%{meta}</extra>',
    }


def _hover(eixo_x: str) -> str:
    """Concurso, banca e n vêm de `customdata`, na ordem de _COLUNAS_DO_HOVER."""
    return f'%{{customdata[0]}} (%{{customdata[1]}})<br>{eixo_x}: %{{y:.2f}}<br>n = %{{customdata[2]}}'


def _rotulo_disciplina(tabela: pd.DataFrame) -> pd.Series:
    return tabela['disciplina'] + ' (' + tabela['bloco'] + ')'


def _cores_por_banca(bancas: pd.Series) -> dict[str, str]:
    return {
        banca: qualitative.Plotly[i % len(qualitative.Plotly)]
        for i, banca in enumerate(sorted(bancas.unique()))
    }


def resumir(tabela: pd.DataFrame, n: int = 10, contar: str | None = None) -> Resumo:
    contagens = tabela[contar].value_counts(sort=False) if contar else None
    return Resumo(len(tabela), tabela.head(n), contagens)
