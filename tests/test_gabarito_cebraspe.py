import pytest
from PIL import Image

from concursos import texto
from concursos.gabarito import detectar_status, ler_gabarito_cebraspe
from concursos.modelo import ItemGabarito
from concursos.texto import OcrIndisponivelError, extrair_paginas

TRECHO_CG = """CÂMARA DOS DEPUTADOS
Aplicação: 08/03/2026
CONHECIMENTOS GERAIS PARA TODOS OS CARGOS
167_CDNS_CG1_05
0
GABARITOS OFICIAIS DEFINITIVOS
0
Obs.: ( X ) item anulado.
Item 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20
Gabarito E E E E C C E C E E E E C C C E C E E C
Item 21 22 23 24 25 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
Gabarito C C E E X 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
"""

TRECHO_CE = """CARGO 2: ANALISTA – ESPECIALIDADE: ANALISTA DE SISTEMAS
GABARITOS OFICIAIS PRELIMINARES
Item 41 42 43 44 45
Gabarito C X E C E
"""


def test_le_grade_item_gabarito_ignorando_preenchimento_com_zeros():
    itens = ler_gabarito_cebraspe(TRECHO_CG, 'gabarito_cg.pdf')
    assert [i.questao for i in itens] == list(range(1, 26))
    assert ''.join(i.resposta or 'X' for i in itens) == 'EEEECCECEEEECCCECEECCCEEX'
    assert itens[-1] == ItemGabarito(25, None, anulada=True)


def test_le_faixa_que_nao_comeca_em_um():
    itens = ler_gabarito_cebraspe(TRECHO_CE, 'gabarito_ce.pdf')
    assert [i.questao for i in itens] == [41, 42, 43, 44, 45]
    assert itens[1].anulada


def test_detecta_status_do_gabarito_pelo_texto():
    assert detectar_status(TRECHO_CG) == 'definitivo'
    assert detectar_status(TRECHO_CE) == 'preliminar'
    assert detectar_status('GABARITO OFICIAL PRELIMINAR\n100 - PAS') == 'preliminar'
    assert detectar_status('Gabaritos Definitivos da prova aplicada') == 'definitivo'
    assert detectar_status('Item 1 2\nGabarito C E') is None


def test_pdf_sem_texto_sem_tesseract_gera_erro_com_instrucao(tmp_path, monkeypatch):
    pdf = tmp_path / 'gabarito_escaneado.pdf'
    Image.new('RGB', (200, 200), 'white').save(pdf)
    monkeypatch.setattr(texto.shutil, 'which', lambda _: None)

    with pytest.raises(OcrIndisponivelError, match='gabarito_escaneado.pdf.*apt install tesseract-ocr'):
        extrair_paginas(pdf)
