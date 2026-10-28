import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from concursos.texto import juntar_linhas

_ITEM_CEBRASPE = re.compile(r'^(\d{1,3})\s+(\S.*)$')
_QUESTAO = re.compile(r'^(\d{1,3})(?:\.\s+(\S.*)|\s*)$')
_COMANDO = re.compile(r'\bjulgue\b', re.IGNORECASE)
_FIM_DE_FRASE = ('.', ':', '?', ')', '”', '"')
SALTO_MAXIMO = 3


@dataclass
class Bloco:
    comando: str
    itens: dict[int, str] = field(default_factory=dict)


def texto_em_colunas(caminho: Path) -> str:
    """Texto do caderno lendo cada página em duas colunas (esquerda, depois direita)."""
    if caminho.suffix.lower() != '.pdf':
        return caminho.read_text(encoding='utf-8')
    partes = []
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            meio = pagina.width / 2
            for x0, x1 in ((0, meio), (meio, pagina.width)):
                partes.append(pagina.crop((x0, 0, x1, pagina.height)).extract_text() or '')
    return '\n'.join(partes)


def segmentar(texto: str, questoes: range, por_itens: bool) -> dict[int, str]:
    """Texto de cada questão; na segmentação por itens (Cebraspe), o comando do bloco vem antes do item."""
    if por_itens:
        return {
            numero: f'{bloco.comando} {item}'.strip()
            for bloco in blocos_cebraspe(texto, questoes)
            for numero, item in bloco.itens.items()
        }
    por_numero = _por_numero(_sem_cabecalhos(texto), questoes, _QUESTAO)
    return {numero: juntar_linhas(linhas) for numero, linhas in por_numero.items()}


def blocos_cebraspe(texto: str, questoes: range) -> list[Bloco]:
    linhas = _sem_cabecalhos(texto)
    inicios = _inicios(linhas, questoes, _ITEM_CEBRASPE)
    blocos: list[Bloco] = []
    comando, _ = _separar_comando(linhas[: inicios[0][1]] if inicios else [])
    bloco = Bloco(comando)
    for indice, (numero, linha) in enumerate(inicios):
        fim = inicios[indice + 1][1] if indice + 1 < len(inicios) else len(linhas)
        primeira = _ITEM_CEBRASPE.match(linhas[linha].strip()).group(2)
        proximo_comando, corpo = _separar_comando(linhas[linha + 1 : fim])
        bloco.itens[numero] = juntar_linhas([primeira, *corpo])
        if proximo_comando:
            blocos.append(bloco)
            bloco = Bloco(proximo_comando)
    if bloco.itens:
        blocos.append(bloco)
    return blocos


def _separar_comando(linhas: list[str]) -> tuple[str, list[str]]:
    """Separa 'Acerca de ..., julgue os itens a seguir.' do fim do trecho; devolve (comando, restante)."""
    ultima = next((i for i in range(len(linhas) - 1, -1, -1) if _COMANDO.search(linhas[i])), None)
    if ultima is None:
        return '', linhas
    fim = next((i for i in range(ultima, len(linhas)) if linhas[i].rstrip().endswith('.')), len(linhas) - 1)
    inicio = ultima
    while inicio > 0 and not linhas[inicio - 1].rstrip().endswith(_FIM_DE_FRASE):
        inicio -= 1
    corpo = linhas[:inicio]
    while corpo and not corpo[-1].rstrip().endswith(_FIM_DE_FRASE):
        corpo.pop()
    corpo = _sem_texto_base(corpo)
    return juntar_linhas(linhas[inicio : fim + 1]), corpo


def _sem_cabecalhos(texto: str) -> list[str]:
    """Descarta cabeçalhos de página ('CEBRASPE – ... – Edital: 2025', '-- CONHECIMENTOS --')."""
    return [linha for linha in texto.splitlines() if linha.strip() and not _cabecalho(linha)]


def _cabecalho(linha: str) -> bool:
    letras = [c for c in linha if c.isalpha()]
    maiusculas = len(letras) >= 4 and sum(c.isupper() for c in letras) >= 0.8 * len(letras)
    return maiusculas or '--' in linha or linha.lstrip().startswith('CEBRASPE')


def _sem_texto_base(linhas: list[str]) -> list[str]:
    """Remove um texto-base ('Texto CE1A1 ...') que aparece entre o último item e o próximo comando."""
    for indice, linha in enumerate(linhas):
        if re.match(r'^Texto\s+[A-Z0-9]+\b', linha.strip()):
            return linhas[:indice]
    return linhas


def _inicios(linhas: list[str], questoes: range, padrao: re.Pattern) -> list[tuple[int, int]]:
    inicios, ultima = [], questoes.start - 1
    for indice, linha in enumerate(linhas):
        encontrado = padrao.match(linha.strip())
        if not encontrado:
            continue
        numero = int(encontrado.group(1))
        if numero in questoes and ultima < numero <= ultima + SALTO_MAXIMO:
            inicios.append((numero, indice))
            ultima = numero
    return inicios


def _por_numero(linhas: list[str], questoes: range, padrao: re.Pattern) -> dict[int, list[str]]:
    inicios = _inicios(linhas, questoes, padrao)
    textos = {}
    for indice, (numero, linha) in enumerate(inicios):
        fim = inicios[indice + 1][1] if indice + 1 < len(inicios) else len(linhas)
        resto = padrao.match(linhas[linha].strip()).group(2)
        textos[numero] = [*([resto] if resto else []), *linhas[linha + 1 : fim]]
    return textos
