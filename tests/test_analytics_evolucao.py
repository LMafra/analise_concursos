import pandas as pd
import pytest

from concursos.analytics.evolucao import comparar_bruto_vs_corrigido

ALTERNATIVAS = {'certo_errado': 2, 'multipla_escolha': 5}


def concurso(
    nome: str,
    resultados: list[str],
    formato: str = 'certo_errado',
    anuladas: tuple[int, ...] = (),
    pesos: dict[str, list[float]] | None = None,
) -> pd.DataFrame:
    """Linhas mínimas do consolidado: Cebraspe líquida (fator 1) ou FGV bruta, com pontuação por item."""
    fator = 1.0 if formato == 'certo_errado' else 0.0
    k = ALTERNATIVAS[formato]
    anulada = [i + 1 in anuladas for i in range(len(resultados))]
    pontos = {
        'bruta': {'acerto': 1.0, 'erro': 0.0, 'branco': 0.0},
        'corrigida': {'acerto': 1.0, 'erro': -fator, 'branco': 0.0},
        'ajustada': {'acerto': 1.0, 'erro': -1 / (k - 1), 'branco': 0.0},
    }
    tabela = pd.DataFrame(
        {
            'concurso': nome,
            'questao': range(1, len(resultados) + 1),
            'anulada': anulada,
            'resultado': resultados,
            'modelo_correcao': 'liquida' if fator else ('ponderada' if pesos else 'bruta'),
            'fator_penalidade': fator,
            'nota_maxima': float(len(resultados)),
            'ordem': pd.array([pd.NA] * len(resultados), dtype='Int64'),
        }
    )
    for versao, valores in pontos.items():
        tabela[f'pontos_{versao}'] = tabela['resultado'].map(valores).mask(tabela['anulada'])
    for variante, valores in (pesos or {'padrao': [1.0] * len(resultados)}).items():
        tabela[f'peso__{variante}'] = valores
    return tabela


def consolidado(*concursos: pd.DataFrame) -> pd.DataFrame:
    return pd.concat(concursos, ignore_index=True)


def test_um_concurso_so_fica_em_primeiro_nas_tres_versoes():
    tabela = comparar_bruto_vs_corrigido(consolidado(concurso('tcu', ['acerto', 'erro', 'acerto', 'branco'])))

    linha = tabela.iloc[0]
    assert len(tabela) == 1
    assert (linha['percentual_bruta'], linha['percentual_corrigida'], linha['percentual_ajustada']) == (
        50.0,
        25.0,
        25.0,
    )
    assert (linha['posicao_bruta'], linha['posicao_corrigida'], linha['posicao_ajustada']) == (1, 1, 1)
    assert (linha['deslocamento_corrigida'], linha['deslocamento_ajustada']) == (0, 0)
    assert (linha['modelo_correcao'], linha['fator_penalidade'], linha['n']) == ('liquida', 1.0, 4)


def test_correcao_liquida_contra_bruta_muda_a_posicao():
    cebraspe = concurso('cebraspe', ['acerto'] * 7 + ['erro'] * 3)
    fgv = concurso('fgv', ['acerto'] * 6 + ['erro'] * 4, formato='multipla_escolha')

    tabela = comparar_bruto_vs_corrigido(consolidado(cebraspe, fgv)).set_index('concurso')

    assert tabela.loc[
        'cebraspe', ['percentual_bruta', 'percentual_corrigida', 'percentual_ajustada']
    ].tolist() == [
        70.0,
        40.0,
        40.0,
    ]
    assert tabela.loc[
        'fgv', ['percentual_bruta', 'percentual_corrigida', 'percentual_ajustada']
    ].tolist() == [
        60.0,
        60.0,
        50.0,
    ]
    assert tabela['posicao_bruta'].to_dict() == {'cebraspe': 1, 'fgv': 2}
    assert tabela['posicao_corrigida'].to_dict() == {'cebraspe': 2, 'fgv': 1}
    assert tabela['deslocamento_corrigida'].to_dict() == {'cebraspe': -1, 'fgv': 1}
    assert tabela['deslocamento_ajustada'].to_dict() == {'cebraspe': -1, 'fgv': 1}


