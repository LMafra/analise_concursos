import pytest

from concursos.gabarito import GabaritoInvalidoError, ler_gabarito_texto
from concursos.modelo import Estado, Formato, ItemGabarito
from concursos.respostas import RespostasInvalidasError, ler_respostas_txt


def alternativas(respostas):
    return [r.alternativa for r in respostas]


def test_aceita_separadores_variados_e_minusculas():
    texto = '1 A\n02: b\n3-C\n4,d\n5. e\n'
    respostas = ler_respostas_txt(texto, Formato.MULTIPLA_ESCOLHA, range(1, 6), 'respostas.txt')
    assert alternativas(respostas) == ['A', 'B', 'C', 'D', 'E']


def test_traco_linha_sem_resposta_e_questao_omitida_viram_branco():
    texto = '1 -\n2\n# 3 omitida\n4 C\n'
    respostas = ler_respostas_txt(texto, Formato.CERTO_ERRADO, range(1, 5), 'respostas.txt')
    assert alternativas(respostas) == [None, None, None, 'C']
    assert [r.estado for r in respostas] == [Estado.BRANCO] * 3 + [Estado.MARCADA]


def test_resposta_invalida_informa_numero_da_linha():
    texto = '1 C\n\n3 A\n'
    with pytest.raises(RespostasInvalidasError, match=r'respostas.txt: linha 3: .*\'A\''):
        ler_respostas_txt(texto, Formato.CERTO_ERRADO, range(1, 4), 'respostas.txt')


def test_questao_duplicada_informa_numero_da_linha():
    with pytest.raises(RespostasInvalidasError, match='linha 2: questão 1 duplicada'):
        ler_respostas_txt('1 A\n1 B\n', Formato.MULTIPLA_ESCOLHA, range(1, 3), 'respostas.txt')


def test_questao_fora_da_faixa_informa_numero_da_linha():
    with pytest.raises(RespostasInvalidasError, match='linha 2: questão 9 fora das faixas'):
        ler_respostas_txt('1 A\n9 B\n', Formato.MULTIPLA_ESCOLHA, range(1, 3), 'respostas.txt')


def test_linha_ilegivel_e_rejeitada():
    with pytest.raises(RespostasInvalidasError, match='linha 1: formato não reconhecido'):
        ler_respostas_txt('primeira A\n', Formato.MULTIPLA_ESCOLHA, range(1, 3), 'respostas.txt')


def test_gabarito_manual_reconhece_anuladas_e_cabecalho():
    texto = 'questao,gabarito\n1,C\n2,X\n3,*\n4,E\n'
    itens = ler_gabarito_texto(texto, Formato.CERTO_ERRADO, 'gabarito.csv')
    assert itens == [
        ItemGabarito(1, 'C'),
        ItemGabarito(2, None, anulada=True),
        ItemGabarito(3, None, anulada=True),
        ItemGabarito(4, 'E'),
    ]


def test_gabarito_manual_sem_resposta_e_invalido():
    with pytest.raises(GabaritoInvalidoError, match='linha 2'):
        ler_gabarito_texto('1 A\n2 -\n', Formato.MULTIPLA_ESCOLHA, 'gabarito.txt')
