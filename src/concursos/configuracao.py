from dataclasses import dataclass, fields
from pathlib import Path

import yaml

from concursos.concurso_config import ConfiguracaoInvalidaError


@dataclass(frozen=True)
class ConfiguracaoGlobal:
    limiar_confianca: float = 0.75
    limiar_topico_baixo: float = 0.6


def carregar_configuracao_global(caminho: Path) -> ConfiguracaoGlobal:
    """Defaults globais; o arquivo é opcional e só precisa conter os campos alterados."""
    if not caminho.exists():
        return ConfiguracaoGlobal()
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro
    conhecidos = {campo.name for campo in fields(ConfiguracaoGlobal)}
    if desconhecidos := sorted(set(dados) - conhecidos):
        raise ConfiguracaoInvalidaError(
            f'{caminho}: campos desconhecidos {", ".join(desconhecidos)} (use {", ".join(sorted(conhecidos))})'
        )
    for campo, valor in dados.items():
        if not isinstance(valor, int | float) or not 0 <= valor <= 1:
            raise ConfiguracaoInvalidaError(
                f'{caminho}: {campo} deve ser um número entre 0 e 1, recebido {valor!r}'
            )
    return ConfiguracaoGlobal(**dados)
