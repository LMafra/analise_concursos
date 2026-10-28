import logging
import re
import shutil
import unicodedata
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

logger = logging.getLogger(__name__)

MINIMO_CARACTERES_PAGINA = 20
ESCALA_OCR = 300 / 72


class OcrIndisponivelError(RuntimeError):
    pass


def normalizar(texto: str) -> str:
    """Forma de comparação: sem acento, em maiúsculas, com um espaço entre palavras e '–'/'—' como '-'."""
    sem_acento = ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[–—]', '-', sem_acento).upper().split())


def juntar_linhas(linhas: list[str]) -> str:
    """Uma linha só, com espaços simples; 'da-' seguido de 'dos' vira 'dados', mas 'Anti-' + 'Corrupção' não."""
    texto = ''
    for linha in (linha.strip() for linha in linhas):
        if texto.endswith('-') and linha[:1].islower():
            texto = texto[:-1] + linha
        else:
            texto = f'{texto} {linha}' if texto else linha
    return re.sub(r'\s+', ' ', texto).strip()


def abreviar(texto: str, limite: int) -> str:
    """Até `limite` caracteres, cortando no último espaço e marcando o corte com '…'."""
    if len(texto) <= limite:
        return texto
    corte = texto[: limite - 1]
    if (espaco := corte.rfind(' ')) > 0:
        corte = corte[:espaco]
    return corte.rstrip(' ,;:.–-') + '…'


def extrair_paginas(caminho: Path, ocr: bool = True) -> list[str]:
    """Texto de cada página (PDF ou txt com páginas separadas por form feed); páginas sem camada de
    texto passam por OCR (Tesseract), a menos que ocr=False."""
    if caminho.suffix.lower() != '.pdf':
        return caminho.read_text(encoding='utf-8').split('\f')
    with pdfplumber.open(caminho) as pdf:
        paginas = [pagina.extract_text() or '' for pagina in pdf.pages]
    sem_texto = [i for i, texto in enumerate(paginas) if len(texto.strip()) < MINIMO_CARACTERES_PAGINA]
    if sem_texto and ocr:
        logger.info('%s: %d página(s) sem texto, aplicando OCR', caminho.name, len(sem_texto))
        for indice, texto in zip(sem_texto, _ocr(caminho, sem_texto), strict=True):
            paginas[indice] = texto
    return paginas


def extrair_texto(caminho: Path) -> str:
    return '\n'.join(extrair_paginas(caminho))


def _ocr(caminho: Path, indices: list[int]) -> list[str]:
    if shutil.which('tesseract') is None:
        raise OcrIndisponivelError(
            f'{caminho}: páginas {[i + 1 for i in indices]} não têm texto e o Tesseract não está instalado. '
            'Instale com: sudo apt install tesseract-ocr tesseract-ocr-por'
        )
    import pytesseract

    documento = pdfium.PdfDocument(caminho)
    try:
        imagens = [documento[i].render(scale=ESCALA_OCR).to_pil() for i in indices]
    finally:
        documento.close()
    return [pytesseract.image_to_string(imagem, lang='por') for imagem in imagens]
