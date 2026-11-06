"""Texto de um livro, página a página, para ler em segundo plano e retomar de onde parou.

No EPUB, cada item da ordem de leitura conta como uma página; no DOCX, as quebras de página
gravadas pelo Word; no TXT, o form feed. Sem quebra nenhuma, o texto é dividido em blocos de
`CARACTERES_POR_PAGINA`, e a "página" citada é o número do bloco.
"""

import logging
import posixpath
import re
import shutil
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from concursos.texto import ESCALA_OCR, MINIMO_CARACTERES_PAGINA

logger = logging.getLogger(__name__)

CARACTERES_POR_PAGINA = 3000
NS_CONTAINER = {'c': 'urn:oasis:names:tc:opendocument:xmlns:container'}
NS_OPF = {'opf': 'http://www.idpf.org/2007/opf'}
QUEBRA_DOCX = re.compile(r'<w:lastRenderedPageBreak/>|<w:br [^>]*w:type="page"')

Ocr = Callable[[Path, int], str]


@dataclass(frozen=True)
class Pagina:
    numero: int
    texto: str
    ocr: bool = False


def _blocos(texto: str) -> list[str]:
    """Divide em blocos de até `CARACTERES_POR_PAGINA`, cortando entre parágrafos quando dá."""
    blocos: list[str] = []
    atual = ''
    for paragrafo in re.split(r'\n\s*\n', texto):
        if atual and len(atual) + len(paragrafo) > CARACTERES_POR_PAGINA:
            blocos.append(atual)
            atual = ''
        atual = f'{atual}\n\n{paragrafo}' if atual else paragrafo
        while len(atual) > CARACTERES_POR_PAGINA:
            blocos.append(atual[:CARACTERES_POR_PAGINA])
            atual = atual[CARACTERES_POR_PAGINA:]
    if atual.strip() or not blocos:
        blocos.append(atual)
    return blocos


def _paginas_de_texto(texto: str) -> list[str]:
    partes = texto.split('\f')
    return partes if len(partes) > 1 else _blocos(texto)


def ler_txt(caminho: Path) -> str:
    dados = caminho.read_bytes()
    try:
        return dados.decode('utf-8-sig')
    except UnicodeDecodeError:
        return dados.decode('cp1252', errors='replace')


class _Texto(HTMLParser):
    IGNORADAS = frozenset({'script', 'style', 'head'})
    BLOCOS = frozenset({'p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr', 'section'})

    def __init__(self) -> None:
        super().__init__()
        self.partes: list[str] = []
        self._ignorando = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self.IGNORADAS:
            self._ignorando += 1
        elif tag in self.BLOCOS:
            self.partes.append('\n')

    def handle_endtag(self, tag: str) -> None:
        if tag in self.IGNORADAS:
            self._ignorando = max(0, self._ignorando - 1)
        elif tag in self.BLOCOS:
            self.partes.append('\n')

    def handle_data(self, data: str) -> None:
        if not self._ignorando:
            self.partes.append(data)

    def texto(self) -> str:
        linhas = (' '.join(linha.split()) for linha in ''.join(self.partes).splitlines())
        return '\n'.join(linha for linha in linhas if linha)


def html_para_texto(html: str) -> str:
    leitor = _Texto()
    leitor.feed(html)
    leitor.close()
    return leitor.texto()


def _capitulos_epub(caminho: Path) -> list[str]:
    with zipfile.ZipFile(caminho) as epub:
        container = ElementTree.fromstring(epub.read('META-INF/container.xml'))
        rootfile = container.find('.//c:rootfile', NS_CONTAINER)
        if rootfile is None:
            return []
        opf_nome = rootfile.get('full-path', '')
        opf = ElementTree.fromstring(epub.read(opf_nome))
        base = posixpath.dirname(opf_nome)
        itens = {
            item.get('id'): item.get('href', '') for item in opf.iterfind('.//opf:manifest/opf:item', NS_OPF)
        }
        capitulos = []
        for referencia in opf.iterfind('.//opf:spine/opf:itemref', NS_OPF):
            href = itens.get(referencia.get('idref'))
            if not href:
                continue
            nome = posixpath.normpath(posixpath.join(base, href))
            try:
                capitulos.append(html_para_texto(epub.read(nome).decode('utf-8', errors='replace')))
            except KeyError:
                continue
        return capitulos


def _paginas_docx(caminho: Path) -> list[str]:
    import docx

    documento = docx.Document(str(caminho))
    paginas: list[list[str]] = [[]]
    for paragrafo in documento.paragraphs:
        if QUEBRA_DOCX.search(paragrafo._p.xml) and any(paginas[-1]):
            paginas.append([])
        paginas[-1].append(paragrafo.text)
    textos = ['\n'.join(pagina).strip() for pagina in paginas]
    return textos if len(textos) > 1 else _blocos(textos[0])


def ocr_da_pagina(caminho: Path, indice: int) -> str:
    """OCR de uma página do PDF; sem o Tesseract, devolve vazio (a página fica sem texto, com aviso)."""
    if shutil.which('tesseract') is None:
        logger.warning('%s: página %d sem texto e o Tesseract não está instalado', caminho.name, indice + 1)
        return ''
    import pypdfium2 as pdfium
    import pytesseract

    documento = pdfium.PdfDocument(caminho)
    try:
        imagem = documento[indice].render(scale=ESCALA_OCR).to_pil()
    finally:
        documento.close()
    return pytesseract.image_to_string(imagem, lang='por')


def contar_paginas(caminho: Path) -> int:
    if caminho.suffix.lower() == '.pdf':
        import pypdfium2 as pdfium

        documento = pdfium.PdfDocument(caminho)
        try:
            return len(documento)
        finally:
            documento.close()
    return len(_paginas_sem_pdf(caminho))


def _paginas_sem_pdf(caminho: Path) -> list[str]:
    extensao = caminho.suffix.lower()
    if extensao == '.epub':
        return _capitulos_epub(caminho)
    if extensao == '.docx':
        return _paginas_docx(caminho)
    return _paginas_de_texto(ler_txt(caminho))


def ler_paginas(caminho: Path, desde: int = 1, ocr: Ocr | None = ocr_da_pagina) -> Iterator[Pagina]:
    """As páginas a partir da `desde` (contando de 1); `ocr=None` não aplica OCR."""
    if caminho.suffix.lower() != '.pdf':
        for numero, texto in enumerate(_paginas_sem_pdf(caminho), start=1):
            if numero >= desde:
                yield Pagina(numero, texto.strip())
        return
    import pdfplumber

    with pdfplumber.open(caminho) as pdf:
        for indice in range(desde - 1, len(pdf.pages)):
            pagina = pdf.pages[indice]
            texto = pagina.extract_text() or ''
            pagina.close()
            if len(texto.strip()) < MINIMO_CARACTERES_PAGINA and ocr is not None:
                yield Pagina(indice + 1, ocr(caminho, indice).strip(), ocr=True)
            else:
                yield Pagina(indice + 1, texto.strip())
