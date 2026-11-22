"""Cancelamento cooperativo da análise."""

import threading
from pathlib import Path

import pytest
from conftest import criar_concurso

from concursos.modelo import Etapa
from concursos.pipeline import AnaliseCancelada, analisar_todos
from concursos.pipeline.nucleo import _pasta_temporaria


def _dois_concursos(raiz: Path) -> None:
    arquivos = {'gabarito.txt': '1 A\n2 B\n', 'respostas.txt': '1 A\n2 C\n'}
    for nome in ('alfa', 'beta'):
        criar_concurso(
            raiz / 'provas',
            nome,
            {
                'nome': nome,
                'banca': 'fgv',
                'formato': 'multipla_escolha',
                'pontuacao': 'simples',
                'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 2]}},
                'respostas': {'arquivo': 'respostas.txt'},
            },
            arquivos,
        )


def test_cancelar_entre_concursos_descarta_temporaria_e_mantem_anterior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dois_concursos(tmp_path)
    provas = tmp_path / 'provas'
    analises = tmp_path / 'analises'
    cancelar = threading.Event()
    visto: list[str] = []

    def ao_progresso(nome: str, indice: int, total: int) -> None:
        visto.append(nome)
        if nome == 'beta':
            cancelar.set()

    with pytest.raises(AnaliseCancelada):
        analisar_todos(provas, analises, cancelar=cancelar, ao_progresso=ao_progresso)

    assert visto == ['alfa', 'beta']
    assert (analises / 'alfa' / 'relatorio.md').exists()
    assert not (analises / 'beta').exists()
    assert not _pasta_temporaria(analises / 'beta').exists()


def test_cancelar_na_etapa_nao_sobrescreve_analise_boa(tmp_path: Path) -> None:
    _dois_concursos(tmp_path)
    provas = tmp_path / 'provas'
    analises = tmp_path / 'analises'
    assert analisar_todos(provas, analises, apenas='alfa') is True
    bom = (analises / 'alfa' / 'relatorio.md').read_text(encoding='utf-8')
    cancelar = threading.Event()

    def ao_etapa(nome: str, etapa: Etapa) -> None:
        if nome == 'alfa' and etapa is Etapa.CORRIGINDO:
            cancelar.set()

    with pytest.raises(AnaliseCancelada):
        analisar_todos(provas, analises, forcar=True, apenas='alfa', ao_etapa=ao_etapa, cancelar=cancelar)

    assert (analises / 'alfa' / 'relatorio.md').read_text(encoding='utf-8') == bom
    assert not _pasta_temporaria(analises / 'alfa').exists()
