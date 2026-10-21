"""Apresentação para os notebooks; cada função recebe um DataFrame já calculado."""

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go


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


def resumir(tabela: pd.DataFrame, n: int = 10, contar: str | None = None) -> Resumo:
    contagens = tabela[contar].value_counts(sort=False) if contar else None
    return Resumo(len(tabela), tabela.head(n), contagens)
