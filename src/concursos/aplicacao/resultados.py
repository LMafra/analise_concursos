from dataclasses import dataclass
from pathlib import Path

from concursos import relatorio_html
from concursos.aplicacao.projeto import pasta_do_candidato
from concursos.biblioteca import ARQUIVO_RECOMENDACOES
from concursos.config.contexto import Contexto
from concursos.consolidado import PASTA_CONSOLIDADO
from concursos.pratica_tec import (
    ARQUIVO_CADERNOS,
    ARQUIVO_DESEMPENHO,
    ARQUIVO_ERROS,
    ARQUIVO_RESUMO,
    PASTA_PRATICA,
)

TABELAS_DA_PRATICA = {
    ARQUIVO_DESEMPENHO: 'Desempenho por disciplina',
    ARQUIVO_ERROS: 'Erros',
    ARQUIVO_CADERNOS: 'Cadernos',
}


@dataclass(frozen=True)
class Resultados:
    """O que a análise deixou na pasta do candidato; None é o que ainda não existe."""

    pasta: Path
    indice: Path | None
    recomendacoes: str | None
    pratica: str | None
    tabelas_pratica: dict[str, Path]


def resultados(contexto: Contexto) -> Resultados:
    pasta = pasta_do_candidato(contexto)
    indice = pasta / relatorio_html.ARQUIVO_INDICE
    pratica = pasta / PASTA_PRATICA
    return Resultados(
        pasta=pasta,
        indice=indice if indice.is_file() else None,
        recomendacoes=_texto(pasta / PASTA_CONSOLIDADO / ARQUIVO_RECOMENDACOES),
        pratica=_texto(pratica / ARQUIVO_RESUMO),
        tabelas_pratica={
            titulo: pratica / nome
            for nome, titulo in TABELAS_DA_PRATICA.items()
            if (pratica / nome).is_file()
        },
    )


def abrir_no_navegador(caminho: Path | str) -> None:
    relatorio_html.abrir_no_navegador(caminho)


def _texto(caminho: Path) -> str | None:
    return caminho.read_text(encoding='utf-8') if caminho.is_file() else None
