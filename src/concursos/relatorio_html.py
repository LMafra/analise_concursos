"""Relatório HTML por candidato: o painel de gestão (`index.html`) e um HTML por relatório markdown, sem
rede. O vocabulário segue `docs/specs/spec-linguagem.md`; o técnico fica no apêndice "Detalhes técnicos".

Implementação em `relatorio_html_secoes` (extraída para manter o MI do módulo público).
"""

from concursos.relatorio_html_secoes import (  # noqa: F401
    _CSS,
    ARQUIVO_CONCURSOS,
    ARQUIVO_INDICE,
    ARQUIVO_RELATORIO_HTML,
    ARQUIVO_SIMULADOS,
    ARQUIVO_TEC,
    ConcursoNoIndice,
    Observacao,
    _no_wsl,
    abrir_no_navegador,
    gerar_relatorio_html,
)

__all__ = [
    'ARQUIVO_CONCURSOS',
    'ARQUIVO_INDICE',
    'ARQUIVO_RELATORIO_HTML',
    'ARQUIVO_SIMULADOS',
    'ARQUIVO_TEC',
    'ConcursoNoIndice',
    'Observacao',
    '_CSS',
    '_no_wsl',
    'abrir_no_navegador',
    'gerar_relatorio_html',
]
