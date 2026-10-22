import hashlib
import json
from pathlib import Path

ARQUIVO_MANIFESTO = '.manifesto.json'
VERSAO_ANALISE = 8
_IGNORADOS = (':Zone.Identifier',)
_PASTA_CANDIDATOS = 'candidatos'


def calcular(pasta: Path, candidato: str | None = None) -> dict:
    """Hash de todos os arquivos de entrada da pasta do concurso (inclui concurso.yaml e revisao/). Com
    candidato, entram só os arquivos comuns e os da subpasta dele."""
    arquivos = {
        str(caminho.relative_to(pasta)): hash_arquivo(caminho)
        for caminho in sorted(pasta.rglob('*'))
        if caminho.is_file()
        and not caminho.name.endswith(_IGNORADOS)
        and _do_par(caminho.relative_to(pasta).parts, candidato)
    }
    return {'versao': VERSAO_ANALISE, 'arquivos': arquivos}


def _do_par(partes: tuple[str, ...], candidato: str | None) -> bool:
    if candidato is None or partes[0] != _PASTA_CANDIDATOS:
        return True
    return len(partes) > 2 and partes[1] == candidato


def hash_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def atualizado(pasta: Path, destino: Path, candidato: str | None = None) -> bool:
    caminho = destino / ARQUIVO_MANIFESTO
    if not caminho.exists():
        return False
    return json.loads(caminho.read_text(encoding='utf-8')) == calcular(pasta, candidato)


def invalidar(destino: Path) -> None:
    (destino / ARQUIVO_MANIFESTO).unlink(missing_ok=True)


def gravar(pasta: Path, destino: Path, candidato: str | None = None) -> None:
    conteudo = json.dumps(calcular(pasta, candidato), indent=2, ensure_ascii=False)
    (destino / ARQUIVO_MANIFESTO).write_text(conteudo, encoding='utf-8')
