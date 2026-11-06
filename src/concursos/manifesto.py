import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import yaml

ARQUIVO_MANIFESTO = '.manifesto.json'
VERSAO_ANALISE = 9
_IGNORADOS = (':Zone.Identifier',)
_PASTA_CANDIDATOS = 'candidatos'


Extras = Mapping[str, Path]


def calcular(pasta: Path, candidato: str | None = None, extras: Extras | None = None) -> dict:
    """Hash de todos os arquivos de entrada da pasta do concurso (inclui concurso.yaml e revisao/). Com
    candidato, entram só os arquivos comuns e os da subpasta dele. Os `extras` (de fora da pasta, como a
    taxonomia do projeto) entram só quando existem, para não invalidar os manifestos de antes deles."""
    arquivos = {
        str(caminho.relative_to(pasta)): hash_arquivo(caminho)
        for caminho in sorted(pasta.rglob('*'))
        if caminho.is_file()
        and not caminho.name.endswith(_IGNORADOS)
        and _do_par(caminho.relative_to(pasta).parts, candidato)
    }
    for nome in _edital_de_fora(pasta):
        if (pasta / nome).is_file():
            arquivos[nome] = hash_arquivo(pasta / nome)
    for chave, caminho in (extras or {}).items():
        if caminho.is_file():
            arquivos[chave] = hash_arquivo(caminho)
    return {'versao': VERSAO_ANALISE, 'arquivos': arquivos}


def _edital_de_fora(pasta: Path) -> list[str]:
    """O edital emprestado de outro concurso (`../alvo/edital.pdf`, no simulado), que o `rglob` não vê."""
    caminho = pasta / 'concurso.yaml'
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) if caminho.exists() else None
    except yaml.YAMLError:
        return []
    edital = dados.get('edital') if isinstance(dados, dict) else None
    if isinstance(edital, dict):
        nomes = [edital.get('arquivo'), edital.get('manual'), *(edital.get('anexos') or [])]
    else:
        nomes = [edital]
    return sorted(n for n in nomes if isinstance(n, str) and n.startswith('../'))


def _do_par(partes: tuple[str, ...], candidato: str | None) -> bool:
    if candidato is None or partes[0] != _PASTA_CANDIDATOS:
        return True
    return len(partes) > 2 and partes[1] == candidato


def hash_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def atualizado(
    pasta: Path, destino: Path, candidato: str | None = None, extras: Extras | None = None
) -> bool:
    caminho = destino / ARQUIVO_MANIFESTO
    if not caminho.exists():
        return False
    return json.loads(caminho.read_text(encoding='utf-8')) == calcular(pasta, candidato, extras)


def invalidar(destino: Path) -> None:
    (destino / ARQUIVO_MANIFESTO).unlink(missing_ok=True)


def gravar(pasta: Path, destino: Path, candidato: str | None = None, extras: Extras | None = None) -> None:
    conteudo = json.dumps(calcular(pasta, candidato, extras), indent=2, ensure_ascii=False)
    (destino / ARQUIVO_MANIFESTO).write_text(conteudo, encoding='utf-8')
