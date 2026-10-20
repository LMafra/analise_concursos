import logging
from pathlib import Path

import pandas as pd
import pytest

from concursos.agregacao import agregar
from concursos.analytics.correcao import (
    ConfiguracaoCorrecao,
    FonteCorrecao,
    ModeloCorrecao,
    aplicar_correcao,
    extrair_fator_correcao,
    mencao_penalidade,
    nota_normalizada,
    resolver_correcao,
)
from concursos.concurso_config import validar_dados
from concursos.modelo import Formato, Pontuacao

CEBRASPE = """8.11 DOS CRITÉRIOS DE AVALIAÇÃO DAS PROVAS OBJETIVAS
8.11.1 As provas objetivas de todos os candidatos serão corrigidas por meio de processamento eletrônico
das folhas de respostas.
8.11.2 A nota em cada item das provas objetivas, feita com base nas marcações da folha de respostas, será
igual a: 1,00 ponto, caso a resposta do candidato esteja em concordância com o gabarito oficial definitivo das
provas; 1,00 ponto negativo, caso a resposta do candidato esteja em discordância com o gabarito oficial
definitivo das provas; 0,00 ponto, caso não haja marcação ou haja marcação dupla (C e E).
8.11.3 A nota em cada prova objetiva será igual à soma das notas obtidas em todos os itens que a compõem.
8.11.4 Será reprovado nas provas objetivas e eliminado do concurso público o candidato que se enquadrar
em pelo menos um dos itens a seguir:
a) obtiver nota inferior a 20,00 pontos na prova objetiva de conhecimentos básicos P ;
1
b) obtiver nota inferior a 30,00 pontos na prova objetiva de conhecimentos específicos P ;
2
c) obtiver nota inferior a 60,00 pontos no conjunto das provas objetivas.
"""


AGSUS = """9.5 A Prova Objetiva totalizará 70 (setenta) pontos e será composta por 70 (setenta) questões de múltipla escolha,
valendo 1 (um) ponto cada questão. As questões serão numeradas sequencialmente, contendo 5 (cinco) alternativas
cada e apenas uma resposta correta.
"""

CPRM = """12.15 Os candidatos aprovados na Prova Objetiva serão classificados em ordem decrescente de acertos
e terão Nota da Prova Objetiva (NPO) igual ao total de acertos.
Companhia de Pesquisa de Recursos Minerais | CONCURSO
27
PÚBLICO 2025
"""

PF_PERITO = """8.11.3 A nota na prova objetiva será igual à soma das notas obtidas em todos os itens que a compõem.
8.11.4 Será reprovado na prova objetiva e eliminado do concurso público o candidato ao cargo de
Delegado de Polícia Federal que obtiver nota inferior a 48,00 pontos na prova objetiva P .
1
"""


def test_cebraspe_ponto_negativo_e_liquida_com_fator_1_e_corte_do_conjunto():
    cfg = extrair_fator_correcao(['Capa do edital', CEBRASPE])

    assert cfg.modelo is ModeloCorrecao.LIQUIDA
    assert cfg.fator_penalidade == 1.0
    assert cfg.nota_corte == 60.0
    assert cfg.fonte is FonteCorrecao.EDITAL
    assert cfg.pagina_origem == 2
    assert cfg.trecho_origem.startswith('8.11.2 A nota em cada item')
    assert '1,00 ponto negativo' in cfg.trecho_origem
    assert cfg.confianca >= 0.9


def test_cebraspe_com_prova_unica_usa_o_corte_da_prova_objetiva():
    cfg = extrair_fator_correcao([CEBRASPE.split('8.11.3')[0] + PF_PERITO])

    assert cfg.nota_corte == 48.0


def test_fgv_valendo_1_ponto_cada_questao_e_bruta_com_nota_maxima():
    cfg = extrair_fator_correcao(['Capa', 'Inscrições', AGSUS])

    assert cfg.modelo is ModeloCorrecao.BRUTA
    assert cfg.fator_penalidade == 0.0
    assert cfg.nota_maxima == 70.0
    assert cfg.nota_corte is None
    assert cfg.fonte is FonteCorrecao.EDITAL
    assert cfg.pagina_origem == 3
    assert cfg.trecho_origem.startswith('9.5 A Prova Objetiva totalizará 70 (setenta) pontos')
    assert cfg.trecho_origem.endswith('valendo 1 (um) ponto cada questão.')


def test_fgv_nota_igual_ao_total_de_acertos_e_bruta():
    cfg = extrair_fator_correcao([CPRM])

    assert cfg.modelo is ModeloCorrecao.BRUTA
    assert cfg.fator_penalidade == 0.0
    assert cfg.nota_maxima is None
    assert cfg.pagina_origem == 1
    assert 'igual ao total de acertos' in cfg.trecho_origem


def test_edital_sem_regra_de_pontuacao_nao_extrai_nada():
    assert extrair_fator_correcao(['EDITAL Nº 1', 'Das inscrições.']) is None


