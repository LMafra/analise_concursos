import logging
from pathlib import Path

import pandas as pd
import pytest

from concursos.agregacao import agregar
from concursos.analytics.correcao import (
    ConfiguracaoCorrecao,
    FonteCorrecao,
    ModeloCorrecao,
    NotaFinal,
    aplicar_correcao,
    extrair_fator_correcao,
    mencao_penalidade,
    nota_normalizada,
    notas_finais,
    notas_pela_regra,
    resolver_correcao,
)
from concursos.concurso_config import PesoItens, validar_dados
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


def avisos_de_correcao(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if 'data da prova' not in r.getMessage()]


def concurso(pontuacao: str = 'cebraspe', correcao: dict | None = None, **extra):
    dados = {
        **extra,
        'nome': 'sintetico',
        'banca': extra.get('banca', 'cebraspe'),
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
        [cfg] = resolver_correcao(
            concurso('simples', banca='generic'), {'edital.pdf': ['EDITAL Nº 1', 'Das inscrições.']}
        )

    assert (cfg.modelo, cfg.fator_penalidade, cfg.fonte) == (ModeloCorrecao.BRUTA, 0.0, FonteCorrecao.DEFAULT)
    assert cfg.trecho_origem is None
    assert cfg.nota_maxima == 120.0
    assert 'sintetico' in caplog.text
    assert 'default' in caplog.text


def test_default_com_edital_mencionando_penalidade_avisa_a_mencao(caplog):
    paginas = ['Cada questão errada implicará desconto de 0,5 ponto na nota final.']

    with caplog.at_level(logging.WARNING):
        [cfg] = resolver_correcao(concurso('simples', banca='generic'), {'edital.pdf': paginas})

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
    assert avisos_de_correcao(caplog) == []


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


def test_nota_final_so_quando_a_regra_desconta_erro_ou_pesa_itens():
    itens = questoes('acerto', 'erro', 'acerto', 'branco', anuladas=(4,))
    com_corte = ConfiguracaoCorrecao(ModeloCorrecao.LIQUIDA, 1.0, nota_maxima=6.0, nota_corte=1.0)
    ponderada = ConfiguracaoCorrecao(
        ModeloCorrecao.PONDERADA, pesos=(PesoItens(3, 4, 2.0),), nota_maxima=6.0, variante='ti'
    )

    assert notas_finais(itens, [com_corte], Formato.CERTO_ERRADO) == [NotaFinal(2.0, 6.0, 1.0)]
    assert notas_finais(itens, [BRUTA, ponderada], Formato.CERTO_ERRADO) == [
        NotaFinal(1.0 + 2.0 + 2.0, 6.0, variante='ti')
    ]
    assert notas_finais(itens, [BRUTA], Formato.CERTO_ERRADO) == []


def test_percentual_pela_regra_desconta_o_erro_do_cebraspe():
    itens = questoes(*['acerto'] * 35, *['erro'] * 15)

    (nota,) = notas_pela_regra(itens, [LIQUIDA], Formato.CERTO_ERRADO)

    assert nota == NotaFinal(20.0, 50.0)
    assert nota.percentual == 40.0


def test_percentual_pela_regra_inclui_a_bruta_e_pesa_os_itens():
    itens = questoes('acerto', 'erro', 'acerto', 'branco', anuladas=(4,))
    ponderada = ConfiguracaoCorrecao(ModeloCorrecao.PONDERADA, pesos=(PesoItens(3, 4, 2.0),), variante='ti')

    bruta, pesada = notas_pela_regra(itens, [BRUTA, ponderada], Formato.CERTO_ERRADO)

    assert bruta.percentual == 75.0
    assert pesada == NotaFinal(5.0, 6.0, variante='ti')
    assert pesada.percentual == 83.33


@pytest.mark.parametrize(
    ('nota', 'texto'),
    [
        (NotaFinal(90.0, 200.0, 60.0), '90 de 200 pontos, nota de corte 60 (atinge o corte)'),
        (NotaFinal(18.0, 120.0, 36.0), '18 de 120 pontos, nota de corte 36 (abaixo do corte)'),
        (NotaFinal(-3.5, 120.0, 0.0), '-3,5 de 120 pontos, nota de corte 0 (abaixo do corte)'),
        (NotaFinal(95.0, 150.0, variante='B3-08-A'), '95 de 150 pontos'),
    ],
)
def test_texto_da_nota_final(nota, texto):
    assert nota.texto == texto


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
    assert nota_normalizada(corrigida.nota, LIQUIDA.nota_maxima) == 0.0
    assert nota_normalizada(3.0, LIQUIDA.nota_maxima) == 50.0


def test_default_nao_acusa_contradicao_com_a_pontuacao_alem_do_aviso_de_default(caplog):
    with caplog.at_level(logging.WARNING):
        resolver_correcao(concurso('cebraspe', banca='generic'), {'edital.pdf': ['Das inscrições.']})

    assert 'usando o default' in caplog.text
    assert 'contradiz' not in caplog.text


def test_pontuacao_coerente_com_o_edital_nao_gera_aviso(caplog):
    with caplog.at_level(logging.WARNING):
        resolver_correcao(concurso('cebraspe'), {'edital.pdf': [CEBRASPE]})

    assert avisos_de_correcao(caplog) == []


CRECI = """11 DAS PROVAS OBJETIVAS 11.1 As provas objetivas, de caráter eliminatório e classificatório, valerão
60,00 pontos e abrangerão os objetos de avaliação constantes do item 22 deste edital.
12.2 Para todos os cargos, a nota em cada questão das provas objetivas, feita com base nas marcações da folha
de respostas, será igual a 1,00 ponto, caso a resposta do candidato esteja em concordância com o gabarito oficial
definitivo da prova de conhecimentos básicos (P ); 2,00 pontos, caso a resposta do candidato esteja em
concordância com o gabarito oficial definitivo da prova de conhecimentos 1 específicos (P ); e 0,00 ponto, caso a
resposta do candidato esteja em discordância com o gabarito oficial definitivo das provas, caso 2
"""

DATAPREV = """9.7 Cada questão de múltipla escolha valerá 1 (um) ponto no Módulo de Conhecimentos Gerais, e 2,5
(dois virgula cinco) pontos no Módulo de Conhecimentos Específicos, sendo 115 (cento e quinze)
pontos a pontuação máxima, para todos os cargos/perfis.
"""


def test_creci_pontos_por_prova_viram_pesos_por_faixa_de_itens():
    cfg = extrair_fator_correcao([CRECI], total_itens=40)

    assert (cfg.modelo, cfg.fator_penalidade) == (ModeloCorrecao.PONDERADA, 0.0)
    assert cfg.pesos == (PesoItens(1, 20, 1.0), PesoItens(21, 40, 2.0))
    assert cfg.nota_maxima == 60.0
    assert cfg.trecho_origem.startswith('12.2 Para todos os cargos')


def test_dataprev_pontos_por_modulo_viram_pesos_por_faixa_de_itens():
    cfg = extrair_fator_correcao(['Capa', DATAPREV], total_itens=70)

    assert cfg.modelo is ModeloCorrecao.PONDERADA
    assert cfg.pesos == (PesoItens(1, 40, 1.0), PesoItens(41, 70, 2.5))
    assert cfg.nota_maxima == 115.0
    assert cfg.pagina_origem == 2
    assert cfg.trecho_origem.startswith('9.7 Cada questão de múltipla escolha')


@pytest.mark.parametrize('total_itens', [None, 70])
def test_pontos_por_prova_sem_faixas_dedutiveis_nao_viram_regra(total_itens):
    assert extrair_fator_correcao([CRECI], total_itens=total_itens) is None


def test_penalidade_fracionaria_a_cada_quatro_erradas_e_liquida_com_fator_025():
    texto = '10.4 Na correção da prova objetiva, a cada 4 (quatro) questões erradas, anula-se uma certa.'

    cfg = extrair_fator_correcao([texto])

    assert (cfg.modelo, cfg.fator_penalidade) == (ModeloCorrecao.LIQUIDA, 0.25)
    assert cfg.trecho_origem == texto


EDITAL_CPNU = """8.9. Para os cargos de Nível Superior, a Prova Objetiva será composta por 90 (noventa) questões, sendo 30
(trinta) questões de Conhecimentos Gerais e 60 (sessenta) questões de Conhecimentos Específicos.
8.9.1. A Nota Final das Provas Objetivas será obtida por meio da soma da pontuação das questões de
Conhecimentos Gerais e da pontuação ponderada das questões de Conhecimentos Específicos,
conforme os critérios estabelecidos a seguir:
a) A pontuação das questões de Conhecimentos Gerais será calculada com base no número de
acertos nas 30 (trinta) questões correspondentes, sendo atribuído peso 1 (um) a cada questão.
Assim, cada acerto valerá 1 (um) ponto, totalizando até 30 (trinta) pontos;
b) A pontuação das questões de Conhecimentos Específicos será calculada com base no número de
acertos nas 60 (sessenta) questões correspondentes, distribuídas em 5 (cinco) eixos temáticos, cada
um contendo 12 (doze) questões ponderadas de acordo com os respectivos pesos atribuídos a cada
eixo temático.
8.9.2. Os pesos atribuídos a cada eixo temático variam de 1 (um) a 5 (cinco), totalizando, em conjunto, o
valor de 10 (dez).
"""

VAGAS_CPNU = """CÓD CARGOS ESPECIALIDADE AC PCD PN PQ PI TOTAL
Analista do Tecnologia da
B3-08-A 12 1 5 0 1 19
Seguro Social informação
Tecnologia da
B3-10-A Analista I 2 0 1 0 0 3
Informação
"""

QUADRO_CPNU_P91 = """Analista de
B3-07-A Ciência e Geral 1 2 2 3 2
Tecnologia
B3-07-B Pesquisador Geral 1 2 1 3 3
B3-07-C Tecnologista Geral 1 2 1 4 2
B3-08 – Instituto Nacional do Seguro Social (INSS)
EIXO 4–
EIXO 2 – EIXO 3–
DADOS
Analista do Tecnologia da
B3-08-A 1 1 2 4 2
Seguro Social Informação
B3-09 – Ministério da Saúde (MS)
"""

QUADRO_CPNU_P92 = """B3-10 – Instituto Brasileiro de Museus (IBRAM)
DADOS
Tecnologia
B3-10-A Analista I da 1 2 3 3 1
Informação
CONTEÚDO PROGRAMÁTICO PARA AS PROVAS
"""

DOCUMENTOS_CPNU = {
    'anexo_bloco3.pdf': ['Anexo III', VAGAS_CPNU, QUADRO_CPNU_P91, QUADRO_CPNU_P92],
    'edital.pdf': ['Capa', EDITAL_CPNU],
}


def cpnu(correcao: dict | None = None):
    correcao = correcao or {'variantes': ['B3-08-A', 'B3-10-A', 'B3-07-C']}
    return validar_dados(
        Path('provas/cpnu'),
        {
            'nome': 'cpnu',
            'banca': 'fgv',
            'formato': 'multipla_escolha',
            'provas': {'unica': {'gabarito': 'g.pdf', 'itens': [1, 90]}},
            'respostas': {'arquivo': 'respostas.txt'},
            'correcao': correcao,
        },
    )


def pesos_cpnu(*eixos: float) -> tuple[PesoItens, ...]:
    faixas = [PesoItens(1, 30, 1.0)]
    for i, peso in enumerate(eixos):
        faixas.append(PesoItens(31 + 12 * i, 42 + 12 * i, float(peso)))
    return tuple(faixas)


def test_cpnu_tem_uma_variante_ponderada_por_cargo_lida_do_quadro_do_anexo(caplog):
    with caplog.at_level(logging.WARNING):
        variantes = resolver_correcao(cpnu(), DOCUMENTOS_CPNU)

    assert [cfg.variante for cfg in variantes] == ['B3-08-A', 'B3-10-A', 'B3-07-C']
    assert [cfg.pesos for cfg in variantes] == [
        pesos_cpnu(1, 1, 2, 4, 2),
        pesos_cpnu(1, 2, 3, 3, 1),
        pesos_cpnu(1, 2, 1, 4, 2),
    ]
    assert [cfg.pagina_origem for cfg in variantes] == [3, 4, 3]
    for cfg in variantes:
        assert (cfg.modelo, cfg.fator_penalidade, cfg.fonte) == (
            ModeloCorrecao.PONDERADA,
            0.0,
            FonteCorrecao.EDITAL,
        )
        assert cfg.documento_origem == 'anexo_bloco3.pdf'
        assert cfg.trecho_origem.startswith(cfg.variante)
        assert cfg.nota_maxima == 150.0
    assert avisos_de_correcao(caplog) == []


def questoes_cpnu() -> pd.DataFrame:
    acertos_por_faixa = [(30, 16), (12, 8), (12, 3), (12, 11), (12, 9), (12, 5)]
    resultados = [r for n, a in acertos_por_faixa for r in ['acerto'] * a + ['erro'] * (n - a)]
    return questoes(*resultados)


def test_notas_das_variantes_do_cpnu_batem_com_o_resultado_oficial():
    variantes = resolver_correcao(cpnu(), DOCUMENTOS_CPNU)

    notas = {
        cfg.variante: aplicar_correcao(questoes_cpnu(), cfg, Formato.MULTIPLA_ESCOLHA).nota
        for cfg in variantes
    }

    assert notas == {'B3-08-A': 95.0, 'B3-10-A': 95.0, 'B3-07-C': 87.0}


def test_pesos_nao_mudam_a_pontuacao_por_item_so_a_nota():
    cfg = ConfiguracaoCorrecao(ModeloCorrecao.PONDERADA, pesos=(PesoItens(2, 3, 4.0),))

    corrigida = aplicar_correcao(
        questoes('acerto', 'acerto', 'erro', 'acerto', anuladas=(4,)), cfg, Formato.MULTIPLA_ESCOLHA
    )

    assert corrigida.itens['pontos_corrigida'].tolist()[:3] == [1.0, 1.0, 0.0]
    assert corrigida.itens['peso'].tolist() == [1.0, 4.0, 4.0, 1.0]
    assert corrigida.nota == 1 + 4 + 0 + 1


def test_liquida_com_pesos_desconta_o_erro_pelo_peso_do_item():
    cfg = ConfiguracaoCorrecao(ModeloCorrecao.LIQUIDA, 1.0, pesos=(PesoItens(2, 2, 2.0),))

    assert aplicar_correcao(questoes('acerto', 'erro'), cfg, Formato.CERTO_ERRADO).nota == 1 - 2


def test_pesos_da_variante_na_configuracao_prevalecem_sobre_o_quadro():
    pesos = [{'itens': [31, 90], 'peso': 2}]
    correcao = {'variantes': ['B3-08-A', {'nome': 'B3-10-A', 'pesos': pesos}]}

    b3_08, b3_10 = resolver_correcao(cpnu(correcao), DOCUMENTOS_CPNU)

    assert b3_08.fonte is FonteCorrecao.EDITAL
    assert (b3_10.fonte, b3_10.modelo) == (FonteCorrecao.CONFIG, ModeloCorrecao.PONDERADA)
    assert b3_10.pesos == (PesoItens(31, 90, 2.0),)
    assert b3_10.trecho_origem is None
    assert b3_10.nota_maxima == 30 + 60 * 2


def test_nota_maxima_do_edital_nao_vale_para_variante_com_pesos_proprios():
    documentos = {**DOCUMENTOS_CPNU, 'edital.pdf': ['A Prova Objetiva totalizará 90 pontos.', EDITAL_CPNU]}
    correcao = {'variantes': ['B3-08-A', {'nome': 'B3-10-A', 'pesos': [{'itens': [31, 90], 'peso': 3}]}]}

    b3_08, b3_10 = resolver_correcao(cpnu(correcao), documentos)

    assert (b3_08.nota_maxima, b3_10.nota_maxima) == (150.0, 30 + 60 * 3)


def test_quadro_com_faixas_que_nao_somam_os_itens_do_concurso_e_ignorado_com_aviso(caplog):
    documentos = {**DOCUMENTOS_CPNU, 'edital.pdf': [EDITAL_CPNU.replace('12 (doze)', '10 (dez)')]}

    with caplog.at_level(logging.WARNING):
        [cfg] = resolver_correcao(cpnu({'variantes': ['B3-08-A']}), documentos)

    assert cfg.pesos == ()
    assert 'quadro de pesos ignorado' in caplog.text


def test_variante_fora_do_quadro_e_sem_pesos_declarados_avisa_e_fica_sem_pesos(caplog):
    with caplog.at_level(logging.WARNING):
        [cfg] = resolver_correcao(cpnu({'variantes': ['B3-99-Z']}), DOCUMENTOS_CPNU)

    assert (cfg.variante, cfg.pesos, cfg.modelo) == ('B3-99-Z', (), ModeloCorrecao.BRUTA)
    assert 'B3-99-Z' in caplog.text


def test_pesos_por_faixa_declarados_sem_regra_no_edital_viram_ponderada_de_configuracao():
    correcao = {'pesos': [{'itens': [51, 120], 'peso': 2}]}

    [cfg] = resolver_correcao(concurso('simples', correcao), {'edital.pdf': ['Das inscrições.']})

    assert (cfg.modelo, cfg.fator_penalidade, cfg.fonte) == (
        ModeloCorrecao.PONDERADA,
        0.0,
        FonteCorrecao.CONFIG,
    )
    assert cfg.pesos == (PesoItens(51, 120, 2.0),)
    assert cfg.nota_maxima == 50 + 70 * 2
