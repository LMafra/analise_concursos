import logging
from pathlib import Path

import pandas as pd
import pytest
from conftest import log_completo
from consolidado_sintetico import concurso, consolidado
from editais_bancas import (
    CVM_2024,
    EMPARN_2025,
    FORTALEZA_2023,
    MPPI_2025,
    PC_PE_2023,
    PF_2025,
    STN_2024,
    TJSP_2023,
    TRF5_2024,
    TRT6_2024,
    TSE_2024,
)

from concursos.analytics.consolidado import SchemaInvalidoError, avisos_do_consolidado, validar_schema
from concursos.analytics.correcao import FonteCorrecao, extrair_fator_correcao, resolver_correcao
from concursos.analytics.evolucao import gap_para_corte, gap_por_disciplina
from concursos.analytics.insights import peculiaridades_do_edital
from concursos.analytics.regras_edital import FonteRegra, TipoPeso, UnidadeCorte, extrair_regras
from concursos.concurso_config import PesoItens, validar_dados
from concursos.deteccao import detectar_banca
from concursos.perfis import ids_de_banca, perfil_da_banca


def config(banca: str, formato: str = 'multipla_escolha', total: int = 100, **extra):
    dados = {
        'banca': banca,
        'formato': formato,
        'provas': {'unica': {'gabarito': 'g.txt', 'itens': [1, total]}},
        **extra,
    }
    return validar_dados(Path('sintetico'), dados)


ME, CE = 'multipla_escolha', 'certo_errado'
NAO_CALCULAVEL = None

# edital, banca, formato do concurso, total de itens, formato, alternativas, penalidade (valor, fonte), tipo de
# peso, cortes (escopo, unidade, valor)
EDITAIS = {
    'PF 2025': (
        PF_2025,
        'cebraspe',
        CE,
        120,
        CE,
        None,
        (1.0, 'edital'),
        TipoPeso.UNIFORME,
        {
            ('geral', 'pontos', 10.0),
            ('especifico', 'pontos', 21.0),
            ('conjunto', 'pontos', 48.0),
            ('conjunto', 'classificados', NAO_CALCULAVEL),
        },
    ),
    'TSE 2024': (
        TSE_2024,
        'cebraspe',
        CE,
        120,
        CE,
        None,
        (1.0, 'edital'),
        TipoPeso.POR_BLOCO,
        {('geral', 'pontos', 10.0), ('especifico', 'pontos', 40.0), ('conjunto', 'pontos', 55.0)},
    ),
    'PC-PE 2023': (
        PC_PE_2023,
        'cebraspe',
        ME,
        100,
        ME,
        5,
        (0.0, 'edital'),
        TipoPeso.UNIFORME,
        {('conjunto', 'pontos', 24.0)},
    ),
    'STN 2024': (
        STN_2024,
        'fgv',
        ME,
        110,
        ME,
        5,
        (0.0, 'perfil'),
        TipoPeso.POR_BLOCO,
        {('conjunto', 'pontos', 95.0)},
    ),
    'CVM 2024': (
        CVM_2024,
        'fgv',
        ME,
        110,
        ME,
        5,
        (0.0, 'edital'),
        TipoPeso.UNIFORME,
        {('geral', 'acertos', 16.0), ('especifico', 'acertos', 28.0)},
    ),
    'TRT-6 2024': (
        TRT6_2024,
        'fcc',
        ME,
        90,
        ME,
        5,
        (0.0, 'perfil'),
        TipoPeso.POR_BLOCO,
        {('conjunto', 'nota_0_10', 6.0)},
    ),
    'MP-PI 2025': (
        MPPI_2025,
        'fcc',
        ME,
        90,
        ME,
        5,
        (0.0, 'perfil'),
        None,
        {('conjunto', 'escore_padronizado', 150.0)},
    ),
    'TJSP 2023': (
        TJSP_2023,
        'vunesp',
        ME,
        100,
        ME,
        5,
        (0.0, 'perfil'),
        None,
        {('geral', 'percentual', 50.0), ('especifico', 'percentual', 50.0)},
    ),
    'TRF-5 2024': (
        TRF5_2024,
        'ibfc',
        ME,
        60,
        ME,
        4,
        (0.0, 'perfil'),
        TipoPeso.POR_BLOCO,
        {('geral', 'pontos', 1.2), ('especifico', 'pontos', 4.8)},
    ),
    'Fortaleza 2023': (
        FORTALEZA_2023,
        'idecan',
        ME,
        80,
        ME,
        4,
        (0.0, 'edital'),
        TipoPeso.POR_BLOCO,
        {('conjunto', 'percentual', 50.0), ('disciplina', 'acertos', 1.0)},
    ),
    'EMPARN 2025': (
        EMPARN_2025,
        'idecan',
        ME,
        50,
        ME,
        5,
        (0.0, 'perfil'),
        TipoPeso.POR_BLOCO,
        {('conjunto', 'percentual', 60.0), ('disciplina', 'acertos', 1.0)},
    ),
}


