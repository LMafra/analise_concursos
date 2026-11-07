import pytest
from test_analytics_regras_edital import CARGOS_PF, config

from concursos.analytics.regras_edital import extrair_regras
from concursos.linguagem import TERMOS_TECNICOS_DA_MENSAGEM, rotulo_do_arquivo, traduzir_aviso


def _sem_prefixo(aviso: str) -> str:
    return aviso.split(': ', 1)[1]


@pytest.mark.parametrize(
    ('cargo', 'documento'),
    [('CARGO 9: ESCRIVÃO', CARGOS_PF), (None, 'EDITAL Nº 1, DE 2 DE JANEIRO DE 2025')],
)
def test_todo_aviso_do_edital_tem_traducao(cargo, documento):
    regras = extrair_regras(config(cargo), {'edital.pdf': [documento]})

    assert regras.avisos
    for aviso in regras.avisos:
        traducao = traduzir_aviso(_sem_prefixo(aviso))
        assert traducao, aviso
        assert not any(termo in traducao for termo in TERMOS_TECNICOS_DA_MENSAGEM), traducao


def test_traduz_o_corte_diferente_e_a_mencao_no_edital():
    assert traduzir_aviso(
        'nota de corte do concurso.yaml (40) difere da do edital (50 pontos); vale o edital'
    ) == ('a nota de corte do cadastro (40) é diferente da do edital (50 pontos); vale a do edital.')
    assert traduzir_aviso(
        'pesos não encontrados no edital, embora o edital mencione peso, pontuação; confira à mão'
    ) == (
        'não encontrei no edital o peso de cada parte da prova. O edital fala em peso, pontuação; '
        'vale conferir no PDF.'
    )


def test_aviso_desconhecido_fica_sem_traducao():
    assert traduzir_aviso('algo novo que ninguém previu') is None


def test_rotulo_do_arquivo():
    assert (
        rotulo_do_arquivo('respostas_extraidas.csv') == 'Respostas lidas da folha (respostas_extraidas.csv)'
    )
    assert rotulo_do_arquivo('provas/') == 'Suas provas (provas/)'
    assert rotulo_do_arquivo('outro.txt') == 'outro.txt'
