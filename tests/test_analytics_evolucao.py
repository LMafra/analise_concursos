import math

import pandas as pd
import pytest
from consolidado_sintetico import concurso, consolidado

from concursos.analytics.evolucao import (
    cobertura_edital,
    comparar_bruto_vs_corrigido,
    comparar_com_meta,
    comparar_percentual_e_gap,
    correlacao_tempo_percentual,
    correlacao_tempo_zscore,
    evolucao_por_topico,
    gap_para_corte,
    gap_por_disciplina,
    modelos_distintos,
    nota_ponderada_por_disciplina,
    percentual_por_disciplina_ao_longo_do_tempo,
    percentual_por_topico,
    ranking_concursos_por_metrica,
    simular_cenario,
    tendencia_por_disciplina,
    topicos_fracos_persistentes,
    zscore_por_disciplina,
)


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


def por_topico(nome: str, ordem: int | None, itens: dict[str, list[str]], **kwargs) -> pd.DataFrame:
    """Concurso Cebraspe com os resultados de cada tópico de Português, na ordem do dicionário."""
    return concurso(
        nome,
        [resultado for resultados in itens.values() for resultado in resultados],
        ordem=ordem,
        topicos=[topico for topico, resultados in itens.items() for _ in resultados],
        **kwargs,
    )


def test_percentual_por_topico_com_contagens_e_amostra_insuficiente():
    a = por_topico(
        'a', 1, {'Crase': ['acerto', 'acerto', 'erro', 'branco', 'acerto'], 'Regência': ['erro'] * 2}
    )

    tabela = percentual_por_topico(consolidado(a)).set_index('topico')

    assert tabela.loc['Crase', ['n', 'acertos', 'erros', 'brancos', 'amostra_insuficiente']].tolist() == [
        5,
        3,
        1,
        1,
        False,
    ]
    assert tabela.loc['Crase', 'percentual'] == pytest.approx(40.0)
    assert tabela.loc['Regência', ['n', 'amostra_insuficiente', 'percentual']].tolist() == [2, True, -100.0]
    assert tabela.loc['Crase', ['concurso', 'ordem', 'disciplina', 'chave_topico']].tolist() == [
        'a',
        1,
        PT,
        f'{PT} | Crase',
    ]


def test_percentual_por_topico_filtra_por_quantidade_de_concursos():
    base = consolidado(
        por_topico('a', 1, {'Crase': ['acerto'], 'Regência': ['acerto']}),
        por_topico('b', 2, {'Crase': ['erro']}),
    )

    assert set(percentual_por_topico(base)['topico']) == {'Crase', 'Regência'}
    assert percentual_por_topico(base, min_concursos=2)['topico'].tolist() == ['Crase', 'Crase']


def test_cobertura_conta_topicos_do_edital_cobrados_e_os_fora_do_edital():
    base = consolidado(
        por_topico('a', 1, {'crase': ['acerto'], 'Regência verbal': ['erro'], 'Pontuação': ['acerto']}),
        por_topico('b', 2, {'Crase': ['acerto'], 'nao_mapeado': ['erro']}),
    )
    edital = pd.DataFrame(
        {
            'concurso': ['a'] * 5,
            'disciplina': [PT] * 4 + ['Redação'],
            'topico': ['Crase.', 'Regência verbal', 'Concordância', 'Crase', 'Concordância'],
        }
    )

    tabela = cobertura_edital(base, edital).set_index('concurso')

    assert tabela.loc['a', ['topicos_edital', 'topicos_cobrados', 'topicos_fora_do_edital']].tolist() == [
        3,
        2,
        1,
    ]
    assert tabela.loc['a', 'percentual_cobertura'] == pytest.approx(200 / 3)
    assert tabela.loc['b', ['topicos_edital', 'topicos_cobrados', 'topicos_fora_do_edital']].tolist() == [
        0,
        0,
        1,
    ]
    assert pd.isna(tabela.loc['b', 'percentual_cobertura'])
    assert 'Concordância' not in set(evolucao_por_topico(base)['topico'])


