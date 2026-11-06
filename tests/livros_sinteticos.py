"""Livros gerados no teste: PDF com páginas de texto e páginas "escaneadas" (sem texto), EPUB e DOCX."""

import zipfile
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402


def pdf(caminho: Path, paginas: list[str | None]) -> Path:
    """Cada item é o texto de uma página; None gera uma página sem camada de texto."""
    with plt.rc_context({'pdf.fonttype': 42}), PdfPages(caminho) as documento:
        for texto in paginas:
            figura = plt.figure(figsize=(6, 8))
            if texto is not None:
                for linha, trecho in enumerate(texto.split('\n')):
                    figura.text(0.05, 0.9 - linha * 0.05, trecho, fontsize=10)
            documento.savefig(figura)
            plt.close(figura)
    return caminho


def epub(caminho: Path, capitulos: list[str]) -> Path:
    manifesto = ''.join(
        f'<item id="c{i}" href="texto/c{i}.xhtml" media-type="application/xhtml+xml"/>'
        for i in range(len(capitulos))
    )
    ordem = ''.join(f'<itemref idref="c{i}"/>' for i in range(len(capitulos)))
    with zipfile.ZipFile(caminho, 'w') as arquivo:
        arquivo.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        arquivo.writestr(
            'META-INF/container.xml',
            '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/livro.opf" media-type="application/oebps-package+xml"/>'
            '</rootfiles></container>',
        )
        arquivo.writestr(
            'OEBPS/livro.opf',
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            f'<manifest>{manifesto}</manifest><spine>{ordem}</spine></package>',
        )
        for i, texto in enumerate(capitulos):
            arquivo.writestr(
                f'OEBPS/texto/c{i}.xhtml',
                f'<html><head><style>p {{}}</style></head><body><h1>Capítulo {i + 1}</h1><p>{texto}</p></body></html>',
            )
    return caminho


def docx(caminho: Path, paginas: list[str]) -> Path:
    import docx as python_docx
    from docx.enum.text import WD_BREAK

    documento = python_docx.Document()
    for indice, texto in enumerate(paginas):
        paragrafo = documento.add_paragraph()
        if indice:
            paragrafo.add_run().add_break(WD_BREAK.PAGE)
        paragrafo.add_run(texto)
    documento.save(str(caminho))
    return caminho
