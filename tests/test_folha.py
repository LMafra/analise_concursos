import random

import pytest
from folha_sintetica import folha_cebraspe

from concursos.folha import FolhaIlegivelError, ler_marcacoes
from concursos.modelo import Estado


def gabarito_aleatorio(total: int, semente: int = 7) -> dict[int, str]:
    sorteio = random.Random(semente)
    return {q: sorteio.choice(['C', 'E', 'C', 'E', '', 'CE']) for q in range(1, total + 1)}


def esperado(marcas: dict[int, str]) -> dict[int, tuple[str | None, Estado]]:
    resultado = {}
    for questao, letras in marcas.items():
        if len(letras) == 1:
            resultado[questao] = (letras, Estado.MARCADA)
        elif letras:
            resultado[questao] = (None, Estado.MULTIPLA)
        else:
            resultado[questao] = (None, Estado.BRANCO)
    return resultado


def lidas(marcacoes) -> dict[int, tuple[str | None, Estado]]:
    return {m.questao: (m.alternativa, m.estado) for m in marcacoes}


@pytest.mark.parametrize(
    ('total', 'por_coluna', 'origem'),
    [(180, 20, (80, 700)), (200, 20, (60, 650)), (120, 15, (150, 900)), (105, 15, (200, 1000))],
    ids=['9x20', '10x20', '8x15', '7x15'],
)
def test_le_grades_de_dimensoes_e_posicoes_diferentes(total, por_coluna, origem):
    marcas = gabarito_aleatorio(total)
    imagem = folha_cebraspe(marcas, total, por_coluna, origem=origem)

    marcacoes = ler_marcacoes(imagem, 'CE', total)

    assert lidas(marcacoes) == esperado(marcas)


def test_le_grade_levemente_rotacionada():
    marcas = gabarito_aleatorio(180, semente=3)
    imagem = folha_cebraspe(marcas, 180, 20, angulo=1.5)

    assert lidas(ler_marcacoes(imagem, 'CE', 180)) == esperado(marcas)


def test_confianca_e_alta_para_marcacoes_nitidas():
    marcas = gabarito_aleatorio(180)
    marcacoes = ler_marcacoes(folha_cebraspe(marcas, 180, 20), 'CE', 180)

    assert min(m.confianca for m in marcacoes) >= 0.75


def test_bolha_parcial_tem_confianca_baixa():
    marcas = {q: 'C' for q in range(1, 181)}
    del marcas[5]
    imagem = folha_cebraspe(marcas, 180, 20, parciais={5: 'E'})

    marcacoes = {m.questao: m for m in ler_marcacoes(imagem, 'CE', 180)}

    assert marcacoes[5].confianca < 0.75
    assert all(m.confianca >= 0.75 for q, m in marcacoes.items() if q != 5)


def test_itens_por_coluna_informado_diferente_do_detectado_falha():
    imagem = folha_cebraspe(gabarito_aleatorio(180), 180, 20)

    with pytest.raises(FolhaIlegivelError, match='20 linhas'):
        ler_marcacoes(imagem, 'CE', 180, itens_por_coluna=15)


def test_imagem_sem_grade_falha_com_mensagem_clara():
    imagem = folha_cebraspe({}, 0, 20)

    with pytest.raises(FolhaIlegivelError, match='grade'):
        ler_marcacoes(imagem, 'CE', 180)
