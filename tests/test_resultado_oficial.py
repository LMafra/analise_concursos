import pytest

from concursos.resultado_oficial import ResultadoOficialError, interpretar_resultado

CPNU = """RESULTADO DEFINITIVO PROVA OBJETIVA
CONCURSO PÚBLICO NACIONAL UNIFICADO - CPNU 2
Nome: FULANO DE TAL
Bloco: Bloco 3 - Ciências, Dados e Tecnologia
Inscrição: 250000000001
Ordem Qtd. Acertos Qtd. Qtd. Qtd. Qtd. Qtd. Nota Nota
de Cargo / Especialidade Conhecimentos Acertos Acertos Acertos Acertos Acertos Conhecimentos Conhecimentos Situação
Preferência Gerais Eixo 1 Eixo 2 Eixo 3 Eixo 4 Eixo 5 Gerais Específicos
0 (B3-07-C) Tecnologista | Geral 16 8 3 11 9 5 16 71 87 Aprovado Não classificado
1 (B3-08-A) Analista do Seguro Social | Tecnologia da informação 16 8 3 11 9 5 16 79 95 Aprovado Não classificado
"""

LISTA_DATAPREV = """RESULTADO PROVA OBJETIVA
ANALISTA DE PROCESSAMENTO
Inscrição Nome Nascimento Portuguesa Inglesa Matemático Atualidades da Info e Proteção de Dados Específicos Objetiva Situação
600000001 Beltrano Silva 25/12/2001 8 7 2 3 2 55 77 Aprovado
600000002 Fulano De Tal 27/08/1993 7 9 3 3 3 47,5 72,5 Aprovado
"""

LISTA_SELECON = """RESULTADO FINAL DA PROVA OBJETIVA
501 - ANALISTA TÉCNICO EM DIREITO
INSCRIÇÃO NOME CGDI CEDI PONTOS
480000001 CICLANO DA SILVA - - -
480000002 FULANO DE TAL 17,00 40,00 57,00
"""

FINAL_DO_CONCURSO = """RESULTADO FINAL DO CONCURSO (RETIFICADO)
101 - PAS - ANALISTA DE TI
INSCRIÇÃO NOME NOTA CLASSIFICAÇÃO
14600001 FULANO DE TAL 44,00 136º
"""


def test_cpnu_individual_soma_acertos_de_gerais_e_eixos():
    resultado = interpretar_resultado([CPNU], None, 'cpnu.pdf')

    assert resultado.medida == 'acertos'
    assert resultado.total == 52
    assert resultado.componentes == (16, 8, 3, 11, 9, 5)
    assert resultado.somente_objetiva


@pytest.mark.parametrize(
    ('texto', 'identificador', 'total', 'componentes'),
    [
        (LISTA_DATAPREV, '600000002', 72.5, (7, 9, 3, 3, 3, 47.5)),
        (LISTA_SELECON, '480000002', 57, (17, 40)),
    ],
    ids=['dataprev', 'selecon'],
)
def test_lista_por_inscricao_usa_a_ultima_coluna_como_total(texto, identificador, total, componentes):
    resultado = interpretar_resultado(['cabeçalho', texto], identificador, 'resultado.pdf')

    assert resultado.medida == 'pontos'
    assert resultado.total == total
    assert resultado.componentes == componentes
    assert resultado.pagina == 2
    assert resultado.somente_objetiva


def test_resultado_final_do_concurso_nao_e_somente_da_objetiva():
    primeira, candidato = FINAL_DO_CONCURSO.rsplit('\n', 2)[0], FINAL_DO_CONCURSO.rsplit('\n', 2)[1]
    resultado = interpretar_resultado([primeira, f'Nível Superior\n{candidato}\n'], '14600001', 'final.pdf')

    assert resultado.total == 44
    assert not resultado.somente_objetiva


def test_candidato_sem_nota_na_lista_falha_com_mensagem_clara():
    with pytest.raises(ResultadoOficialError, match='480000001.*sem nota'):
        interpretar_resultado([LISTA_SELECON], '480000001', 'resultado.pdf')


def test_identificador_ausente_falha_com_arquivo():
    with pytest.raises(ResultadoOficialError, match=r'resultado\.pdf: inscrição 999 não encontrada'):
        interpretar_resultado([LISTA_SELECON], '999', 'resultado.pdf')


def test_lista_sem_identificador_configurado_falha():
    with pytest.raises(ResultadoOficialError, match='identificador'):
        interpretar_resultado([LISTA_SELECON], None, 'resultado.pdf')
