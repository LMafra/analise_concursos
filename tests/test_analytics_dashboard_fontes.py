from pathlib import Path

import pandas as pd

from concursos.analytics.dashboard_fontes import (
    EMPTY_TEC,
    MetasDashboard,
    RegistroSimulado,
    kpis_concursos,
    kpis_simulados,
    kpis_tec,
    metas_do_toml,
)
from concursos.analytics.painel import Prova


def test_metas_do_toml_lidas():
    metas = metas_do_toml({'dashboard': {'tec_meta_alta': 0.9, 'banca_alvo': 'FGV'}})
    assert metas.tec_alta == 0.9
    assert metas.banca_alvo == 'FGV'


def test_kpis_tec_vazios(tmp_path: Path):
    sub = kpis_tec(tmp_path)
    assert sub.vazio == EMPTY_TEC
    assert sub.cta


def test_kpis_tec_trio_notebooklm(tmp_path: Path):
    pratica = tmp_path / 'pratica'
    pratica.mkdir()
    linhas = []
    for i in range(12):
        linhas.append(
            {
                'id': f'a{i}',
                'tipo_questao': 'certo_errado',
                'mat': 'Direito',
                'ass': 'Constitucional',
                'banca': 'CESPE',
                'resultado': 'erro' if i < 8 else 'acerto',
            }
        )
    for i in range(12):
        linhas.append(
            {
                'id': f'b{i}',
                'tipo_questao': 'certo_errado',
                'mat': 'Português',
                'ass': 'Concordância',
                'banca': 'FGV',
                'resultado': 'acerto',
            }
        )
    pd.DataFrame(linhas).to_csv(pratica / 'tec_respostas.csv', index=False)
    sub = kpis_tec(tmp_path, MetasDashboard(banca_alvo='CESPE', amostra_minima=10))
    assert sub.vazio is None
    assert len(sub.kpis) == 3
    assert 'Taxa geral' in sub.kpis[0].rotulo
    assert 'gargalo' in sub.kpis[1].rotulo.lower()
    assert 'Constitucional' in sub.kpis[1].valor
    assert 'banca alvo' in sub.kpis[2].rotulo.lower()
    assert 'CESPE' in sub.kpis[2].valor


def test_kpis_concursos_distancia_e_media():
    provas = [
        Prova('a', 'A', 80.0, data='2025-01-01', gap=2.5, atingido=True),
        Prova('b', 'B', 70.0, data='2024-01-01', gap=-4.0, atingido=False),
        Prova('c', 'C', 75.0, data='2024-06-01', gap=0.0, atingido=True),
    ]
    sub = kpis_concursos(provas)
    assert sub.kpis[0].rotulo.startswith('Distância')
    assert 'Tendência' in sub.kpis[1].rotulo
    assert 'Média' in sub.kpis[2].rotulo
    assert sub.extras


def test_kpis_simulados_evolucao():
    regs = [
        RegistroSimulado('SEFAZ', 'PCI', 78.0, '2025-02-01'),
        RegistroSimulado('Erros TEC', 'TEC', 68.0, '2025-01-01'),
    ]
    sub = kpis_simulados(regs)
    assert 'último' in sub.kpis[0].rotulo.lower()
    assert 'Evolução' in sub.kpis[1].rotulo
    assert '+' in sub.kpis[1].valor or '↗' in sub.kpis[1].valor
