import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

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
    ARQUIVO_SIMULADO,
    PASTA_PRATICA,
)
from concursos.relatorio_html import ARQUIVO_INDICE, ARQUIVO_RELATORIO_HTML
from concursos.simulado_focado import ARQUIVO_SIMULADO_FOCADO

logger = logging.getLogger('concursos')

TABELAS_DA_PRATICA = {
    ARQUIVO_DESEMPENHO: 'Desempenho por disciplina',
    ARQUIVO_ERROS: 'Erros',
    ARQUIVO_CADERNOS: 'Cadernos',
}


@dataclass(frozen=True)
class RelatorioEscolhido:
    """Uma opção do seletor de Resultados: visão geral ou um concurso."""

    rotulo: str
    caminho: Path


@dataclass(frozen=True)
class Resultados:
    """O que a análise deixou na pasta do candidato; None é o que ainda não existe."""

    pasta: Path
    indice: Path | None
    recomendacoes: str | None
    pratica: str | None
    tabelas_pratica: dict[str, Path]
    simulado_focado: str | None = None
    simulado_tec: Path | None = None


def resultados(contexto: Contexto) -> Resultados:
    pasta = pasta_do_candidato(contexto)
    indice = pasta / ARQUIVO_INDICE
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
        simulado_focado=_texto(pasta / ARQUIVO_SIMULADO_FOCADO),
        simulado_tec=pratica / ARQUIVO_SIMULADO if (pratica / ARQUIVO_SIMULADO).is_file() else None,
    )


def relatorios_disponiveis(contexto: Contexto) -> list[RelatorioEscolhido]:
    """Visão geral (`index.html`) e cada `relatorio.html` de concurso analisado."""
    pasta = pasta_do_candidato(contexto)
    indice = pasta / ARQUIVO_INDICE
    if not indice.is_file():
        return []
    opcoes = [RelatorioEscolhido('Visão geral', indice)]
    for filho in sorted(pasta.iterdir()):
        relatorio = filho / ARQUIVO_RELATORIO_HTML
        if filho.is_dir() and relatorio.is_file():
            opcoes.append(RelatorioEscolhido(filho.name, relatorio))
    return opcoes


def abrir_no_navegador(caminho: Path | str) -> None:
    relatorio_html.abrir_no_navegador(caminho)


def _texto(caminho: Path) -> str | None:
    return caminho.read_text(encoding='utf-8') if caminho.is_file() else None


@dataclass(frozen=True)
class PontoDeNota:
    """Nota e corte já calculados, em percentual, na ordem da prova."""

    concurso: str
    ordem: int
    nota: float
    corte: float | None
    atingido: bool | None


@dataclass(frozen=True)
class TopicoParaAgir:
    disciplina: str
    topico: str
    percentual: float


@dataclass(frozen=True)
class ResumoVisual:
    pontos: tuple[PontoDeNota, ...] = ()
    fracos: tuple[TopicoParaAgir, ...] = ()


def resumo_visual(contexto: Contexto) -> ResumoVisual:
    """Lê o consolidado já gravado. Sem ele, o hero e o gráfico ficam vazios e a tela segue."""
    from concursos.analytics.consolidado import (
        ARQUIVO_PARQUET,
        cortes_por_concurso,
        pasta_consolidado,
        regras_por_concurso,
    )
    from concursos.analytics.evolucao import comparar_percentual_e_gap, topicos_fracos_persistentes
    from concursos.configuracao import configuracao_do_projeto

    pasta = pasta_do_candidato(contexto)
    cache = pasta_consolidado(pasta) / ARQUIVO_PARQUET
    if not cache.is_file():
        return ResumoVisual()
    try:
        consolidado = pd.read_parquet(cache)
        if consolidado.empty:
            return ResumoVisual()
        tabela = comparar_percentual_e_gap(consolidado, cortes_por_concurso(regras_por_concurso(pasta)))
        limiar = configuracao_do_projeto(contexto).limiar_topico_baixo
        fracos = topicos_fracos_persistentes(consolidado, limiar=limiar)
    except Exception:  # noqa: BLE001
        logger.debug('resumo visual indisponível', exc_info=True)
        return ResumoVisual()
    return ResumoVisual(pontos=_pontos(tabela), fracos=_fracos(fracos))


def _pontos(tabela: pd.DataFrame) -> tuple[PontoDeNota, ...]:
    escolhidos: dict[str, PontoDeNota] = {}
    for linha in tabela.itertuples(index=False):
        nota = float(linha.percentual_ponderado)
        if pd.isna(nota):
            continue
        gap = linha.menor_gap_percentual
        corte = None if pd.isna(gap) else nota - float(gap)
        atingido = None if pd.isna(linha.atingido) else bool(linha.atingido)
        ponto = PontoDeNota(str(linha.concurso), int(linha.ordem), nota, corte, atingido)
        atual = escolhidos.get(ponto.concurso)
        if atual is None or (ponto.corte is not None and (atual.corte is None or ponto.nota - ponto.corte < atual.nota - (atual.corte or 0))):
            escolhidos[ponto.concurso] = ponto
    return tuple(sorted(escolhidos.values(), key=lambda ponto: ponto.ordem))


def _fracos(tabela: pd.DataFrame) -> tuple[TopicoParaAgir, ...]:
    if tabela.empty:
        return ()
    linhas = tabela.sort_values('percentual').head(3).itertuples(index=False)
    return tuple(
        TopicoParaAgir(str(linha.disciplina), str(linha.topico), float(linha.percentual)) for linha in linhas
    )
