from pathlib import Path

import cv2
from conftest import analisar, criar_concurso, ler_csv
from folha_sintetica import folha_cebraspe, folha_fgv
from PIL import Image

TOTAL = 105
GABARITO = ''.join(f'{q} {"C" if q % 2 else "E"}\n' for q in range(1, TOTAL + 1))


def config(folha: str = 'folha.png') -> dict:
    return {
        'banca': 'cebraspe',
        'formato': 'certo_errado',
        'pontuacao': 'cebraspe',
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, TOTAL]}},
        'respostas': {'folha': folha, 'template': 'cebraspe_ce', 'total_itens': TOTAL},
    }


def concurso_com_folha(provas: Path, imagem, nome_folha: str = 'folha.png') -> Path:
    pasta = criar_concurso(provas, 'cebraspe', config(nome_folha), {'gabarito.txt': GABARITO})
    if nome_folha.endswith('.pdf'):
        Image.fromarray(imagem).save(pasta / nome_folha, resolution=150)
    else:
        cv2.imwrite(str(pasta / nome_folha), imagem)
    return pasta


def marcas_padrao() -> dict[int, str]:
    marcas = {q: 'C' for q in range(1, TOTAL + 1)}
    marcas[2] = ''
    marcas[3] = 'CE'
    del marcas[4]
    return marcas


def test_folha_gera_respostas_rastreaveis_e_imagem_de_depuracao(raizes):
    provas, analises = raizes
    concurso_com_folha(provas, folha_cebraspe(marcas_padrao(), TOTAL, 15, parciais={4: 'E'}))

    assert analisar(provas, analises) == 0

    respostas = ler_csv(analises / 'cebraspe' / 'respostas_extraidas.csv').set_index('questao')
    assert len(respostas) == TOTAL
    assert respostas.loc[1, ['alternativa_marcada', 'estado', 'origem', 'arquivo', 'pagina']].tolist() == [
        'C',
        'marcada',
        'folha',
        'folha.png',
        1,
    ]
    assert respostas.loc[2, 'estado'] == 'branco'
    assert respostas.loc[3, 'estado'] == 'multipla'
    assert respostas['revisar'].tolist() == [q == 4 for q in range(1, TOTAL + 1)]
    assert (analises / 'cebraspe' / 'depuracao' / 'folha_p1.png').exists()


def test_folha_em_pdf(raizes):
    provas, analises = raizes
    concurso_com_folha(provas, folha_cebraspe(marcas_padrao(), TOTAL, 15), 'folha.pdf')

    assert analisar(provas, analises) == 0

    respostas = ler_csv(analises / 'cebraspe' / 'respostas_extraidas.csv')
    assert respostas['alternativa_marcada'].iloc[0] == 'C'
    assert respostas['pagina'].iloc[0] == 1


def test_limiar_de_revisao_vem_da_configuracao_global(raizes, tmp_path):
    provas, analises = raizes
    concurso_com_folha(provas, folha_cebraspe(marcas_padrao(), TOTAL, 15, parciais={4: 'E'}))
    configuracao = tmp_path / 'config.yaml'
    configuracao.write_text('limiar_confianca: 0.3\n', encoding='utf-8')

    assert analisar(provas, analises, '--config', str(configuracao)) == 0

    assert not ler_csv(analises / 'cebraspe' / 'respostas_extraidas.csv')['revisar'].any()


def test_cartao_fgv_pelo_template(raizes):
    provas, analises = raizes
    gabarito = ''.join(f'{q} A\n' for q in range(1, 71))
    criar_concurso(
        provas,
        'fgv',
        {
            'banca': 'fgv',
            'formato': 'multipla_escolha',
            'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 70]}},
            'respostas': {'folha': 'cartao.png', 'template': 'fgv_mod70ae', 'total_itens': 70},
        },
        {'gabarito.txt': gabarito},
    )
    marcas = {q: 'ABCDE'[q % 5] for q in range(1, 71)}
    cv2.imwrite(str(provas / 'fgv' / 'cartao.png'), folha_fgv(marcas, 70, 20))

    assert analisar(provas, analises) == 0

    respostas = ler_csv(analises / 'fgv' / 'respostas_extraidas.csv')
    assert ''.join(respostas['alternativa_marcada']) == ''.join(marcas[q] for q in range(1, 71))
    assert (analises / 'fgv' / 'depuracao' / 'cartao_p1.png').exists()


def test_folha_ilegivel_falha_apontando_arquivo_e_pagina(raizes, caplog):
    provas, analises = raizes
    concurso_com_folha(provas, folha_cebraspe({}, 0, 15))

    assert analisar(provas, analises) == 1
    assert 'folha.png: página 1' in caplog.text
