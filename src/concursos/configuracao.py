from dataclasses import dataclass, fields
from pathlib import Path

import yaml

from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import Contexto, ler_toml, resolver_contexto


@dataclass(frozen=True)
class ConfiguracaoGlobal:
    limiar_confianca: float = 0.75
    limiar_topico_baixo: float = 0.6
    concurso_alvo: str | None = None


def configuracao_do_projeto(contexto: Contexto | None = None) -> ConfiguracaoGlobal:
    """A seção `[analise]` do `config.toml` do projeto."""
    contexto = contexto or resolver_contexto()
    return _validar(ler_toml(contexto.config_projeto).get('analise', {}), contexto.config_projeto)


def carregar_configuracao_global(caminho: Path) -> ConfiguracaoGlobal:
    """Defaults globais; o arquivo é opcional e só precisa conter os campos alterados."""
    if not caminho.exists():
        return ConfiguracaoGlobal()
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro
    return _validar(dados, caminho)


def _validar(dados: dict, caminho: Path) -> ConfiguracaoGlobal:
    conhecidos = {campo.name for campo in fields(ConfiguracaoGlobal)}
    if desconhecidos := sorted(set(dados) - conhecidos):
        raise ConfiguracaoInvalidaError(
            f'{caminho}: campos desconhecidos {", ".join(desconhecidos)} (use {", ".join(sorted(conhecidos))})'
        )
    for campo, valor in dados.items():
        if campo == 'concurso_alvo':
            if valor is not None and (not isinstance(valor, str) or not valor.strip()):
                raise ConfiguracaoInvalidaError(
                    f'{caminho}: concurso_alvo deve ser o nome da pasta do concurso, recebido {valor!r}'
                )
        elif not isinstance(valor, int | float) or not 0 <= valor <= 1:
            raise ConfiguracaoInvalidaError(
                f'{caminho}: {campo} deve ser um número entre 0 e 1, recebido {valor!r}'
            )
    return ConfiguracaoGlobal(**dados)
