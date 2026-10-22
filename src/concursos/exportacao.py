"""Exportação do consolidado por questão de um candidato."""

from enum import StrEnum
from pathlib import Path

from concursos.analytics.consolidado import carregar_consolidado
from concursos.relatorio import tabela_markdown

PASTA_EXPORTACAO = 'export'


class FormatoExportacao(StrEnum):
    CSV = 'csv'
    PARQUET = 'parquet'
    MD = 'md'


def exportar_consolidado(
    raiz_provas: Path, raiz_analises: Path, arquivo_taxonomia: Path, formato: FormatoExportacao
) -> Path:
    """Grava `export/consolidado.<formato>` na pasta do candidato, uma linha por questão."""
    consolidado = carregar_consolidado(raiz_provas, raiz_analises, arquivo_taxonomia)
    destino = raiz_analises / PASTA_EXPORTACAO / f'consolidado.{formato}'
    destino.parent.mkdir(parents=True, exist_ok=True)
    if formato is FormatoExportacao.CSV:
        consolidado.to_csv(destino, index=False)
    elif formato is FormatoExportacao.PARQUET:
        consolidado.to_parquet(destino, index=False)
    else:
        texto = tabela_markdown(consolidado.fillna(''), list(consolidado.columns))
        destino.write_text(texto + '\n', encoding='utf-8')
    return destino
