import hashlib
import json
from pathlib import Path

ARQUIVO_MANIFESTO = '.manifesto.json'
VERSAO_ANALISE = 5
_IGNORADOS = (':Zone.Identifier',)


def calcular(pasta: Path) -> dict:
    """Hash de todos os arquivos de entrada da pasta do concurso (inclui concurso.yaml e revisao/)."""
    arquivos = {
        str(caminho.relative_to(pasta)): hash_arquivo(caminho)
        for caminho in sorted(pasta.rglob('*'))
        if caminho.is_file() and not caminho.name.endswith(_IGNORADOS)
    }
    return {'versao': VERSAO_ANALISE, 'arquivos': arquivos}


def hash_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def atualizado(pasta: Path, destino: Path) -> bool:
    caminho = destino / ARQUIVO_MANIFESTO
    if not caminho.exists():
        return False
    return json.loads(caminho.read_text(encoding='utf-8')) == calcular(pasta)


def invalidar(destino: Path) -> None:
    (destino / ARQUIVO_MANIFESTO).unlink(missing_ok=True)


def gravar(pasta: Path, destino: Path) -> None:
    conteudo = json.dumps(calcular(pasta), indent=2, ensure_ascii=False)
    (destino / ARQUIVO_MANIFESTO).write_text(conteudo, encoding='utf-8')
