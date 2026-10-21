import math

import pandas as pd
import pytest

from concursos.analytics.evolucao import (
    comparar_bruto_vs_corrigido,
    correlacao_tempo_zscore,
    modelos_distintos,
    percentual_por_disciplina_ao_longo_do_tempo,
    tendencia_por_disciplina,
    zscore_por_disciplina,
)

ALTERNATIVAS = {'certo_errado': 2, 'multipla_escolha': 5}


def concurso(
    nome: str,
    resultados: list[str],
    formato: str = 'certo_errado',
    anuladas: tuple[int, ...] = (),
    pesos: dict[str, list[float]] | None = None,
    ordem: int | None = None,
    disciplinas: list[str] | None = None,
    blocos: list[str] | None = None,
    topicos: list[str] | None = None,
    banca: str | None = None,
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
            'banca': banca or ('cebraspe' if formato == 'certo_errado' else 'fgv'),
            'prova': 'unica',
            'questao': range(1, len(resultados) + 1),
            'disciplina_canonica': disciplinas or ['Português'] * len(resultados),
            'bloco': blocos or ['geral'] * len(resultados),
            'topico': topicos or ['Crase'] * len(resultados),
            'anulada': anulada,
            'resultado': resultados,
            'modelo_correcao': 'liquida' if fator else ('ponderada' if pesos else 'bruta'),
            'fator_penalidade': fator,
            'nota_maxima': float(len(resultados)),
            'ordem': pd.array([ordem] * len(resultados), dtype='Int64'),
        }
    )
    tabela['disciplina'] = tabela['disciplina_canonica']
    tabela['chave_topico'] = (tabela['disciplina_canonica'] + ' | ' + tabela['topico']).mask(
        tabela['topico'] == 'nao_mapeado'
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


PT, TI = 'Português', 'TI'


def test_percentual_por_disciplina_com_n_e_amostra_insuficiente():
    tcu = concurso(
        'tcu', ['acerto'] * 5 + ['acerto', 'erro', 'erro'], ordem=1, disciplinas=[PT] * 5 + [TI] * 3
    )

    tabela = percentual_por_disciplina_ao_longo_do_tempo(consolidado(tcu)).set_index('disciplina')

    assert tabela.loc[PT, ['n', 'amostra_insuficiente', 'percentual_ajustada']].tolist() == [5, False, 100.0]
    assert tabela.loc[TI, ['n', 'amostra_insuficiente']].tolist() == [3, True]
    assert tabela.loc[TI, 'percentual_corrigida'] == pytest.approx(-100 / 3)
    assert tabela.loc[TI, 'nota_normalizada'] == 0.0
    assert tabela.loc[
        TI, ['concurso', 'banca', 'ordem', 'bloco', 'modelo_correcao', 'fator_penalidade']
    ].tolist() == [
        'tcu',
        'cebraspe',
        1,
        'geral',
        'liquida',
        1.0,
    ]


def test_correcao_liquida_baixa_o_percentual_e_a_bruta_nao():
    cebraspe = concurso('cebraspe', ['acerto', 'acerto', 'acerto', 'erro'], ordem=1)
    fgv = concurso('fgv', ['acerto', 'acerto', 'acerto', 'erro'], formato='multipla_escolha', ordem=2)

    tabela = percentual_por_disciplina_ao_longo_do_tempo(consolidado(cebraspe, fgv)).set_index('concurso')

    assert tabela.loc['cebraspe', ['percentual_bruta', 'percentual_corrigida']].tolist() == [75.0, 50.0]
    assert tabela.loc['fgv', ['percentual_bruta', 'percentual_corrigida']].tolist() == [75.0, 75.0]


def test_geral_e_especifico_ficam_separados():
    pf = concurso(
        'pf',
        ['acerto', 'erro', 'acerto', 'acerto'],
        ordem=1,
        blocos=['geral', 'geral', 'especifico', 'especifico'],
    )

    tabela = percentual_por_disciplina_ao_longo_do_tempo(consolidado(pf)).set_index('bloco')

    assert tabela.loc['geral', 'percentual_bruta'] == 50.0
    assert tabela.loc['especifico', 'percentual_bruta'] == 100.0
    assert set(zscore_por_disciplina(consolidado(pf))['bloco']) == {'geral', 'especifico'}


def test_zscore_escala_pelo_n_da_disciplina():
    tcu = concurso(
        'tcu', ['acerto'] * 4 + ['acerto', 'erro', 'erro', 'erro'], ordem=1, disciplinas=[PT] * 4 + [TI] * 4
    )

    tabela = zscore_por_disciplina(consolidado(tcu)).set_index('disciplina')

    desvio = math.sqrt(1 - 0.25**2)
    assert tabela.loc[PT, 'zscore'] == pytest.approx((1 - 0.25) / (desvio / 2))
    assert tabela.loc[TI, 'zscore'] == pytest.approx((-0.5 - 0.25) / (desvio / 2))
    assert tabela.loc[PT, ['n', 'percentual']].tolist() == [4, 100.0]


def test_zscore_igual_entre_bruta_e_ajustada_na_fgv_sem_brancos():
    fgv = concurso(
        'fgv',
        ['acerto', 'erro', 'acerto', 'erro', 'erro', 'acerto'],
        formato='multipla_escolha',
        disciplinas=[PT] * 3 + [TI] * 3,
    )

    bruta = zscore_por_disciplina(consolidado(fgv), usar='bruta')['zscore']
    ajustada = zscore_por_disciplina(consolidado(fgv), usar='ajustada')['zscore']

    assert bruta.tolist() == pytest.approx(ajustada.tolist())


def test_zscore_muda_com_a_versao_quando_ha_brancos_na_cebraspe():
    tcu = concurso(
        'tcu', ['acerto', 'branco', 'branco', 'erro', 'erro', 'acerto'], disciplinas=[PT] * 3 + [TI] * 3
    )

    bruta = zscore_por_disciplina(consolidado(tcu), usar='bruta').set_index('disciplina')['zscore']
    corrigida = zscore_por_disciplina(consolidado(tcu), usar='corrigida').set_index('disciplina')['zscore']

    assert bruta[PT] == pytest.approx(0.0)
    assert corrigida[PT] > 0


def test_versao_invalida_falha():
    with pytest.raises(ValueError, match="usar: 'liquida' inválido"):
        zscore_por_disciplina(consolidado(concurso('tcu', ['acerto'])), usar='liquida')


def melhorando(nome: str, ordem: int, acertos_ti: int, banca: str | None = None) -> pd.DataFrame:
    return concurso(
        nome,
        ['acerto', 'erro'] * 3 + ['acerto'] * acertos_ti + ['erro'] * (6 - acertos_ti),
        ordem=ordem,
        disciplinas=[PT] * 6 + [TI] * 6,
        banca=banca,
    )


def test_tendencia_com_tres_pontos_ou_mais():
    base = consolidado(melhorando('a', 1, 2), melhorando('b', 2, 4), melhorando('c', 3, 6))

    tabela = tendencia_por_disciplina(base).set_index('disciplina')

    assert tabela.loc[TI, 'pontos'] == 3
    assert tabela.loc[TI, 'slope'] > 0
    assert tabela.loc[TI, 'situacao'] == 'tendência'
    assert 0 <= tabela.loc[TI, 'p_valor'] <= 1
    assert tabela.loc[TI, 'n'] == 18


def test_menos_de_tres_pontos_nao_gera_tendencia_e_concurso_sem_data_fica_fora():
    base = consolidado(melhorando('a', 1, 2), melhorando('b', 2, 4), melhorando('sem_data', None, 6))

    tabela = tendencia_por_disciplina(base).set_index('disciplina')

    assert tabela.loc[TI, 'pontos'] == 2
    assert tabela.loc[TI, 'situacao'] == 'amostra insuficiente'
    assert pd.isna(tabela.loc[TI, 'slope'])


def test_ponto_com_n_menor_que_5_nao_conta_para_a_tendencia():
    pequeno = concurso(
        'd', ['acerto'] * 6 + ['erro', 'erro', 'acerto'], ordem=4, disciplinas=[PT] * 6 + [TI] * 3
    )
    base = consolidado(melhorando('a', 1, 2), melhorando('b', 2, 4), pequeno)

    tabela = tendencia_por_disciplina(base).set_index('disciplina')

    assert tabela.loc[TI, ['pontos', 'n', 'situacao']].tolist() == [2, 12, 'amostra insuficiente']
    assert tabela.loc[PT, 'pontos'] == 3


def test_um_concurso_so_nao_gera_tendencia_nem_erro():
    base = consolidado(melhorando('a', 1, 2))

    assert tendencia_por_disciplina(base)['situacao'].unique().tolist() == ['amostra insuficiente']
    correlacao = correlacao_tempo_zscore(base)
    assert correlacao['rho'].isna().all()
    assert correlacao['pontos'].tolist() == [1, 1]


def test_sem_serie_valida_devolve_tabela_vazia_com_as_colunas():
    base = consolidado(melhorando('sem_data', None, 2))

    tendencia = tendencia_por_disciplina(base)
    correlacao = correlacao_tempo_zscore(base, estrato='banca')

    assert tendencia.empty
    assert {'disciplina', 'pontos', 'n', 'slope', 'p_valor', 'situacao'} <= set(tendencia.columns)
    assert correlacao.empty
    assert {'disciplina', 'banca', 'rho', 'p_valor'} <= set(correlacao.columns)


def test_topico_sem_gabarito_nao_gera_percentual_nem_quebra_as_series():
    anuladas = tuple(range(7, 13))
    base = consolidado(
        *(
            concurso(
                nome,
                ['acerto', 'erro'] * 3 + ['acerto'] * 6,
                ordem=ordem,
                anuladas=anuladas,
                disciplinas=[PT] * 6 + [TI] * 6,
            )
            for nome, ordem in (('a', 1), ('b', 2), ('c', 3))
        )
    )

    assert set(percentual_por_disciplina_ao_longo_do_tempo(base)['disciplina']) == {PT}
    assert set(zscore_por_disciplina(base)['disciplina']) == {PT}
    assert tendencia_por_disciplina(base)['disciplina'].tolist() == [PT]
    assert correlacao_tempo_zscore(base)['disciplina'].tolist() == [PT]


def test_estratificacao_por_banca_separa_as_series():
    base = consolidado(
        melhorando('a', 1, 2),
        melhorando('b', 3, 4),
        melhorando('c', 5, 6),
        melhorando('f1', 2, 1, banca='fgv'),
        melhorando('f2', 4, 5, banca='fgv'),
    )

    unica = tendencia_por_disciplina(base).set_index('disciplina')
    por_banca = tendencia_por_disciplina(base, estrato='banca').set_index(['disciplina', 'banca'])

    assert unica.loc[TI, 'pontos'] == 5
    assert por_banca.loc[(TI, 'cebraspe'), 'situacao'] == 'tendência'
    assert por_banca.loc[(TI, 'fgv'), 'situacao'] == 'amostra insuficiente'
    assert set(correlacao_tempo_zscore(base, estrato='banca')['banca']) == {'cebraspe', 'fgv'}


def test_correlacao_de_spearman_entre_ordem_e_zscore():
    base = consolidado(melhorando('a', 1, 2), melhorando('b', 2, 4), melhorando('c', 3, 6))

    tabela = correlacao_tempo_zscore(base).set_index('disciplina')

    assert tabela.loc[TI, 'rho'] == pytest.approx(1.0)
    assert tabela.loc[PT, 'rho'] == pytest.approx(-1.0)
    assert tabela.loc[TI, 'pontos'] == 3
    assert tabela.loc[TI, 'p_valor'] == pytest.approx(1 / 3)


def test_modelos_distintos():
    cebraspe = concurso('cebraspe', ['acerto'])
    fgv = concurso('fgv', ['acerto'], formato='multipla_escolha')

    assert modelos_distintos(consolidado(cebraspe, fgv)) == ['bruta', 'liquida']
    assert modelos_distintos(consolidado(cebraspe)) == ['liquida']