def test_evolucao_por_topico_so_com_tres_pontos_de_n_minimo():
    base = consolidado(
        *(
            por_topico(
                nome,
                ordem,
                {
                    'Crase': ['acerto'] * acertos + ['erro'] * (5 - acertos),
                    'Regência': ['acerto', 'erro', 'erro', 'acerto'],
                    **({'Pontuação': ['acerto'] * 5} if ordem < 3 else {}),
                    **({'Concordância': ['erro'] * 5} if ordem == 1 else {}),
                },
            )
            for nome, ordem, acertos in (('a', 1, 2), ('b', 2, 3), ('c', 3, 5))
        )
    )

    tabela = evolucao_por_topico(base).set_index('topico')

    assert tabela.loc['Crase', ['pontos', 'n', 'situacao']].tolist() == [3, 15, 'tendência']
    assert tabela.loc['Crase', 'slope'] > 0
    assert 0 <= tabela.loc['Crase', 'p_valor'] <= 1
    assert tabela.loc['Regência', ['pontos', 'n', 'n_total']].tolist() == [0, 0, 12]
    assert tabela.loc['Crase', 'n_total'] == 15
    assert tabela.loc['Pontuação', 'pontos'] == 2
    assert tabela.loc['Concordância', 'pontos'] == 1
    insuficientes = tabela.loc[['Regência', 'Pontuação', 'Concordância']]
    assert insuficientes['situacao'].eq('amostra insuficiente').all()
    assert insuficientes['slope'].isna().all()
    assert evolucao_por_topico(base, min_n=4).set_index('topico').loc['Regência', 'situacao'] == 'tendência'


def test_evolucao_por_topico_estratificada_por_banca():
    base = consolidado(
        *(
            por_topico(nome, ordem, {'Crase': ['acerto'] * acertos + ['erro'] * (5 - acertos)}, banca=banca)
            for nome, ordem, acertos, banca in (
                ('a', 1, 1, 'cebraspe'),
                ('b', 2, 3, 'cebraspe'),
                ('c', 3, 5, 'cebraspe'),
                ('f', 4, 0, 'fgv'),
            )
        )
    )

    tabela = evolucao_por_topico(base, estrato='banca').set_index('banca')

    assert tabela.loc['cebraspe', ['pontos', 'situacao']].tolist() == [3, 'tendência']
    assert tabela.loc['fgv', ['pontos', 'situacao']].tolist() == [1, 'amostra insuficiente']


def test_fracos_persistentes_somam_entre_concursos_e_exigem_dois_concursos():
    base = consolidado(
        por_topico(
            'a',
            1,
            {'Crase': ['acerto', 'erro', 'erro'], 'Regência': ['erro'] * 3, 'Pontuação': ['erro'] * 2},
        ),
        por_topico(
            'b',
            2,
            {'Crase': ['acerto', 'acerto', 'erro'], 'Regência': ['acerto'] * 3, 'Pontuação': ['erro'] * 2},
        ),
    )

    tabela = topicos_fracos_persistentes(base).set_index('topico')

    assert tabela.index.tolist() == ['Crase']
    assert tabela.loc['Crase', ['concursos', 'n', 'acertos', 'erros', 'brancos']].tolist() == [2, 6, 3, 3, 0]
    assert tabela.loc['Crase', 'percentual'] == pytest.approx(0.0)
    assert tabela.loc['Crase', 'concursos_abaixo'] == ['a', 'b']
    assert 'Regência' in set(topicos_fracos_persistentes(base, min_concursos=1)['topico'])


def test_topico_em_geral_e_especifico_do_mesmo_concurso_conta_uma_vez():
    itens = ['erro'] * 3
    a = concurso('a', itens, ordem=1, blocos=['geral', 'geral', 'especifico'])
    b = concurso('b', itens, ordem=2)

    assert percentual_por_topico(consolidado(a))['n'].tolist() == [3]
    assert topicos_fracos_persistentes(consolidado(a), min_n=1).empty
    assert topicos_fracos_persistentes(consolidado(a, b))['concursos_abaixo'].tolist() == [['a', 'b']]