ANULACAO_AGSUS = """14.3.4 Se, do exame de recurso, resultar a anulação de questão integrante da Prova Objetiva, a pontuação
correspondente a ela será atribuída a todos os candidatos."""

DESCONTOS_TCU = """12.7 Durante o Programa de Formação, o candidato fará jus a auxílio financeiro, na forma da legislação
vigente à época de sua realização, sobre o qual incidirão os descontos legais, ressalvado o direito de optar"""


@pytest.mark.parametrize('texto', [ANULACAO_AGSUS, DESCONTOS_TCU, 'os valores descontados em folha'])
def test_anulacao_de_questao_e_descontos_legais_nao_sao_mencao_a_penalidade(texto):
    assert not mencao_penalidade([texto])


@pytest.mark.parametrize(
    'texto',
    [
        '1,00 ponto negativo, caso a resposta esteja em discordância',
        'cada questão errada implicará desconto de 0,25 ponto',
        'o valor da questão errada será descontado da nota',
        'a cada 4 (quatro) questões erradas, anula-se uma certa',
        'cada erro anulará um acerto',
    ],
)
def test_frases_de_penalidade_sao_mencao(texto):
    assert mencao_penalidade(['Capa', texto])


def test_mencao_a_penalidade_quebrada_entre_paginas_e_reconhecida():
    assert mencao_penalidade(['caso discorde, 1,00 ponto', 'negativo, caso a resposta'])


def test_ponto_por_questao_com_mencao_a_desconto_nao_e_bruta():
    texto = AGSUS + 'Cada resposta errada implicará desconto de 0,25 ponto.'

    assert extrair_fator_correcao([texto]) is None


def concurso(pontuacao: str = 'cebraspe', correcao: dict | None = None):
    dados = {
        'nome': 'sintetico',
        'banca': 'cebraspe',
        'formato': 'certo_errado',
        'pontuacao': pontuacao,
        'provas': {
            'cg': {'gabarito': 'g1.txt', 'itens': [1, 50]},
            'ce': {'gabarito': 'g2.txt', 'itens': [51, 120]},
        },
        'respostas': {'arquivo': 'respostas.txt'},
    }
    if correcao is not None:
        dados['correcao'] = correcao
    return validar_dados(Path('provas/sintetico'), dados)


def test_resolver_usa_o_edital_com_documento_de_origem_e_nota_maxima_pelo_numero_de_itens():
    [cfg] = resolver_correcao(concurso(), {'anexo.pdf': ['Anexo I'], 'edital.pdf': ['Capa', CEBRASPE]})

    assert (cfg.modelo, cfg.fator_penalidade, cfg.fonte) == (
        ModeloCorrecao.LIQUIDA,
        1.0,
        FonteCorrecao.EDITAL,
    )
    assert (cfg.documento_origem, cfg.pagina_origem) == ('edital.pdf', 2)
    assert cfg.trecho_origem
    assert cfg.nota_maxima == 120.0
    assert cfg.nota_corte == 60.0


def test_resolver_sem_edital_nem_configuracao_cai_no_default_com_aviso(caplog):
    with caplog.at_level(logging.WARNING):
        [cfg] = resolver_correcao(concurso('simples'), {'edital.pdf': ['EDITAL Nº 1', 'Das inscrições.']})

    assert (cfg.modelo, cfg.fator_penalidade, cfg.fonte) == (ModeloCorrecao.BRUTA, 0.0, FonteCorrecao.DEFAULT)
    assert cfg.trecho_origem is None
    assert cfg.nota_maxima == 120.0
    assert 'sintetico' in caplog.text
    assert 'default' in caplog.text


def test_default_com_edital_mencionando_penalidade_avisa_a_mencao(caplog):
    paginas = ['Cada questão errada implicará desconto de 0,5 ponto na nota final.']

    with caplog.at_level(logging.WARNING):
        [cfg] = resolver_correcao(concurso('simples'), {'edital.pdf': paginas})

    assert cfg.fonte is FonteCorrecao.DEFAULT
    assert 'menciona penalidade' in caplog.text


def test_configuracao_vale_quando_o_edital_nao_define_a_regra(caplog):
    correcao = {'modelo': 'liquida', 'fator_penalidade': 1.0, 'nota_maxima': 100, 'nota_corte': 50}

    with caplog.at_level(logging.WARNING):
        [cfg] = resolver_correcao(concurso(correcao=correcao), {'edital.pdf': ['Das inscrições.']})

    assert (cfg.modelo, cfg.fator_penalidade, cfg.fonte) == (
        ModeloCorrecao.LIQUIDA,
        1.0,
        FonteCorrecao.CONFIG,
    )
    assert (cfg.nota_maxima, cfg.nota_corte) == (100.0, 50.0)
    assert caplog.text == ''


