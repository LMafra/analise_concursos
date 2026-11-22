"""Busca local de concursos e tópicos fracos."""

from __future__ import annotations

from dataclasses import dataclass

from concursos.config.contexto import Contexto
from concursos.status import listar_concursos


@dataclass(frozen=True)
class ResultadoBusca:
    tipo: str
    rotulo: str
    rota: str


def procurar(contexto: Contexto, termo: str, *, limiar: float = 0.6) -> list[ResultadoBusca]:
    """Nome de pasta de concurso e tópico fraco do consolidado do candidato."""
    termo = termo.strip().casefold()
    if not termo:
        return []
    achados: list[ResultadoBusca] = []
    for pasta in listar_concursos(contexto.provas):
        if termo in pasta.name.casefold():
            achados.append(ResultadoBusca('concurso', pasta.name, f'/?destaque={pasta.name}'))
    consolidado = contexto.analises_do_candidato / 'consolidado' / 'desempenho_por_topico.csv'
    if consolidado.exists():
        import pandas as pd

        tabela = pd.read_csv(consolidado, keep_default_na=False)
        if {'topico', 'percentual'}.issubset(tabela.columns):
            for _, linha in tabela.iterrows():
                topico = str(linha['topico'])
                try:
                    percentual = float(linha['percentual'])
                except (TypeError, ValueError):
                    continue
                if percentual < limiar * 100 and termo in topico.casefold():
                    achados.append(ResultadoBusca('topico', topico, f'/resultados?topico={topico}'))
    return achados[:20]