def test_fracos_persistentes_pela_correcao_liquida_e_nao_pela_bruta():
    itens = {'Crase': ['acerto'] * 3 + ['erro'] * 2}
    base = consolidado(por_topico('a', 1, itens), por_topico('b', 2, itens))

    assert topicos_fracos_persistentes(base, usar='bruta').empty
    assert topicos_fracos_persistentes(base, usar='corrigida')['topico'].tolist() == ['Crase']


def test_topico_sem_gabarito_fica_fora_das_metricas_mas_conta_como_cobrado():
    base = consolidado(
        *(
            por_topico(
                nome, ordem, {'Crase': ['acerto'] * 5, 'Regência': ['erro'] * 5}, anuladas=(6, 7, 8, 9, 10)
            )
            for nome, ordem in (('a', 1), ('b', 2), ('c', 3))
        )
    )
    edital = pd.DataFrame({'concurso': ['a', 'a'], 'disciplina': [PT, PT], 'topico': ['Crase', 'Regência']})

    assert set(percentual_por_topico(base)['topico']) == {'Crase'}
    assert evolucao_por_topico(base)['topico'].tolist() == ['Crase']
    assert topicos_fracos_persistentes(base, limiar=1.1)['topico'].tolist() == ['Crase']
    assert cobertura_edital(base, edital).set_index('concurso').loc['a', 'topicos_cobrados'] == 2


def test_um_concurso_so_nas_metricas_por_disciplina_e_por_topico():
    base = consolidado(por_topico('a', 1, {'Crase': ['erro'] * 5, 'Regência': ['acerto', 'erro']}))

    assert percentual_por_disciplina_ao_longo_do_tempo(base)['n'].tolist() == [7]
    assert zscore_por_disciplina(base)['zscore'].tolist() == [pytest.approx(0.0)]
    assert percentual_por_topico(base).set_index('topico')['n'].to_dict() == {'Crase': 5, 'Regência': 2}
    assert percentual_por_topico(base, min_concursos=2).empty
    assert evolucao_por_topico(base)['situacao'].eq('amostra insuficiente').all()
    assert topicos_fracos_persistentes(base).empty


def test_meta_por_variante_com_os_pesos_da_variante():
    cpnu = concurso(
        'cpnu',
        ['acerto', 'acerto', 'erro', 'erro'],
        formato='multipla_escolha',
        pesos={'v1': [1.0, 1.0, 2.0, 2.0], 'v2': [2.0, 2.0, 1.0, 1.0]},
        ordem=1,
    ).assign(nota_maxima=6.0)

    tabela = comparar_com_meta(consolidado(cpnu), meta=0.6).set_index('variante')

    assert tabela.loc['v1', ['nota', 'nota_maxima']].tolist() == [2.0, 6.0]
    assert tabela.loc['v1', 'nota_normalizada'] == pytest.approx(100 / 3)
    assert tabela.loc['v2', 'nota_normalizada'] == pytest.approx(200 / 3)
    assert tabela.loc['v1', 'distancia'] == pytest.approx(100 / 3 - 60)
    assert tabela.loc['v2', 'distancia'] == pytest.approx(200 / 3 - 60)
    assert tabela['atingiu'].tolist() == [False, True]
    assert tabela['meta'].tolist() == [60.0, 60.0]


def test_meta_com_nota_truncada_em_zero_e_anulada_valendo_ponto():
    tcu = concurso('tcu', ['erro', 'erro', 'erro', 'acerto'], ordem=1)
    pf = concurso('pf', ['acerto', 'acerto', 'erro', 'erro'], anuladas=(3,), ordem=2)

    tabela = comparar_com_meta(consolidado(tcu, pf)).set_index('concurso')

    assert tabela.loc['tcu', ['nota', 'nota_normalizada', 'distancia']].tolist() == [-2.0, 0.0, -70.0]
    assert tabela.loc['pf', ['nota', 'nota_normalizada']].tolist() == [2.0, 50.0]
    assert tabela.index.tolist() == ['tcu', 'pf']


