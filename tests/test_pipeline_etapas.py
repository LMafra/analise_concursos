"""Cobertura das etapas privadas do pipeline (ramos raros pós-extração)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from concursos.analytics.taxonomia import TaxonomiaInvalidaError
from concursos.pipeline.etapas import leitura, regras


def test_paginas_sem_edital_devolve_vazio():
    config = MagicMock()
    config.edital = None
    assert leitura.paginas_dos_documentos(config) == {}


def test_ler_edital_sem_edital_devolve_none():
    config = MagicMock()
    config.edital = None
    assert leitura.ler_edital(config, {}) is None


def test_taxonomia_ausente(tmp_path, monkeypatch):
    ctx = MagicMock()
    ctx.taxonomia = tmp_path / 'taxonomia.yaml'
    monkeypatch.setattr(regras, 'resolver_contexto', lambda: ctx)
    assert regras.taxonomia_do_contexto() is None


def test_taxonomia_invalida(tmp_path, monkeypatch):
    caminho = tmp_path / 'taxonomia.yaml'
    caminho.write_text('x: 1\n', encoding='utf-8')
    ctx = MagicMock()
    ctx.taxonomia = caminho
    monkeypatch.setattr(regras, 'resolver_contexto', lambda: ctx)

    def _falha(_):
        raise TaxonomiaInvalidaError('ruim')

    monkeypatch.setattr(regras, 'carregar_taxonomia', _falha)
    assert regras.taxonomia_do_contexto() is None


def test_taxonomia_vazia_vira_none(tmp_path, monkeypatch):
    caminho = tmp_path / 'taxonomia.yaml'
    caminho.write_text('{}\n', encoding='utf-8')
    ctx = MagicMock()
    ctx.taxonomia = caminho
    monkeypatch.setattr(regras, 'resolver_contexto', lambda: ctx)
    monkeypatch.setattr(regras, 'carregar_taxonomia', lambda _: {})
    assert regras.taxonomia_do_contexto() is None


def test_diff_sem_preliminar_apaga_arquivo(tmp_path, monkeypatch):
    import pandas as pd

    diff = tmp_path / 'diff_gabarito.csv'
    diff.write_text('a\n', encoding='utf-8')
    monkeypatch.setattr(regras, 'questoes_preliminares', lambda _: None)
    assert regras.diff_da_troca(tmp_path, pd.DataFrame()) is None
    assert not diff.exists()


def test_caderno_ausente_avisa(tmp_path):
    config = MagicMock()
    config.caminho = lambda nome: tmp_path / nome
    prova = MagicMock()
    prova.caderno = 'caderno.pdf'
    prova.chave = 'unica'
    assert leitura.caderno_presente(config, prova) is False


def test_folha_sem_todas_as_questoes_falha(tmp_path, monkeypatch):
    from concursos.folha import FolhaIlegivelError
    from concursos.modelo import Estado, Origem, RespostaMarcada

    config = MagicMock()
    config.respostas_arquivo = None
    config.provas = [MagicMock(questoes=(1, 2))]
    config.folha = MagicMock(arquivo='folha.png', template='x', total_itens=None, itens_por_coluna=None)
    config.caminho = lambda n: tmp_path / n
    config.formato.letras = lambda n: 'ABCDE'
    config.n_alternativas = 5
    parcial = [
        RespostaMarcada(
            questao=1,
            alternativa='A',
            estado=Estado.MARCADA,
            confianca=1.0,
            origem=Origem.FOLHA,
            arquivo='folha.png',
            pagina=1,
        )
    ]
    monkeypatch.setattr(leitura, 'ler_folha', lambda *a, **k: parcial)
    with pytest.raises(FolhaIlegivelError):
        leitura.ler_respostas(config, tmp_path, 0.5)
