import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pdfplumber

from concursos.gabarito import detectar_status
from concursos.linhas import LinhaInvalidaError, ler_linhas

EXTENSOES_IMAGEM = frozenset({'.png', '.jpg', '.jpeg'})
EXTENSOES_TEXTO = frozenset({'.txt', '.csv'})
EXTENSOES_COMPACTADAS = frozenset({'.rar', '.zip', '.7z', '.tar', '.gz'})
ARQUIVOS_DO_SISTEMA = frozenset({'concurso.yaml'})
PASTAS_DO_SISTEMA = frozenset({'revisao', 'candidatos'})
MAXIMO_CARACTERES_FOLHA = 400

_MARCAS_PROVA = (
    'JULGUE',
    'SUA PROVA',
    'CADERNO DE',
    'LEIA ATENTAMENTE',
    'PROVAS OBJETIVAS E',
    'CADA UM DOS ITENS',
    'CONFIRA INICIALMENTE',
)
_MARCAS_EDITAL = ('TORNA PUBLIC', 'NO USO DE SUAS ATRIBUICOES', 'CONTEUDO PROGRAMATICO', 'DAS DISPOSICOES')
_BANCAS = (
    ('cebraspe', ('CEBRASPE',)),
    ('fgv', ('FGV', 'FUNDACAO GETULIO VARGAS')),
    ('selecon', ('SELECON',)),
    ('quadrix', ('QUADRIX',)),
)


class Papel(StrEnum):
    EDITAL = 'edital'
    PROVA = 'prova'
    GABARITO = 'gabarito'
    FOLHA = 'folha'
    RESPOSTAS = 'respostas'
    RESULTADO = 'resultado'
    IGNORADO = 'ignorado'
    DESCONHECIDO = 'desconhecido'


@dataclass(frozen=True)
class ArquivoDetectado:
    caminho: Path
    papel: Papel
    banca: str | None = None
    status_gabarito: str | None = None
    tipo_caderno: str | None = None
    texto: str = ''

    @property
    def nome(self) -> str:
        return self.caminho.name


def normalizar(texto: str) -> str:
    sem_acento = ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[–—]', '-', sem_acento).upper().split())


def classificar_texto(nome: str, texto: str, paginas: int, tem_imagem: bool) -> Papel:
    """Papel de um PDF a partir do texto das primeiras páginas, do número de páginas e de imagens."""
    texto = re.sub(r'https?://\S+', '', texto)
    inicio = normalizar(texto[:900])
    if 'RESULTADO' in inicio[:450]:
        return Papel.RESULTADO
    if 'GABARITO' in inicio[:700]:
        return Papel.GABARITO
    if paginas == 1 and tem_imagem and len(texto.strip()) < MAXIMO_CARACTERES_FOLHA:
        return Papel.FOLHA
    corpo = normalizar(texto)
    marcas_edital = any(marca in corpo for marca in _MARCAS_EDITAL) or eh_anexo(texto)
    if re.search(r'\bEDITAL\b(?!\s*:)', inicio) and marcas_edital:
        return Papel.EDITAL
    if any(marca in corpo for marca in _MARCAS_PROVA):
        return Papel.PROVA
    return Papel.DESCONHECIDO


def eh_anexo(texto: str) -> bool:
    """Título 'ANEXO <n>' numa linha própria; citações como 'art. 19, Anexo I' não contam."""
    return re.search(r'^\s*ANEXO\s+[IVXLC\d]+\b', texto[:900], re.MULTILINE) is not None


def detectar_banca(texto: str) -> str | None:
    corpo = normalizar(texto)
    for banca, marcas in _BANCAS:
        if any(re.search(rf'\b{marca}\b', corpo) for marca in marcas):
            return banca
    return None


def detectar_tipo_caderno(texto: str) -> str | None:
    corpo = _desduplicar(normalizar(texto[:2000]))
    if casamento := re.search(r'\bTIPO\s+0?(\d)\b', corpo):
        return casamento[1]
    if casamento := re.search(r'\bPROVA\s+([AB])\b', corpo):
        return casamento[1]
    return None


def _desduplicar(texto: str) -> str:
    """Desfaz o texto em negrito simulado que alguns PDFs extraem com letras dobradas ('PPRROOVVAA')."""
    return ' '.join(_token_simples(token) for token in texto.split())


def _token_simples(token: str) -> str:
    pares = (
        len(token) >= 2
        and len(token) % 2 == 0
        and all(token[i] == token[i + 1] for i in range(0, len(token), 2))
    )
    return token[::2] if pares else token


def classificar_arquivo(caminho: Path, pasta: Path) -> ArquivoDetectado:
    if arquivo_do_sistema(caminho, pasta):
        return ArquivoDetectado(caminho, Papel.IGNORADO)
    sufixo = caminho.suffix.lower()
    if sufixo in EXTENSOES_COMPACTADAS:
        return ArquivoDetectado(caminho, Papel.IGNORADO)
    if sufixo in EXTENSOES_IMAGEM:
        return ArquivoDetectado(caminho, Papel.FOLHA)
    if sufixo in EXTENSOES_TEXTO:
        texto = caminho.read_text(encoding='utf-8', errors='replace')
        papel = classificar_texto_manual(caminho.name, texto)
    elif sufixo == '.pdf':
        texto, paginas, tem_imagem = _ler_pdf(caminho)
        papel = classificar_texto(caminho.name, texto, paginas, tem_imagem)
    else:
        return ArquivoDetectado(caminho, Papel.DESCONHECIDO)
    return ArquivoDetectado(
        caminho,
        papel,
        banca=detectar_banca(texto),
        status_gabarito=detectar_status(texto) if papel is Papel.GABARITO else None,
        tipo_caderno=detectar_tipo_caderno(texto) if papel is Papel.PROVA else None,
        texto=texto,
    )


def classificar_texto_manual(nome: str, texto: str) -> Papel:
    """Arquivo de texto com uma questão por linha: gabarito se citar 'gabarito', senão respostas."""
    if 'GABARITO' in normalizar(f'{nome} {texto}'):
        return Papel.GABARITO
    try:
        linhas = ler_linhas(texto)
    except LinhaInvalidaError:
        return Papel.DESCONHECIDO
    return Papel.RESPOSTAS if linhas else Papel.DESCONHECIDO


def arquivo_do_sistema(caminho: Path, pasta: Path) -> bool:
    relativo = caminho.relative_to(pasta)
    return (
        caminho.name in ARQUIVOS_DO_SISTEMA
        or caminho.suffix.lower() in {'.yaml', '.yml'}
        or caminho.name.endswith(':Zone.Identifier')
        or relativo.parts[0] in PASTAS_DO_SISTEMA
    )


def _ler_pdf(caminho: Path, paginas_lidas: int = 2) -> tuple[str, int, bool]:
    with pdfplumber.open(caminho) as pdf:
        primeiras = pdf.pages[:paginas_lidas]
        texto = '\n'.join(pagina.extract_text() or '' for pagina in primeiras)
        tem_imagem = any(pagina.images for pagina in primeiras)
        return texto, len(pdf.pages), tem_imagem