@pytest.mark.parametrize('nome', list(EDITAIS))
def test_trecho_do_edital_de_cada_banca_da_as_regras_esperadas(nome):
    texto, banca, formato, total, esperado, alternativas, penalidade, peso, cortes = EDITAIS[nome]

    regras = extrair_regras(config(banca, formato, total), {'edital.pdf': [texto]})

    assert (regras.prova.formato.valor, regras.prova.formato.fonte) == (esperado, FonteRegra.EDITAL)
    assert regras.prova.alternativas.valor == alternativas
    assert (regras.prova.penalidade.valor, regras.prova.penalidade.fonte) == penalidade
    assert regras.pesos.tipo.valor == peso
    assert {(c.escopo, c.unidade, c.valor) for c in regras.cortes} == cortes


def test_pesos_por_parte_com_o_numero_de_questoes_viram_faixas():
    stn = extrair_regras(config('fgv', ME, 110), {'edital.pdf': [STN_2024]})
    trf5 = extrair_regras(config('ibfc', ME, 60), {'edital.pdf': [TRF5_2024]})

    assert stn.pesos.faixas[''].valor == (PesoItens(1, 40, 1.25), PesoItens(41, 110, 2.0))
    assert trf5.pesos.faixas[''].valor == (PesoItens(1, 20, 0.1), PesoItens(21, 60, 0.2))


def test_edital_cebraspe_de_multipla_escolha_vence_o_perfil_e_fica_sem_penalidade():
    assert perfil_da_banca('cebraspe').penalidade == 1.0
    cfg = config('cebraspe', ME, 100)

    [correcao] = resolver_correcao(cfg, {'edital.pdf': [PC_PE_2023]})

    assert extrair_fator_correcao([PC_PE_2023]).fator_penalidade == 0.0
    assert (correcao.fator_penalidade, correcao.fonte) == (0.0, FonteCorrecao.EDITAL)


def test_campo_ausente_no_edital_e_na_configuracao_vem_do_perfil_com_confianca_menor(caplog):
    cfg = config('cebraspe', CE, 120)

    with caplog.at_level(logging.WARNING):
        [correcao] = resolver_correcao(cfg, {'edital.pdf': ['Edital sem regra de correção.']})
    regras = extrair_regras(cfg, {'edital.pdf': ['Edital sem regra de correção.']})

    assert (correcao.fator_penalidade, correcao.fonte) == (1.0, FonteCorrecao.PERFIL)
    assert 0 < correcao.confianca < 0.9
    assert 'perfil da banca cebraspe' in log_completo(caplog)
    penalidade = regras.prova.penalidade
    assert (penalidade.valor, penalidade.fonte) == (1.0, FonteRegra.PERFIL)
    assert 0 < penalidade.confianca_extracao < 0.9
    assert regras.prova.formato.fonte == FonteRegra.CONFIG


def test_perfil_de_outro_formato_nao_preenche_a_penalidade():
    cfg = config('cebraspe', ME, 100)

    [correcao] = resolver_correcao(cfg, {'edital.pdf': ['Edital sem regra de correção.']})
    regras = extrair_regras(cfg, {'edital.pdf': ['Edital sem regra de correção.']})

    assert (correcao.fator_penalidade, correcao.fonte) == (0.0, FonteCorrecao.DEFAULT)
    assert (regras.prova.penalidade.valor, regras.prova.penalidade.fonte) == (0.0, FonteRegra.DEFAULT)
    assert (regras.prova.alternativas.valor, regras.prova.alternativas.fonte) == (5, FonteRegra.DEFAULT)


def test_alternativas_da_configuracao_vencem_o_perfil():
    regras = extrair_regras(config('idecan', ME, 80, alternativas=4), {'edital.pdf': ['Sem regras.']})

    assert (regras.prova.alternativas.valor, regras.prova.alternativas.fonte) == (4, FonteRegra.CONFIG)


def test_fonte_perfil_aparece_no_parquet_e_nos_avisos():
    tabela = concurso('x', ['acerto', 'erro'])
    tabela['fonte_correcao'] = FonteCorrecao.PERFIL.value
    tabela['confianca_correcao'] = 0.5
    tabela['data_prova'] = pd.Timestamp('2025-01-01')

    with pytest.raises(SchemaInvalidoError) as erro:
        validar_schema(tabela, 2)

    assert 'fonte_correcao' not in str(erro.value)
    [aviso] = avisos_do_consolidado(tabela).query("tipo == 'correcao'").to_dict('records')
    assert 'perfil da banca' in aviso['aviso']