def test_cada_variante_vira_uma_linha_com_o_corrigido_pelo_seu_peso():
    cpnu = concurso(
        'cpnu',
        ['acerto', 'acerto', 'erro', 'erro'],
        formato='multipla_escolha',
        pesos={'B3-08-A': [1.0, 1.0, 1.0, 1.0], 'B3-10-A': [3.0, 3.0, 1.0, 1.0]},
    )
    tcu = concurso('tcu', ['acerto', 'acerto', 'acerto', 'erro'])

    tabela = comparar_bruto_vs_corrigido(consolidado(cpnu, tcu))

    cpnu_linhas = tabela[tabela['concurso'] == 'cpnu'].set_index('variante')
    assert sorted(cpnu_linhas.index) == ['B3-08-A', 'B3-10-A']
    assert cpnu_linhas['percentual_bruta'].tolist() == [50.0, 50.0]
    assert cpnu_linhas.loc['B3-08-A', 'percentual_corrigida'] == 50.0
    assert cpnu_linhas.loc['B3-10-A', 'percentual_corrigida'] == 75.0
    assert pd.isna(tabela.loc[tabela['concurso'] == 'tcu', 'variante'].iloc[0])


def test_variantes_ocupam_uma_posicao_so_no_ranking_dos_outros_concursos():
    cpnu = concurso(
        'cpnu',
        ['acerto', 'acerto', 'erro', 'erro'],
        formato='multipla_escolha',
        pesos={'B3-08-A': [1.0, 1.0, 1.0, 1.0], 'B3-10-A': [3.0, 3.0, 1.0, 1.0]},
    )
    tcu = concurso('tcu', ['acerto', 'acerto', 'acerto', 'erro'])
    fraco = concurso('fraco', ['acerto', 'erro', 'erro', 'erro'], formato='multipla_escolha')

    tabela = comparar_bruto_vs_corrigido(consolidado(cpnu, tcu, fraco))
    posicoes = tabela.set_index(tabela['concurso'] + '/' + tabela['variante'].fillna(''))

    assert posicoes['posicao_bruta'].to_dict() == {
        'tcu/': 1,
        'cpnu/B3-08-A': 2,
        'cpnu/B3-10-A': 2,
        'fraco/': 3,
    }
    assert posicoes['posicao_corrigida'].to_dict() == {
        'cpnu/B3-10-A': 1,
        'cpnu/B3-08-A': 1,
        'tcu/': 2,
        'fraco/': 3,
    }


def test_anuladas_ficam_fora_do_percentual_e_do_n():
    tabela = comparar_bruto_vs_corrigido(
        consolidado(concurso('tcu', ['acerto', 'erro', 'acerto', 'acerto'], anuladas=(2,)))
    )

    assert tabela.iloc[0]['n'] == 3
    assert tabela.iloc[0]['percentual_bruta'] == pytest.approx(100.0)
    assert tabela.iloc[0]['percentual_corrigida'] == pytest.approx(100.0)


def test_empate_divide_a_mesma_posicao():
    tabela = comparar_bruto_vs_corrigido(
        consolidado(
            concurso('a', ['acerto', 'erro']),
            concurso('b', ['erro', 'acerto']),
            concurso('c', ['erro', 'erro']),
        )
    ).set_index('concurso')

    assert tabela['posicao_bruta'].to_dict() == {'a': 1, 'b': 1, 'c': 3}
    assert tabela['deslocamento_ajustada'].to_dict() == {'a': 0, 'b': 0, 'c': 0}


def test_tabela_sai_ordenada_pela_posicao_ajustada():
    tabela = comparar_bruto_vs_corrigido(
        consolidado(concurso('fraco', ['erro', 'erro']), concurso('forte', ['acerto', 'acerto']))
    )

    assert tabela['concurso'].tolist() == ['forte', 'fraco']
