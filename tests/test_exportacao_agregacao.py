"""Testes sintéticos de exportação e agregação."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd

from concursos.agregacao import agregar, percentual_de_merito
from concursos.exportacao import FormatoExportacao, exportar_consolidado
from concursos.modelo import Pontuacao, Resultado


def test_agregar_percentual_e_colunas() -> None:
    resultados = pd.DataFrame(
        {
            'concurso': ['a', 'a', 'a'],
            'prova': ['u', 'u', 'u'],
            'disciplina': ['dir', 'dir', 'port'],
            'topico': ['t1', 't1', 't2'],
            'questao': [1, 2, 3],
            'resultado': [Resultado.ACERTO, Resultado.ERRO, Resultado.ACERTO],
            'anulada': [False, False, True],
        }
    )
    tabela = agregar(resultados, ['concurso', 'prova', 'disciplina'], Pontuacao.SIMPLES)
    assert list(tabela.columns) == [
        'concurso',
        'prova',
        'disciplina',
        'topico',
        'total',
        'acertos',
        'erros',
        'percentual',
        'em_branco',
        'anuladas',
        'nota_liquida',
    ]
    dir_ = tabela[tabela['disciplina'] == 'dir'].iloc[0]
    assert dir_['total'] == 2
    assert dir_['acertos'] == 1
    assert dir_['erros'] == 1
    assert percentual_de_merito(tabela).iloc[0] == 50.0


def test_exportar_consolidado_csv(tmp_path: Path) -> None:
    tabela = pd.DataFrame(
        {
            'concurso': ['alfa'],
            'prova': ['unica'],
            'questao': [1],
            'disciplina': ['Português'],
            'topico': ['Crase'],
            'resultado': ['acerto'],
        }
    )
    provas = tmp_path / 'provas'
    analises = tmp_path / 'analises'
    taxonomia = tmp_path / 'taxonomia.yaml'
    taxonomia.write_text('', encoding='utf-8')
    with patch('concursos.exportacao.carregar_consolidado', return_value=tabela):
        destino = exportar_consolidado(provas, analises, taxonomia, FormatoExportacao.CSV)
    assert destino == analises / 'export' / 'consolidado.csv'
    assert destino.read_text(encoding='utf-8').startswith('concurso,')


def test_exportar_consolidado_md(tmp_path: Path) -> None:
    tabela = pd.DataFrame({'concurso': ['alfa'], 'questao': [1]})
    with patch('concursos.exportacao.carregar_consolidado', return_value=tabela):
        destino = exportar_consolidado(
            tmp_path / 'provas', tmp_path / 'analises', tmp_path / 't.yaml', FormatoExportacao.MD
        )
    assert destino.suffix == '.md'
    assert destino.read_text(encoding='utf-8')
