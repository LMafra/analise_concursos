from pathlib import Path

import yaml

from concursos.arquivos import gravar_se_mudou
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.pratica.tipos import Escolhas


def ler_escolhas(caminho: Path) -> Escolhas:
    if not caminho.exists():
        return Escolhas()
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro
    if not isinstance(dados, dict):
        raise ConfiguracaoInvalidaError(f'{caminho}: esperado um mapa com aliases, materias e cadernos')
    return Escolhas(
        dict(dados.get('aliases') or {}),
        dict(dados.get('materias') or {}),
        dict(dados.get('cadernos') or {}),
        dict(dados.get('planilhas') or {}),
    )


def gravar_escolhas(caminho: Path, escolhas: Escolhas) -> bool:
    if escolhas == Escolhas() and not caminho.exists():
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = {'aliases': escolhas.aliases, 'materias': escolhas.materias, 'cadernos': escolhas.cadernos}
    if escolhas.planilhas:
        dados['planilhas'] = escolhas.planilhas
    return gravar_se_mudou(caminho, yaml.safe_dump(dados, allow_unicode=True, sort_keys=True))