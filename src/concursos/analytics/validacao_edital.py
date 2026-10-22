"""Validação edital × prova × gabarito: o que o edital promete contra o que a prova entregou."""

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

import pandas as pd

from concursos.analytics.regras_edital import RegrasEdital
from concursos.concurso_config import ConcursoConfig

ARQUIVO_DISCREPANCIAS = 'discrepancias_edital.csv'
COLUNAS_DISCREPANCIAS = [
    'item',
    'esperado_edital',
    'observado_prova',
    'diferenca',
    'severidade',
    'acao_sugerida',
]


class Severidade(StrEnum):
    INFO = 'info'
    WARN = 'warn'
    ERROR = 'error'


@dataclass(frozen=True)
class Discrepancia:
    item: str
    esperado_edital: str
    observado_prova: str
    diferenca: float | None
    severidade: Severidade
    acao_sugerida: str


def validar_edital(config: ConcursoConfig, regras: RegrasEdital) -> pd.DataFrame:
    """Uma linha por divergência, com severidade e ação sugerida; vazia quando tudo confere."""
    discrepancias = [*_cargo(config, regras)]
    return pd.DataFrame([asdict(d) for d in discrepancias], columns=COLUNAS_DISCREPANCIAS)


def gravar_discrepancias(discrepancias: pd.DataFrame, destino: Path) -> None:
    discrepancias.to_csv(destino / ARQUIVO_DISCREPANCIAS, index=False)


def _cargo(config: ConcursoConfig, regras: RegrasEdital) -> list[Discrepancia]:
    identificacao = regras.identificacao
    if identificacao.cargo_casado or not identificacao.cargos_do_edital:
        return []
    return [
        Discrepancia(
            'cargo',
            '; '.join(identificacao.cargos_do_edital),
            config.cargo or '',
            None,
            Severidade.WARN,
            'Corrija o cargo no concurso.yaml com o nome (ou número) do cargo no edital; '
            'sem casamento, cortes e distribuição são lidos do concurso inteiro',
        )
    ]