def test_meta_com_um_concurso_so():
    tabela = comparar_com_meta(consolidado(concurso('tcu', ['acerto'] * 3 + ['erro'])))

    assert len(tabela) == 1
    assert pd.isna(tabela.loc[0, 'variante'])
    assert tabela.loc[0, 'nota_normalizada'] == 50.0
    assert pd.isna(tabela.loc[0, 'nota_corte'])
    com_corte = comparar_com_meta(consolidado(concurso('tcu', ['acerto'] * 3 + ['erro'], nota_corte=1.5)))
    assert com_corte.loc[0, 'nota_corte'] == 1.5


def test_correlacao_entre_a_ordem_e_o_percentual_de_cada_concurso():
    base = consolidado(
        concurso('a', ['acerto', 'erro', 'erro', 'erro'], ordem=1),
        concurso('b', ['acerto', 'acerto', 'erro', 'erro'], ordem=2),
        concurso('c', ['acerto', 'acerto', 'acerto', 'erro'], ordem=3),
        concurso('sem_data', ['erro'] * 4),
    )

    correlacao = correlacao_tempo_percentual(base)

    assert correlacao.rho == pytest.approx(1.0)
    assert correlacao.p_valor == pytest.approx(1 / 3)
    assert correlacao.pontos == 3
    assert math.isnan(correlacao_tempo_percentual(consolidado(concurso('a', ['acerto'], ordem=1))).rho)


def test_nota_ponderada_vale_o_peso_do_acerto_sem_desconto_e_a_anulada_conta():
    cpnu = concurso(
        'cpnu',
        ['acerto', 'erro', 'acerto', 'branco', 'erro'],
        formato='multipla_escolha',
        anuladas=(5,),
        pesos={'B3-08-A': [1.0, 2.0, 0.5, 2.0, 1.0]},
        disciplinas=['Dados'] * 4 + ['Português'],
    )

    tabela = nota_ponderada_por_disciplina(consolidado(cpnu)).set_index('disciplina')

    dados = tabela.loc['Dados']
    assert (dados['variante'], dados['n'], dados['nota_ponderada'], dados['nota_maxima']) == (
        'B3-08-A',
        4,
        1.5,
        5.5,
    )
    assert dados['percentual_ponderado'] == pytest.approx(100 * 1.5 / 5.5)
    assert (tabela.loc['Português', 'nota_ponderada'], tabela.loc['Português', 'nota_maxima']) == (1.0, 1.0)


def corte(escopo: str, valor: float, unidade: str = 'pontos', bloco: str | None = None) -> dict:
    return {'escopo': escopo, 'valor': valor, 'unidade': unidade, 'bloco': bloco}


def cebraspe(geral: list[str], especifico: list[str]) -> pd.DataFrame:
    return concurso(
        'cd_25',
        geral + especifico,
        blocos=['geral'] * len(geral) + ['especifico'] * len(especifico),
        disciplinas=['Português'] * len(geral) + ['Dados'] * len(especifico),
    )


CORTES_CEBRASPE = [corte('geral', 3), corte('especifico', 2), corte('conjunto', 4), corte('discursiva', 30)]


def test_bloco_abaixo_do_corte_nao_atinge_mesmo_com_o_conjunto_acima():
    prova = cebraspe(['acerto', 'acerto', 'erro', 'branco'], ['acerto'] * 4)

    tabela = gap_para_corte(consolidado(prova), {'cd_25': CORTES_CEBRASPE}).set_index('escopo')

    assert list(tabela.index) == ['geral', 'especifico', 'conjunto']
    geral = tabela.loc['geral']
    assert (geral['nota'], geral['corte'], geral['gap'], geral['nota_maxima']) == (1.0, 3.0, -2.0, 4.0)
    assert geral['gap_percentual'] == -50.0
    assert (geral['unidade'], geral['satisfeito']) == ('pontos', False)
    assert (tabela.loc['conjunto', 'nota'], tabela.loc['conjunto', 'satisfeito']) == (5.0, True)
    assert not tabela['atingido'].any()


