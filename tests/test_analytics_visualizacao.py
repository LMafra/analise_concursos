import pandas as pd

from concursos.analytics.visualizacao import painel_correcao

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