def test_corte_nao_calculavel_fica_fora_do_atingido_e_aparece_com_aviso():
    prova = concurso('pf', ['acerto'] * 3 + ['erro'])
    cortes = {
        'pf': [
            {'escopo': 'conjunto', 'valor': 2, 'unidade': 'pontos', 'bloco': None},
            {'escopo': 'conjunto', 'valor': None, 'unidade': 'classificados', 'bloco': None},
            {'escopo': 'conjunto', 'valor': 150, 'unidade': 'escore_padronizado', 'bloco': None},
        ]
    }

    tabela = gap_para_corte(consolidado(prova), cortes)
    regras = extrair_regras(config('cebraspe', CE, 120), {'edital.pdf': [PF_2025]})
    peculiaridades = peculiaridades_do_edital({'pf': {'cortes': cortes['pf'], 'metadados': []}})

    assert list(tabela['unidade']) == ['pontos']
    assert tabela['atingido'].all()
    assert gap_por_disciplina(consolidado(prova), cortes)['unidade'].tolist() == ['pontos']
    assert not UnidadeCorte.CLASSIFICADOS.calculavel and not UnidadeCorte.ESCORE_PADRONIZADO.calculavel
    assert any('não calculável' in aviso for aviso in regras.avisos)
    nao_calculaveis = peculiaridades[peculiaridades['peculiaridade'] == 'Corte não calculável']
    assert len(nao_calculaveis) == 2
    assert nao_calculaveis['uso'].str.contains('fora do "atingido"').all()


def test_nao_zerar_disciplina_reprova_o_atingido():
    regras = extrair_regras(config('idecan', ME, 80), {'edital.pdf': [FORTALEZA_2023]})
    cortes = [vars(c) | {'escopo': str(c.escopo), 'unidade': str(c.unidade)} for c in regras.cortes]
    prova = concurso(
        'fortaleza',
        ['acerto'] * 8 + ['erro', 'branco'],
        formato=ME,
        disciplinas=['Português'] * 8 + ['Informática'] * 2,
    )

    tabela = gap_para_corte(consolidado(prova), {'fortaleza': cortes})

    conjunto = tabela[tabela['escopo'] == 'conjunto'].iloc[0]
    assert (conjunto['unidade'], conjunto['nota'], conjunto['nota_maxima']) == ('percentual', 80.0, 100.0)
    assert conjunto['satisfeito']
    zerada = tabela[(tabela['escopo'] == 'disciplina') & (tabela['disciplina'] == 'Informática')].iloc[0]
    assert not zerada['satisfeito']
    assert not tabela['atingido'].any()


def test_nota_de_0_a_10_e_percentual_sao_calculados_na_escala_do_corte():
    prova = concurso('trt6', ['acerto'] * 6 + ['erro'] * 4, formato=ME)
    cortes = {
        'trt6': [
            {'escopo': 'conjunto', 'valor': 6.0, 'unidade': 'nota_0_10', 'bloco': None},
            {'escopo': 'geral', 'valor': 70.0, 'unidade': 'percentual', 'bloco': None},
        ]
    }

    tabela = gap_para_corte(consolidado(prova), cortes).set_index('unidade')
    exigencia = gap_por_disciplina(consolidado(prova), cortes)

    assert (tabela.loc['nota_0_10', 'nota'], tabela.loc['nota_0_10', 'gap']) == (6.0, 0.0)
    assert (tabela.loc['percentual', 'nota'], tabela.loc['percentual', 'gap']) == (60.0, -10.0)
    assert exigencia['exigido'].max() == 70.0


def test_bancas_novas_sao_detectadas_e_generic_nunca():
    assert {'fcc', 'vunesp', 'ibfc', 'idecan', 'generic'} <= set(ids_de_banca())
    assert detectar_banca('CONCURSO PÚBLICO - FUNDAÇÃO CARLOS CHAGAS') == 'fcc'
    assert detectar_banca('Fundação VUNESP') == 'vunesp'
    assert detectar_banca('Instituto Brasileiro de Formação e Capacitação - IBFC') == 'ibfc'
    assert detectar_banca('IDECAN') == 'idecan'
    assert detectar_banca('Edital de uma banca qualquer') is None
    generic = perfil_da_banca('generic')
    assert (generic.formato, generic.alternativas, generic.penalidade) == (ME, 5, 0.0)
