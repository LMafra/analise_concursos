"""Busca local de concursos e tópicos fracos."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

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
            achados.append(
                ResultadoBusca(
                    'Concurso',
                    pasta.name,
                    f'/resultados?aba=concursos&concurso={quote(pasta.name)}',
                )
            )
    achados.extend(_topicos(contexto, termo, limiar=limiar))
    return achados[:20]


def _topicos(contexto: Contexto, termo: str, *, limiar: float) -> list[ResultadoBusca]:
    """Tópicos fracos do resumo já gravado. Sem o consolidado, a busca segue só com os concursos."""
    try:
        from concursos.aplicacao.resultados import resumo_visual

        fracos = resumo_visual(contexto).fracos
    except Exception:  # noqa: BLE001
        return []
    vistos: set[str] = set()
    achados: list[ResultadoBusca] = []
    for fraco in fracos:
        chave = fraco.topico.casefold()
        if chave in vistos or termo not in chave or fraco.percentual >= limiar * 100:
            continue
        vistos.add(chave)
        achados.append(
            ResultadoBusca(
                'Tópico fraco',
                fraco.topico,
                f'/estudar?aba=simulado&topico={quote(fraco.topico)}',
            )
        )
    return achados
