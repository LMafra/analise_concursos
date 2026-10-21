"""Apresentação para os notebooks; cada função recebe um DataFrame já calculado."""

from dataclasses import dataclass

import pandas as pd


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


def resumir(tabela: pd.DataFrame, n: int = 10, contar: str | None = None) -> Resumo:
    contagens = tabela[contar].value_counts(sort=False) if contar else None
    return Resumo(len(tabela), tabela.head(n), contagens)
