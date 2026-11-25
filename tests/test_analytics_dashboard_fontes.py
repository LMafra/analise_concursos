from pathlib import Path

import pandas as pd

from concursos.analytics.dashboard_fontes import kpis_tec, kpis_concursos_resumo
from concursos.analytics.painel import Kpis, Tendencia


def test_kpis_tec_vazios(tmp_path: Path):
    sub = kpis_tec(tmp_path)
    assert sub.vazio
    assert sub.kpis == []


def test_kpis_tec_com_respostas(tmp_path: Path):
    pratica = tmp_path / 'pratica'
    pratica.mkdir()
    pd.DataFrame(
        [
            {
                'id': '1',
                'tipo_questao': 'certo_errado',
                'mat': 'Direito',
                'ass': 'Constitucional',
                'banca': 'CESPE',
                'resultado': 'erro',
            },
            {
                'id': '2',
                'tipo_questao': 'certo_errado',
                'mat': 'Direito',
                'ass': 'Constitucional',
                'banca': 'CESPE',
                'resultado': 'erro',
            },
            {
                'id': '3',
                'tipo_questao': 'multipla_escolha',
                'mat': 'Português',
                'ass': 'Concordância',
                'banca': 'FGV',
                'resultado': 'acerto',
            },
        ]
    ).to_csv(pratica / 'tec_respostas.csv', index=False)
    sub = kpis_tec(tmp_path)
    assert sub.vazio is None
    assert len(sub.kpis) == 3
    assert '33' in sub.kpis[0].valor or '1 de 3' in sub.kpis[0].valor or '%' in sub.kpis[0].valor
    assert 'Constitucional' in sub.kpis[1].valor


def test_kpis_concursos_resumo():
    indicadores = Kpis(
        concursos=2,
        provas=2,
        acima=1,
        abaixo=1,
        no_limite=0,
        com_corte=2,
        melhor=None,
        mais_fraco=None,
        tendencia=Tendencia('estavel', 'Estável', '→', 'Seu desempenho geral está estável.'),
    )
    sub = kpis_concursos_resumo(indicadores)
    assert sub.vazio is None
    assert any('1 de 2' in k.valor for k in sub.kpis)