def test_edital_prevalece_sobre_a_configuracao_e_ela_completa_o_que_falta(caplog):
    correcao = {'modelo': 'bruta', 'fator_penalidade': 0, 'nota_maxima': 100}

    with caplog.at_level(logging.WARNING):
        [cfg] = resolver_correcao(concurso(correcao=correcao), {'edital.pdf': [CEBRASPE]})

    assert (cfg.modelo, cfg.fator_penalidade, cfg.fonte) == (
        ModeloCorrecao.LIQUIDA,
        1.0,
        FonteCorrecao.EDITAL,
    )
    assert (cfg.nota_maxima, cfg.nota_corte) == (100.0, 60.0)
    assert 'difere do edital' in caplog.text


def test_pontuacao_declarada_que_contradiz_o_edital_gera_aviso(caplog):
    with caplog.at_level(logging.WARNING):
        resolver_correcao(concurso('simples'), {'edital.pdf': [CEBRASPE]})

    assert "pontuacao 'simples'" in caplog.text


def questoes(*resultados: str, anuladas: tuple[int, ...] = ()) -> pd.DataFrame:
    return pd.DataFrame(
        {
            'questao': range(1, len(resultados) + 1),
            'gabarito': ['C'] * len(resultados),
            'anulada': [i + 1 in anuladas for i in range(len(resultados))],
            'resultado': list(resultados),
        }
    )


LIQUIDA = ConfiguracaoCorrecao(ModeloCorrecao.LIQUIDA, 1.0, nota_maxima=6.0)
BRUTA = ConfiguracaoCorrecao(ModeloCorrecao.BRUTA, 0.0, nota_maxima=6.0)


@pytest.mark.parametrize(('cfg', 'difere'), [(LIQUIDA, True), (BRUTA, False)])
def test_corrigida_so_difere_da_bruta_com_penalidade(cfg, difere):
    itens = aplicar_correcao(questoes('acerto', 'erro', 'branco'), cfg, Formato.CERTO_ERRADO).itens

    assert (itens['pontos_corrigida'] != itens['pontos_bruta']).any() == difere


def test_pontos_por_item_nas_tres_versoes():
    itens = aplicar_correcao(
        questoes('acerto', 'erro', 'branco', 'acerto', anuladas=(4,)), LIQUIDA, Formato.MULTIPLA_ESCOLHA
    ).itens

    assert itens['pontos_bruta'].tolist()[:3] == [1.0, 0.0, 0.0]
    assert itens['pontos_corrigida'].tolist()[:3] == [1.0, -1.0, 0.0]
    assert itens['pontos_ajustada'].tolist()[:3] == [1.0, -0.25, 0.0]
    assert itens.loc[3, ['pontos_bruta', 'pontos_corrigida', 'pontos_ajustada']].isna().all()


def test_ajuste_ao_acaso_em_certo_errado_desconta_um_ponto_por_erro():
    itens = aplicar_correcao(questoes('acerto', 'erro'), BRUTA, Formato.CERTO_ERRADO).itens

    assert itens['pontos_ajustada'].tolist() == [1.0, -1.0]


def test_nota_do_concurso_conta_anulada_como_ponto_e_bate_com_a_nota_liquida_legada():
    resultados = questoes('acerto', 'erro', 'acerto', 'branco', 'erro', 'acerto', anuladas=(3,))
    legado = agregar(resultados.assign(concurso='x', prova='u'), ['concurso'], Pontuacao.CEBRASPE)

    nota = aplicar_correcao(resultados, LIQUIDA, Formato.CERTO_ERRADO).nota

    assert nota == 1.0
    assert nota == legado['nota_liquida'].sum()


def test_questao_sem_gabarito_e_pontuada_pelo_resultado():
    sem_gabarito = questoes('branco', 'erro').assign(gabarito=[None, None])

    itens = aplicar_correcao(sem_gabarito, LIQUIDA, Formato.CERTO_ERRADO).itens

    assert itens['pontos_corrigida'].tolist() == [0.0, -1.0]


def test_nota_negativa_e_truncada_em_zero_so_na_nota_normalizada():
    corrigida = aplicar_correcao(questoes('erro', 'erro', 'acerto'), LIQUIDA, Formato.CERTO_ERRADO)

    assert corrigida.nota == -1.0
    assert corrigida.itens['pontos_corrigida'].mean() < 0
    assert nota_normalizada(corrigida.nota, LIQUIDA) == 0.0
    assert nota_normalizada(3.0, LIQUIDA) == 50.0


def test_default_nao_acusa_contradicao_com_a_pontuacao_alem_do_aviso_de_default(caplog):
    with caplog.at_level(logging.WARNING):
        resolver_correcao(concurso('cebraspe'), {'edital.pdf': ['Das inscrições.']})

    assert 'usando o default' in caplog.text
    assert 'contradiz' not in caplog.text


def test_pontuacao_coerente_com_o_edital_nao_gera_aviso(caplog):
    with caplog.at_level(logging.WARNING):
        resolver_correcao(concurso('cebraspe'), {'edital.pdf': [CEBRASPE]})

    assert caplog.text == ''
