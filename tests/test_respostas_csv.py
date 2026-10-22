import pytest

from concursos.modelo import Estado, Formato, Origem
from concursos.respostas import RespostasInvalidasError, ler_respostas_csv


def ler(texto: str | bytes, formato=Formato.MULTIPLA_ESCOLHA, questoes=range(1, 5), **extra):
    conteudo = texto if isinstance(texto, bytes) else texto.encode('utf-8')
    return ler_respostas_csv(conteudo, formato, questoes, 'respostas.csv', **extra)


def test_csv_manual_questao_alternativa():
    respostas = ler('questao,alternativa\n1,a\n2,\n3,-\n')

    assert [(r.questao, r.alternativa, r.estado) for r in respostas] == [
        (1, 'A', Estado.MARCADA),
        (2, None, Estado.BRANCO),
        (3, None, Estado.BRANCO),
        (4, None, Estado.BRANCO),
    ]
    assert {(r.origem, r.confianca, r.arquivo) for r in respostas} == {(Origem.MANUAL, 1.0, 'respostas.csv')}


def test_csv_do_excel_com_ponto_e_virgula_bom_e_latin1():
    texto = '\ufeffQuestão;Alternativa\n1;B\n2;C\n'

    assert [r.alternativa for r in ler(texto)][:2] == ['B', 'C']
    assert [r.alternativa for r in ler(texto.removeprefix('\ufeff').encode('cp1252'))][:2] == ['B', 'C']


def test_csv_revisado_usa_alternativa_marcada_e_mantem_a_multipla_nao_corrigida():
    texto = (
        'concurso,prova,questao,alternativa_marcada,estado,confianca_ocr,revisar,origem,arquivo,pagina\n'
        'x,unica,1,A,marcada,0.9,False,folha,folha.png,1\n'
        'x,unica,2,,multipla,0.4,True,folha,folha.png,1\n'
        'x,unica,3,D,multipla,0.4,True,folha,folha.png,1\n'
    )

    respostas = ler(texto, origem=Origem.REVISADA)

    assert [(r.alternativa, r.estado) for r in respostas[:3]] == [
        ('A', Estado.MARCADA),
        (None, Estado.MULTIPLA),
        ('D', Estado.MARCADA),
    ]
    assert respostas[0].origem is Origem.REVISADA


def test_certo_errado():
    assert [r.alternativa for r in ler('questao,alternativa\n1,c\n2,E\n', Formato.CERTO_ERRADO)][:2] == [
        'C',
        'E',
    ]


@pytest.mark.parametrize(
    ('texto', 'mensagem'),
    [
        ('numero,resposta\n1,A\n', "coluna 'questao'"),
        ('questao,alternativa\n1,F\n', "resposta 'F' inválida"),
        ('questao,alternativa\n9,A\n', 'questão 9 fora das faixas'),
        ('questao,alternativa\n1,A\n1,B\n', 'questão 1 repetida'),
        ('questao,alternativa\num,A\n', "questão 'um' inválida"),
    ],
)
def test_csv_invalido_cita_arquivo_e_linha(texto, mensagem):
    with pytest.raises(RespostasInvalidasError, match=mensagem) as erro:
        ler(texto)
    assert str(erro.value).startswith('respostas.csv')
