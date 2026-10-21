import pandas as pd

from concursos.analytics.visualizacao import (
    aviso_modelos,
    barras_fracos,
    box_por_disciplina,
    exportar_heatmap_topicos,
    exportar_linha_evolucao,
    exportar_painel_correcao,
    heatmap_topicos,
    linha_evolucao,
    painel_correcao,
)

PNG = b'\x89PNG'

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


PERCENTUAIS = pd.DataFrame(
    {
        'concurso': ['b', 'a', 'a', 'b', 'b'],
        'ordem': [2, 1, 1, 2, 2],
        'disciplina': 'Português',
        'topico': ['Crase', 'Crase', 'Regência', 'Regência', 'Pontuação'],
        'chave_topico': ['crase', 'crase', 'regencia', 'regencia', 'pontuacao'],
        'n': [5, 2, 6, 1, 7],
        'amostra_insuficiente': [False, True, False, True, False],
        'percentual': [40.0, 50.0, 83.3, -100.0, 70.0],
    }
)


def test_heatmap_anota_so_as_celulas_com_n_minimo():
    figura = heatmap_topicos(PERCENTUAIS)
    percentual, cinza = figura.data

    assert list(percentual.x) == ['a', 'b']
    assert list(percentual.y) == ['Crase (Português)', 'Pontuação (Português)', 'Regência (Português)']
    assert [list(linha) for linha in percentual.text] == [['', '40%'], ['', '70%'], ['83%', '']]
    assert [list(linha) for linha in cinza.text] == [['n<5', ''], ['', ''], ['', 'n<5']]
    assert pd.isna(percentual.z[0][0])
    assert cinza.showscale is False
    assert [list(linha) for linha in heatmap_topicos(PERCENTUAIS, min_n=6).data[1].text][0] == ['n<6', 'n<6']


def test_barras_de_fracos_empilham_acertos_e_erros_com_n():
    fracos = pd.DataFrame(
        {
            'disciplina': 'Português',
            'topico': ['Crase', 'Regência'],
            'n': [6, 7],
            'acertos': [3, 1],
            'erros': [3, 5],
            'brancos': [0, 1],
            'percentual': [0.0, -57.1],
            'concursos_abaixo': [['a', 'b'], ['a', 'c']],
        }
    )

    figura = barras_fracos(fracos)

    assert figura.layout.barmode == 'stack'
    assert [serie.name for serie in figura.data] == ['acertos', 'erros', 'brancos']
    assert list(figura.data[1].x) == [3, 5]
    assert [nota.text for nota in figura.layout.annotations] == ['n = 6', 'n = 7']


def rotulos(eixo) -> list[str]:
    return [linha.get_label() for linha in eixo.get_lines() if not linha.get_label().startswith('_')]


def test_exporta_a_linha_so_com_series_de_pontos_suficientes(tmp_path):
    caminho = tmp_path / 'linha.png'

    figura = exportar_linha_evolucao(EVOLUCAO, caminho, min_pontos=2)

    assert caminho.read_bytes().startswith(PNG)
    assert rotulos(figura.axes[0]) == ['Português (geral)', 'TI (especifico)']
    assert rotulos(exportar_linha_evolucao(EVOLUCAO, tmp_path / 'vazia.png').axes[0]) == []
    assert (tmp_path / 'vazia.png').exists()


def test_exporta_o_heatmap_anotado_so_com_n_minimo(tmp_path):
    caminho = tmp_path / 'heatmap.png'

    figura = exportar_heatmap_topicos(PERCENTUAIS, caminho)

    assert caminho.read_bytes().startswith(PNG)
    assert sorted(texto.get_text() for texto in figura.axes[0].texts) == ['40%', '70%', '83%', 'n<5', 'n<5']


def test_exporta_o_painel_com_as_tres_versoes(tmp_path):
    caminho = tmp_path / 'painel.png'

    figura = exportar_painel_correcao(COMPARACAO, caminho)

    assert caminho.read_bytes().startswith(PNG)
    assert [barras.get_label() for barras in figura.axes[0].containers] == ['bruto', 'corrigido', 'ajustado']
    assert len(figura.axes[0].containers[0]) == len(COMPARACAO)
