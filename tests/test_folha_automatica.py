import logging

import cv2
import numpy as np
import pytest
from conftest import analisar, criar_concurso, ler_csv
from folha_sintetica import folha_generica

from concursos.folha import FolhaIlegivelError, ler_folha
from concursos.modelo import Estado

TOTAL = 40
MARCAS = {q: 'ABCD'[q % 4] for q in range(1, TOTAL + 1)}
GABARITO = ''.join(f'{q} {MARCAS[q]}\n' for q in range(1, TOTAL + 1))


def config(**respostas) -> dict:
    return {
        'banca': 'generic',
        'formato': 'multipla_escolha',
        'alternativas': 4,
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, TOTAL]}},
        'respostas': {'folha': 'folha.png', 'total_itens': TOTAL, **respostas},
    }


def concurso_com_folha(provas, nome: str, imagem: np.ndarray, **respostas):
    pasta = criar_concurso(provas, nome, config(**respostas), {'gabarito.txt': GABARITO})
    cv2.imwrite(str(pasta / 'folha.png'), imagem)
    return pasta


def test_folha_sem_perfil_e_levemente_rotacionada_e_lida_pela_deteccao_automatica(tmp_path):
    caminho = tmp_path / 'folha.png'
    cv2.imwrite(str(caminho), folha_generica('ABCD', MARCAS, TOTAL, 15, angulo=1.5))

    lidas = ler_folha(caminho, None, TOTAL, None, tmp_path / 'depuracao', 0.75, alternativas='ABCD')

    assert [r.alternativa for r in lidas] == [MARCAS[q] for q in range(1, TOTAL + 1)]
    assert all(r.estado is Estado.MARCADA for r in lidas)
    assert (tmp_path / 'depuracao' / 'folha_p1.png').exists()


def test_duas_bolhas_de_preenchimento_parecido_saem_com_confianca_baixa(tmp_path):
    caminho = tmp_path / 'folha.png'
    cv2.imwrite(str(caminho), folha_generica('ABCD', MARCAS, TOTAL, 15, parciais={5: 'A'}))

    lidas = {r.questao: r for r in ler_folha(caminho, None, TOTAL, None, tmp_path, 0.75, alternativas='ABCD')}

    assert lidas[5].confianca < 0.75
    assert all(r.confianca >= 0.75 for q, r in lidas.items() if q != 5)


def test_sem_template_a_analise_usa_a_deteccao_automatica(raizes):
    provas, analises = raizes
    concurso_com_folha(provas, 'ficticia', folha_generica('ABCD', MARCAS, TOTAL, 15, parciais={5: 'A'}))

    assert analisar(provas, analises) == 0

    respostas = ler_csv(analises / 'ficticia' / 'respostas_extraidas.csv').set_index('questao')
    assert all(respostas.loc[q, 'alternativa_marcada'] == MARCAS[q] for q in range(1, TOTAL + 1) if q != 5)
    assert respostas['revisar'].tolist() == [q == 5 for q in range(1, TOTAL + 1)]
    assert (analises / 'ficticia' / 'depuracao' / 'folha_p1.png').exists()


def test_perfil_que_nao_le_a_folha_cai_na_deteccao_automatica(raizes, caplog):
    provas, analises = raizes
    concurso_com_folha(
        provas,
        'ficticia',
        folha_generica('ABCD', MARCAS, TOTAL, 15),
        template='grade_abcd',
        itens_por_coluna=20,
    )

    with caplog.at_level(logging.INFO):
        assert analisar(provas, analises) == 0

    assert 'detecção automática' in caplog.text
    respostas = ler_csv(analises / 'ficticia' / 'respostas_extraidas.csv')
    assert ''.join(respostas['alternativa_marcada']) == ''.join(MARCAS[q] for q in range(1, TOTAL + 1))


def test_grade_nao_detectada_da_dica_do_csv_manual(tmp_path):
    caminho = tmp_path / 'folha.png'
    cv2.imwrite(str(caminho), np.full((1754, 1240), 255, np.uint8))

    with pytest.raises(FolhaIlegivelError, match=r'dica: .*respostas\.csv'):
        ler_folha(caminho, None, TOTAL, None, tmp_path, 0.75, alternativas='ABCD')


def test_grade_nao_detectada_nao_interrompe_os_outros_concursos(raizes, caplog):
    provas, analises = raizes
    concurso_com_folha(provas, 'branca', np.full((1754, 1240), 255, np.uint8))
    concurso_com_folha(provas, 'ficticia', folha_generica('ABCD', MARCAS, TOTAL, 15))

    assert analisar(provas, analises) == 1

    assert 'dica:' in caplog.text
    assert (analises / 'ficticia' / 'respostas_extraidas.csv').exists()
