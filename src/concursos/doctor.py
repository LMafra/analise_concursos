import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from concursos.config.contexto import ARQUIVO_CONFIG_GLOBAL
from concursos.llm import ler_configuracao, obter_chave

ESPACO_MINIMO_MB = 200
ESPACO_RECOMENDADO_MB = 1024
PYTHON_SUPORTADO = ((3, 11), (3, 12))


class Situacao(StrEnum):
    OK = '✓'
    AVISO = '!'
    ERRO = '✗'


class Sistema(StrEnum):
    LINUX = 'apt'
    MAC = 'brew'
    WINDOWS = 'winget'


@dataclass(frozen=True)
class Item:
    nome: str
    situacao: Situacao
    detalhe: str
    correcao: str | None = None


_CORRECOES = {
    'uv': {
        Sistema.LINUX: 'curl -LsSf https://astral.sh/uv/install.sh | sh',
        Sistema.MAC: 'brew install uv',
        Sistema.WINDOWS: 'winget install astral-sh.uv',
    },
    'python': {
        Sistema.LINUX: 'uv python install 3.12',
        Sistema.MAC: 'uv python install 3.12',
        Sistema.WINDOWS: 'uv python install 3.12',
    },
    'tesseract': {
        Sistema.LINUX: 'sudo apt install tesseract-ocr tesseract-ocr-por',
        Sistema.MAC: 'brew install tesseract tesseract-lang',
        Sistema.WINDOWS: 'winget install UB-Mannheim.TesseractOCR (marque "Portuguese" nos idiomas)',
    },
    'por': {
        Sistema.LINUX: 'sudo apt install tesseract-ocr-por',
        Sistema.MAC: 'brew install tesseract-lang',
        Sistema.WINDOWS: 'rode o instalador do Tesseract de novo e marque "Portuguese" nos idiomas',
    },
}


def sistema_atual() -> Sistema:
    nome = platform.system()
    if nome == 'Darwin':
        return Sistema.MAC
    if nome == 'Windows':
        return Sistema.WINDOWS
    return Sistema.LINUX


def diagnosticar(pastas: list[Path], home: Path | None = None) -> list[Item]:
    """Os itens na ordem em que aparecem; só leitura, sem rede (a chave do LLM não é validada no provedor)."""
    sistema = sistema_atual()
    llm = [_llm(home, sistema)] if home is not None else []
    return [
        _uv(sistema),
        _python(sistema),
        _tesseract(sistema),
        Item('poppler', Situacao.OK, 'não necessário (os PDFs são lidos com pypdfium2)'),
        *(_escrita(pasta) for pasta in dict.fromkeys(pastas)),
        _espaco(pastas[0]),
        *llm,
    ]


def formatar(itens: list[Item]) -> str:
    linhas = []
    for item in itens:
        linhas.append(f'{item.situacao} {item.nome}: {item.detalhe}')
        if item.correcao:
            linhas.append(f'    correção: {item.correcao}')
    return '\n'.join(linhas)


def tem_erro(itens: list[Item]) -> bool:
    return any(item.situacao is Situacao.ERRO for item in itens)


def _uv(sistema: Sistema) -> Item:
    if caminho := shutil.which('uv'):
        return Item('uv', Situacao.OK, caminho)
    return Item(
        'uv',
        Situacao.AVISO,
        'não encontrado; é o jeito recomendado de instalar e atualizar',
        _CORRECOES['uv'][sistema],
    )


def _python(sistema: Sistema) -> Item:
    versao = sys.version_info[:2]
    texto = '.'.join(map(str, sys.version_info[:3]))
    if versao in PYTHON_SUPORTADO:
        return Item('Python', Situacao.OK, texto)
    suportadas = ' ou '.join('.'.join(map(str, v)) for v in PYTHON_SUPORTADO)
    return Item('Python', Situacao.ERRO, f'{texto}; use {suportadas}', _CORRECOES['python'][sistema])


def _tesseract(sistema: Sistema) -> Item:
    caminho = shutil.which('tesseract')
    if caminho is None:
        return Item(
            'Tesseract',
            Situacao.ERRO,
            'não encontrado no PATH; sem ele, edital e folha em imagem não são lidos',
            _CORRECOES['tesseract'][sistema],
        )
    if 'por' not in _idiomas_do_tesseract(caminho):
        return Item(
            'Tesseract',
            Situacao.AVISO,
            f'{caminho}, sem o idioma português (por)',
            _CORRECOES['por'][sistema],
        )
    return Item('Tesseract', Situacao.OK, f'{caminho}, com português')


def _idiomas_do_tesseract(caminho: str) -> list[str]:
    try:
        saida = subprocess.run(
            [caminho, '--list-langs'], capture_output=True, text=True, timeout=10, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [linha.strip() for linha in saida.splitlines()[1:] if linha.strip()]


def _llm(home: Path, sistema: Sistema) -> Item:
    configuracao = ler_configuracao(home / ARQUIVO_CONFIG_GLOBAL)
    if configuracao is None:
        return Item('LLM', Situacao.OK, 'desligado (nenhuma chamada de rede)')
    if not configuracao.consentimento:
        return Item(
            'LLM',
            Situacao.AVISO,
            f'{configuracao.provedor} configurado sem consentimento',
            'concurso-analise init',
        )
    if configuracao.variavel_chave is None:
        return Item('LLM', Situacao.OK, f'{configuracao.provedor} em {configuracao.url}, sem chave')
    encontrada = obter_chave(configuracao, home)
    if encontrada is None:
        variavel = configuracao.variavel_chave
        comando = (
            f'setx {variavel} <sua chave>' if sistema is Sistema.WINDOWS else f'export {variavel}=<sua chave>'
        )
        return Item('LLM', Situacao.ERRO, f'{configuracao.provedor} sem chave ({variavel})', comando)
    return Item('LLM', Situacao.OK, f'{configuracao.provedor}, chave em {encontrada[1]} (não validada)')


def _escrita(pasta: Path) -> Item:
    existente = next(p for p in (pasta, *pasta.parents) if p.exists())
    if os.access(existente, os.W_OK):
        return Item(
            f'escrita em {pasta}', Situacao.OK, 'ok' if existente == pasta else f'será criada em {existente}'
        )
    return Item(
        f'escrita em {pasta}',
        Situacao.ERRO,
        f'sem permissão de escrita em {existente}',
        f'chmod u+w "{existente}"' if os.name != 'nt' else 'ajuste as permissões da pasta ou escolha outra',
    )


def _espaco(pasta: Path) -> Item:
    existente = next(p for p in (pasta, *pasta.parents) if p.exists())
    livre = shutil.disk_usage(existente).free // 2**20
    detalhe = f'{livre} MB livres em {existente}'
    if livre < ESPACO_MINIMO_MB:
        return Item(
            'espaço em disco', Situacao.ERRO, f'{detalhe}; precisa de {ESPACO_MINIMO_MB} MB', 'libere espaço'
        )
    if livre < ESPACO_RECOMENDADO_MB:
        return Item('espaço em disco', Situacao.AVISO, f'{detalhe}; recomendado {ESPACO_RECOMENDADO_MB} MB')
    return Item('espaço em disco', Situacao.OK, detalhe)
