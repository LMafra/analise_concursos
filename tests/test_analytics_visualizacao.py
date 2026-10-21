import pandas as pd

from concursos.analytics.visualizacao import (
    aviso_modelos,
    box_por_disciplina,
    linha_evolucao,
    painel_correcao,
)

COMPARACAO = pd.DataFrame(
    {
        'concurso': ['tcu_25', 'cpnu', 'cpnu'],
        'variante': [pd.NA, 'B3-08-A', 'B3-10-A'],
        'modelo_correcao': ['liquida', 'ponderada', 'ponderada'],
        'fator_penalidade': [1.0, 0.0, 0.0],
        'n': [185, 89, 89],
        'percentual_bruta': [72.5, 57.8, 57.8],
        'percentual_corrigida': [45.0, 63.3, 63.3],
        'percentual_ajustada': [45.0, 47.2, 47.2],
    }
)


def test_painel_tem_as_tres_versoes_por_concurso_e_variante():
    figura = painel_correcao(COMPARACAO)

    assert [serie.name for serie in figura.data] == ['bruto', 'corrigido', 'ajustado']
    assert list(figura.data[0].x) == ['tcu_25', 'cpnu (B3-08-A)', 'cpnu (B3-10-A)']
    assert list(figura.data[1].y) == [45.0, 63.3, 63.3]
    assert figura.layout.barmode == 'group'


def test_hover_mostra_modelo_e_fator():
    figura = painel_correcao(COMPARACAO)

    for serie in figura.data:
        assert [list(linha) for linha in serie.customdata] == [
            ['liquida', 1.0, 185],
            ['ponderada', 0.0, 89],
            ['ponderada', 0.0, 89],
        ]
        assert '%{customdata[0]}' in serie.hovertemplate
        assert '%{customdata[1]' in serie.hovertemplate


EVOLUCAO = pd.DataFrame(
    {
        'concurso': ['a', 'b', 'c', 'a', 'b', 'c'],
        'banca': ['cebraspe', 'fgv', 'cebraspe'] * 2,
        'ordem': pd.array([1, 2, 3] * 2, dtype='Int64'),
        'bloco': ['geral'] * 3 + ['especifico'] * 3,
        'disciplina': ['Português'] * 3 + ['TI'] * 3,
        'n': [10, 3, 12, 8, 9, 2],
        'amostra_insuficiente': [False, True, False, False, False, True],
        'percentual': [50.0, 40.0, 60.0, 30.0, 35.0, 90.0],
        'zscore': [0.5, -0.2, 0.8, -1.0, -0.4, 1.5],
    }
)


def test_linha_de_evolucao_deixa_n_pequeno_fora_da_linha_continua():
    figura = linha_evolucao(EVOLUCAO)

    continuas = [serie for serie in figura.data if 'lines' in serie.mode]
    soltas = [serie for serie in figura.data if serie.mode == 'markers']
    assert {serie.meta for serie in continuas} == {'Português (geral)', 'TI (especifico)'}
    portugues = [serie for serie in continuas if serie.meta == 'Português (geral)']
    assert [list(serie.x) for serie in portugues] == [[1, 3], [1, 3]]
    assert all(serie.marker.opacity < 1 for serie in soltas)
    assert sorted(x for serie in soltas if serie.meta == 'Português (geral)' for x in serie.x) == [2, 2]


def test_linha_de_evolucao_tem_percentual_e_zscore_hover_com_n_e_filtro():
    figura = linha_evolucao(EVOLUCAO)

    portugues = [
        serie for serie in figura.data if serie.meta == 'Português (geral)' and 'lines' in serie.mode
    ]
    assert sorted(list(serie.y) for serie in portugues) == [[0.5, 0.8], [50.0, 60.0]]
    assert all('n = %{customdata[2]}' in serie.hovertemplate for serie in figura.data)
    botoes = figura.layout.updatemenus[0].buttons
    assert [botao.label for botao in botoes] == ['Português (geral)', 'TI (especifico)']
    assert sum(botoes[0].args[0]['visible']) == sum(
        serie.meta == 'Português (geral)' for serie in figura.data
    )


def test_linha_estratificada_tem_uma_linha_por_banca():
    tabela = EVOLUCAO.assign(amostra_insuficiente=False)

    figura = linha_evolucao(tabela, estrato='banca')

    portugues = [
        serie for serie in figura.data if serie.meta == 'Português (geral)' and 'lines' in serie.mode
    ]
    assert sorted(serie.name for serie in portugues) == ['cebraspe', 'cebraspe', 'fgv', 'fgv']


def test_box_por_disciplina_com_os_pontos():
    figura = box_por_disciplina(EVOLUCAO)

    assert [serie.name for serie in figura.data] == ['Português (geral)', 'TI (especifico)']
    assert all(serie.boxpoints == 'all' for serie in figura.data)
    assert list(figura.data[0].y) == [0.5, -0.2, 0.8]


def test_aviso_de_modelos_distintos():
    assert '⚠ modelos de correção distintos' in aviso_modelos(['bruta', 'liquida'])._repr_markdown_()
    assert '⚠' not in aviso_modelos(['liquida'])._repr_markdown_()
