from pathlib import Path

import pandas as pd

from concursos.analytics.dashboard_fontes import (
    EMPTY_CONCURSOS,
    EMPTY_SIMULADOS,
    EMPTY_TEC,
    MetasDashboard,
    RegistroSimulado,
    html_dashboard,
    kpis_concursos,
    kpis_concursos_resumo,
    kpis_simulados,
    kpis_tec,
    metas_do_toml,
)
from concursos.analytics.painel import Kpis, Prova


def test_metas_do_toml_lidas():
    metas = metas_do_toml({'dashboard': {'tec_meta_alta': 0.9, 'banca_alvo': 'FGV'}})
    assert metas.tec_alta == 0.9
    assert metas.banca_alvo == 'FGV'


def test_kpis_tec_vazios(tmp_path: Path):
    sub = kpis_tec(tmp_path)
    assert sub.vazio == EMPTY_TEC
    assert sub.cta


def _csv_tec(tmp_path: Path, linhas: list[dict]) -> None:
    pratica = tmp_path / 'pratica'
    pratica.mkdir(exist_ok=True)
    pd.DataFrame(linhas).to_csv(pratica / 'tec_respostas.csv', index=False)


def test_kpis_tec_trio_notebooklm(tmp_path: Path):
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
    _csv_tec(tmp_path, linhas)
    sub = kpis_tec(tmp_path, MetasDashboard(banca_alvo='CESPE', amostra_minima=10))
    assert sub.vazio is None
    assert len(sub.kpis) == 3
    assert 'Taxa geral' in sub.kpis[0].rotulo
    assert 'gargalo' in sub.kpis[1].rotulo.lower()
    assert 'Constitucional' in sub.kpis[1].valor
    assert 'banca alvo' in sub.kpis[2].rotulo.lower()
    assert 'CESPE' in sub.kpis[2].valor


def test_kpis_tec_amostra_insuficiente_e_banca_ausente(tmp_path: Path):
    _csv_tec(
        tmp_path,
        [
            {
                'id': '1',
                'tipo_questao': 'certo_errado',
                'mat': 'X',
                'ass': 'Y',
                'banca': 'FGV',
                'resultado': 'acerto',
            }
        ],
    )
    sub = kpis_tec(tmp_path, MetasDashboard(banca_alvo='CEBRASPE', amostra_minima=10))
    assert 'Amostra' in (sub.kpis[1].selo.texto if sub.kpis[1].selo else '')
    assert 'Sem questões' in sub.kpis[2].valor


def test_kpis_tec_banca_mais_frequente(tmp_path: Path):
    _csv_tec(
        tmp_path,
        [
            {
                'id': str(i),
                'tipo_questao': 'certo_errado',
                'mat': 'A',
                'ass': 'B',
                'banca': 'FGV' if i < 3 else 'CESPE',
                'resultado': 'acerto',
            }
            for i in range(5)
        ],
    )
    sub = kpis_tec(tmp_path, MetasDashboard(amostra_minima=1))
    assert 'FGV' in sub.kpis[2].valor


def test_kpis_concursos_vazios_e_resumo():
    from concursos.analytics.painel import tendencia_geral

    vazio = kpis_concursos([])
    assert vazio.vazio == EMPTY_CONCURSOS
    legado = kpis_concursos_resumo(
        Kpis(
            concursos=0,
            provas=0,
            acima=0,
            abaixo=0,
            no_limite=0,
            com_corte=0,
            melhor=None,
            mais_fraco=None,
            tendencia=tendencia_geral(None),
        )
    )
    assert legado.vazio == EMPTY_CONCURSOS


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


def test_kpis_simulados_vazio_primeiro_e_queda():
    assert kpis_simulados([]).vazio == EMPTY_SIMULADOS
    primeiro = kpis_simulados([RegistroSimulado('A', 'PCI', 70.0, '2025-01-01')])
    assert 'Primeiro' in primeiro.kpis[1].valor
    queda = kpis_simulados(
        [
            RegistroSimulado('B', 'TEC', 60.0, '2025-02-01'),
            RegistroSimulado('A', 'PCI', 80.0, '2025-01-01'),
        ]
    )
    assert '↘' in queda.kpis[1].valor or '-' in queda.kpis[1].valor


def test_html_dashboard_vazio_e_com_extras():
    vazio = html_dashboard([kpis_concursos([])])
    assert 'empty-msg' in vazio and EMPTY_CONCURSOS in vazio
    cheio = html_dashboard(
        [kpis_concursos([Prova('a', 'A', 80.0, data='2025-01-01', gap=2.5, atingido=True)])]
    )
    assert 'dash-extras' in cheio and 'kpi-valor' in cheio