def test_atingido_so_com_todos_os_cortes_satisfeitos():
    prova = cebraspe(['acerto', 'acerto', 'acerto', 'branco'], ['acerto', 'acerto', 'erro', 'acerto'])

    tabela = gap_para_corte(consolidado(prova), {'cd_25': CORTES_CEBRASPE})

    assert tabela['satisfeito'].all()
    assert tabela['atingido'].all()


def test_disciplina_zerada_nao_atinge_mesmo_com_o_conjunto_acima():
    agsus = concurso(
        'agsus',
        ['acerto'] * 4 + ['erro', 'branco'],
        formato='multipla_escolha',
        disciplinas=['Português'] * 4 + ['Informática'] * 2,
    )
    cortes = [corte('conjunto', 3, 'acertos'), corte('disciplina', 1, 'acertos')]

    tabela = gap_para_corte(consolidado(agsus), {'agsus': cortes})

    por_disciplina = tabela[tabela['escopo'] == 'disciplina'].set_index('disciplina')
    assert por_disciplina['satisfeito'].to_dict() == {'Informática': False, 'Português': True}
    assert (por_disciplina.loc['Informática', 'gap'], por_disciplina.loc['Informática', 'nota_maxima']) == (
        -1,
        2,
    )
    assert tabela.loc[tabela['escopo'] == 'conjunto', 'satisfeito'].item()
    assert not tabela['atingido'].any()


def test_no_corte_em_acertos_a_anulada_conta_como_acerto():
    fgv = concurso('cprm', ['acerto', 'acerto', 'erro', 'erro'], formato='multipla_escolha', anuladas=(3,))

    [linha] = gap_para_corte(consolidado(fgv), {'cprm': [corte('conjunto', 3, 'acertos')]}).to_dict('records')

    assert (linha['nota'], linha['gap'], linha['satisfeito'], linha['atingido']) == (3, 0, True, True)


def test_sem_concurso_alvo_saem_todos_e_com_ele_so_o_alvo():
    dois = consolidado(
        cebraspe(['acerto'] * 4, ['acerto'] * 4), concurso('tcu', ['acerto', 'erro', 'acerto', 'acerto'])
    )
    cortes = {'cd_25': [corte('conjunto', 4)], 'tcu': [corte('conjunto', 2)]}

    assert set(gap_para_corte(dois, cortes)['concurso']) == {'cd_25', 'tcu'}
    assert set(gap_para_corte(dois, cortes, concurso_alvo='tcu')['concurso']) == {'tcu'}
    assert set(nota_ponderada_por_disciplina(dois)['concurso']) == {'cd_25', 'tcu'}
    assert set(nota_ponderada_por_disciplina(dois, concurso_alvo='tcu')['concurso']) == {'tcu'}


def test_ranking_entre_bruto_corrigido_e_ponderado_confere_com_o_calculo_a_mao():
    liquida = concurso('a', ['acerto'] * 7 + ['erro'] * 3)
    bruta = concurso('b', ['acerto'] * 6 + ['erro'] * 4, formato='multipla_escolha')
    ponderada = concurso(
        'c',
        ['acerto', 'acerto', 'erro', 'erro'],
        formato='multipla_escolha',
        pesos={'padrao': [2.0, 2.0, 1.0, 1.0]},
    )

    tabela = ranking_concursos_por_metrica(consolidado(liquida, bruta, ponderada)).set_index('concurso')

    assert tabela.loc['a', ['percentual_bruto', 'percentual_corrigido', 'percentual_ponderado']].tolist() == [
        70.0,
        40.0,
        70.0,
    ]
    assert tabela.loc['c', 'percentual_ponderado'] == pytest.approx(100 * 4 / 6)
    assert tabela['posicao_bruto'].to_dict() == {'a': 1, 'b': 2, 'c': 3}
    assert tabela['posicao_corrigido'].to_dict() == {'a': 3, 'b': 2, 'c': 1}
    assert tabela['posicao_ponderado'].to_dict() == {'a': 1, 'b': 3, 'c': 2}
    assert tabela['deslocamento_corrigido'].to_dict() == {'a': -2, 'b': 0, 'c': 2}
    assert tabela['deslocamento_ponderado'].to_dict() == {'a': 0, 'b': -1, 'c': 1}


