"""Regras do edital, taxonomia do projeto e diff de gabarito."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from concursos.analytics.catalogo_edital import gravar_catalogo
from concursos.analytics.correcao import ConfiguracaoCorrecao
from concursos.analytics.regras_edital import RegrasEdital, extrair_regras
from concursos.analytics.taxonomia import DisciplinaCanonica, TaxonomiaInvalidaError, carregar_taxonomia
from concursos.analytics.validacao_edital import gravar_discrepancias, validar_edital
from concursos.atualizacao import ARQUIVO_DIFF, diff_gabarito, questoes_preliminares
from concursos.concurso_config import ConcursoConfig
from concursos.config.contexto import resolver_contexto
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO
from concursos.edital_a_confirmar import gravar_confirmacao
from concursos.edital_llm import completar_com_llm
from concursos.erros import avisar
from concursos.llm import ClienteLlm
from concursos.texto import extrair_paginas

logger = logging.getLogger(__name__)


def regras_do_edital(
    config: ConcursoConfig,
    documentos: dict[str, list[str]],
    resultados: pd.DataFrame,
    correcoes: list[ConfiguracaoCorrecao],
    destino: Path,
    taxonomia: dict[str, DisciplinaCanonica] | None,
    cliente_llm: ClienteLlm | None = None,
) -> RegrasEdital | None:
    """Regras do edital no edital estruturado e as discrepâncias com a prova; só quando há PDF do edital."""
    if not documentos:
        return None
    retificacoes = {
        arquivo: extrair_paginas(config.caminho(arquivo), ocr=False) for arquivo in config.edital.retificacoes
    }
    regras = extrair_regras(config, documentos, retificacoes)
    if cliente_llm is not None:
        regras = completar_com_llm(regras, documentos, cliente_llm)
    regras.gravar_json(destino / ARQUIVO_EDITAL_ESTRUTURADO)
    gravar_confirmacao(config, regras, correcoes)
    gravar_discrepancias(validar_edital(config, regras, resultados, taxonomia, correcoes), destino)
    gravar_catalogo(config, regras, destino)
    return regras


def taxonomia_do_contexto() -> dict[str, DisciplinaCanonica] | None:
    """Taxonomia do projeto (`.concurso/` ou legado na raiz); vazia ou inválida vira None na validação."""
    caminho = resolver_contexto().taxonomia
    if not caminho.exists():
        return None
    try:
        mapeamento = carregar_taxonomia(caminho)
    except TaxonomiaInvalidaError as erro:
        avisar(
            logger,
            'não consegui ler a lista de disciplinas equivalentes; comparei as disciplinas do edital só pelo nome.',
            'corrija a lista em Configurações > Disciplinas e temas.',
            str(erro),
        )
        return None
    return mapeamento or None


def diff_da_troca(destino: Path, resultados: pd.DataFrame) -> pd.DataFrame | None:
    preliminar = questoes_preliminares(destino)
    if preliminar is None:
        (destino / ARQUIVO_DIFF).unlink(missing_ok=True)
        return None
    diff = diff_gabarito(preliminar, resultados)
    diff.to_csv(destino / ARQUIVO_DIFF, index=False)
    return diff
