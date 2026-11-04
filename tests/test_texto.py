import time

import pytesseract
from PIL import Image

from concursos import texto
from concursos.gabarito import Secao, selecionar_secao
from concursos.texto import abreviar, extrair_paginas, juntar_linhas, normalizar


def test_normalizar_tira_acento_espacos_extras_e_unifica_tracos_em_maiusculas():
    assert normalizar('  Analista –  Tecnologia — da Informação ') == 'ANALISTA - TECNOLOGIA - DA INFORMACAO'


def test_secao_do_gabarito_casa_cargo_com_caixa_acento_e_traco_diferentes():
    secoes = [Secao('CARGO 2: ANALISTA – TI', '1', []), Secao('CARGO 3: TÉCNICO', '1', [])]

    assert selecionar_secao(secoes, 'cargo 3: tecnico', 'Tipo 1', 'g.pdf') is secoes[1]


def test_abreviar_corta_no_ultimo_espaco_antes_do_limite_e_marca_o_corte():
    assert abreviar('Ameaças e vulnerabilidades em aplicações', 20) == 'Ameaças e…'
    assert len(abreviar('Ameaças e vulnerabilidades em aplicações', 20)) <= 20


def test_abreviar_nao_mexe_no_texto_que_cabe_e_corta_palavra_unica_longa():
    assert abreviar('Redes de computadores', 21) == 'Redes de computadores'
    assert abreviar('Desoxirribonucleico', 10) == 'Desoxirri…'


def test_abreviar_nao_deixa_pontuacao_antes_das_reticencias():
    assert abreviar('Segurança: injection, XSS e CSRF', 24) == 'Segurança: injection…'


def test_juntar_linhas_desfaz_hifenizacao_na_quebra_e_colapsa_espacos():
    linhas = ['Modelagem de da-  ', '  dos relacional   e', 'Lei Anti-', 'Corrupção']

    assert juntar_linhas(linhas) == 'Modelagem de dados relacional e Lei Anti- Corrupção'


def test_ocr_em_paralelo_devolve_as_paginas_na_ordem_do_pdf(tmp_path, monkeypatch):
    pdf = tmp_path / 'edital_escaneado.pdf'
    larguras = [100, 160, 220, 280, 340, 400]
    primeira, *demais = [Image.new('RGB', (largura, 200), 'white') for largura in larguras]
    primeira.save(pdf, save_all=True, append_images=demais)
    monkeypatch.setattr(texto.shutil, 'which', lambda _: '/usr/bin/tesseract')

    def tesseract_que_termina_as_primeiras_por_ultimo(imagem, lang):
        largura = round(imagem.width / texto.ESCALA_OCR)
        time.sleep((500 - largura) / 10_000)
        return f'página de {largura} pt'

    monkeypatch.setattr(pytesseract, 'image_to_string', tesseract_que_termina_as_primeiras_por_ultimo)

    assert extrair_paginas(pdf) == [f'página de {largura} pt' for largura in larguras]


def test_leitura_repetida_vem_da_memoria_ate_o_conteudo_mudar(tmp_path, monkeypatch):
    caminho = tmp_path / 'gabarito.txt'
    caminho.write_text('1 A\f2 B', encoding='utf-8')
    leituras = []
    ler_texto = type(caminho).read_text
    monkeypatch.setattr(type(caminho), 'read_text', lambda *a, **k: leituras.append(1) or ler_texto(*a, **k))

    primeira = extrair_paginas(caminho)
    primeira.append('alterada por quem leu')
    assert extrair_paginas(caminho) == ['1 A', '2 B']
    assert len(leituras) == 1

    caminho.write_text('1 C', encoding='utf-8')
    assert extrair_paginas(caminho) == ['1 C']
    assert len(leituras) == 2