def test_simulacao_converte_erros_e_brancos_na_proporcao_e_muda_nota_e_gap():
    prova = concurso(
        'cd_25',
        ['acerto'] * 5 + ['erro'] * 3 + ['branco'] * 2 + ['acerto'] * 2,
        disciplinas=['Dados'] * 10 + ['Português'] * 2,
    )
    cortes = {'cd_25': [corte('conjunto', 8)]}

    [linha] = simular_cenario(consolidado(prova), cortes, 'Dados', 20).to_dict('records')

    assert (linha['itens_convertidos'], linha['erros_convertidos'], linha['brancos_convertidos']) == (2, 1, 1)
    assert (linha['nota_atual'], linha['nota_estimada']) == (4.0, 7.0)
    assert (linha['gap_atual'], linha['gap_estimado']) == (-4.0, -1.0)
    assert (linha['atingido_atual'], linha['atingido_estimado']) == (False, False)
    assert linha['natureza'] == 'estimativa'


def test_simulacao_nao_converte_mais_itens_do_que_os_que_nao_sao_acerto():
    prova = concurso('cd_25', ['acerto'] * 9 + ['erro'], disciplinas=['Dados'] * 10)

    [linha] = simular_cenario(consolidado(prova), {'cd_25': [corte('conjunto', 9)]}, 'Dados', 50).to_dict(
        'records'
    )

    assert (linha['itens_convertidos'], linha['nota_estimada'], linha['atingido_estimado']) == (1, 10.0, True)


def test_gap_por_disciplina_usa_o_corte_que_mais_aperta_cada_disciplina():
    prova = concurso(
        'cd_25',
        ['acerto', 'acerto', 'acerto', 'erro'] + ['acerto', 'branco', 'branco', 'branco'],
        blocos=['geral'] * 4 + ['especifico'] * 4,
        disciplinas=['Português'] * 4 + ['Dados'] * 4,
    )
    cortes = [corte('conjunto', 2), corte('especifico', 2)]

    tabela = gap_por_disciplina(consolidado(prova), {'cd_25': cortes}).set_index('disciplina')

    portugues, dados = tabela.loc['Português'], tabela.loc['Dados']
    assert (portugues['corte_escopo'], portugues['percentual'], portugues['exigido']) == (
        'conjunto',
        50.0,
        25.0,
    )
    assert (portugues['gap_percentual'], portugues['falta'], portugues['atingido']) == (25.0, 0.0, True)
    assert (dados['corte_escopo'], dados['percentual'], dados['exigido']) == ('especifico', 25.0, 50.0)
    assert (dados['gap_percentual'], dados['falta'], dados['atingido']) == (-25.0, 1.0, False)
    assert not tabela['amostra_suficiente'].any()
    assert list(tabela.index) == ['Dados', 'Português']


def test_comparacao_lado_a_lado_traz_bruto_ponderado_e_o_gap_mais_distante():
    prova = cebraspe(['acerto', 'acerto', 'erro', 'branco'], ['acerto'] * 4)

    [linha] = comparar_percentual_e_gap(consolidado(prova), {'cd_25': CORTES_CEBRASPE}).to_dict('records')

    assert (linha['percentual_bruto'], linha['percentual_ponderado']) == (75.0, 75.0)
    assert (linha['menor_gap_percentual'], linha['corte_mais_distante'], linha['atingido']) == (
        -50.0,
        'geral',
        False,
    )
