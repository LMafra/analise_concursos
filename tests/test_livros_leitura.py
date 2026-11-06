from livros_sinteticos import docx, epub, pdf

from concursos.livros import leitura


def test_pdf_pagina_a_pagina_com_ocr_so_na_escaneada(tmp_path):
    arquivo = pdf(
        tmp_path / 'livro.pdf', ['Ato administrativo vinculado', None, 'Poder de polícia e seus atributos']
    )
    lidas = []

    def ocr(caminho, indice):
        lidas.append(indice)
        return 'texto da página escaneada'

    paginas = list(leitura.ler_paginas(arquivo, ocr=ocr))

    assert [p.numero for p in paginas] == [1, 2, 3]
    assert 'vinculado' in paginas[0].texto and not paginas[0].ocr
    assert paginas[1].texto == 'texto da página escaneada' and paginas[1].ocr
    assert lidas == [1]
    assert leitura.contar_paginas(arquivo) == 3


def test_retoma_da_pagina_indicada(tmp_path):
    arquivo = pdf(
        tmp_path / 'livro.pdf', ['um texto qualquer aqui', 'dois texto qualquer aqui', 'três texto aqui']
    )

    assert [p.numero for p in leitura.ler_paginas(arquivo, desde=3)] == [3]


def test_sem_tesseract_a_pagina_fica_vazia(tmp_path, monkeypatch):
    arquivo = pdf(tmp_path / 'livro.pdf', [None])
    monkeypatch.setattr(leitura.shutil, 'which', lambda _: None)

    assert [p.texto for p in leitura.ler_paginas(arquivo)] == ['']


def test_epub_um_capitulo_por_pagina_sem_estilo(tmp_path):
    arquivo = epub(tmp_path / 'livro.epub', ['Licitação e contratos', 'Improbidade'])

    paginas = list(leitura.ler_paginas(arquivo))

    assert [p.numero for p in paginas] == [1, 2]
    assert 'Licitação e contratos' in paginas[0].texto
    assert 'p {}' not in paginas[0].texto


def test_docx_pelas_quebras_de_pagina(tmp_path):
    arquivo = docx(tmp_path / 'apostila.docx', ['Primeira página', 'Segunda página'])

    assert [p.texto for p in leitura.ler_paginas(arquivo)] == ['Primeira página', 'Segunda página']


def test_txt_pelo_form_feed_ou_em_blocos(tmp_path):
    com_quebra = tmp_path / 'a.txt'
    com_quebra.write_text('um\fdois', encoding='utf-8')
    corrido = tmp_path / 'b.txt'
    corrido.write_text(('parágrafo longo ' * 60 + '\n\n') * 5, encoding='utf-8')
    latin = tmp_path / 'c.txt'
    latin.write_bytes('ação'.encode('cp1252'))

    assert [p.texto for p in leitura.ler_paginas(com_quebra)] == ['um', 'dois']
    assert len(list(leitura.ler_paginas(corrido))) == 2
    assert [p.texto for p in leitura.ler_paginas(latin)] == ['ação']
