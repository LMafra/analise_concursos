from dataclasses import dataclass, fields, replace
from pathlib import Path

import yaml

from concursos.calibracao import carregar_calibrado
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import Contexto, ler_toml, resolver_contexto
from concursos.llm import ClienteLlm
from concursos.perfis import PerfilOcr


@dataclass(frozen=True)
class ConfiguracaoGlobal:
    limiar_confianca: float = 0.75
    limiar_topico_baixo: float = 0.6
    concurso_alvo: str | None = None
    incluir_simulados: bool = False
    perfil_calibrado: PerfilOcr | None = None
    cliente_llm: ClienteLlm | None = None


_FORA_DO_ARQUIVO = {'perfil_calibrado', 'cliente_llm'}


def configuracao_do_projeto(contexto: Contexto | None = None) -> ConfiguracaoGlobal:
    """A seção `[analise]` do `config.toml` do projeto e o perfil de OCR calibrado, se houver."""
    contexto = contexto or resolver_contexto()
    configuracao = _validar(ler_toml(contexto.config_projeto).get('analise', {}), contexto.config_projeto)
    return replace(configuracao, perfil_calibrado=carregar_calibrado(contexto.projeto))


def incluir_simulados_do_projeto(contexto: Contexto | None = None) -> bool:
    """Só `[analise] incluir_simulados`, sem carregar o resto da configuração."""
    contexto = contexto or resolver_contexto()
    valor = ler_toml(contexto.config_projeto).get('analise', {}).get('incluir_simulados', False)
    return valor is True


def carregar_configuracao_global(caminho: Path) -> ConfiguracaoGlobal:
    """Defaults globais; o arquivo é opcional e só precisa conter os campos alterados."""
    if not caminho.exists():
        return ConfiguracaoGlobal()
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro
    return _validar(dados, caminho)


def validar_analise(dados: dict, caminho: Path) -> ConfiguracaoGlobal:
    """Valida a seção `[analise]` como a leitura faz, para quem grava."""
    return _validar(dados, caminho)


def _validar(dados: dict, caminho: Path) -> ConfiguracaoGlobal:
    conhecidos = {campo.name for campo in fields(ConfiguracaoGlobal)} - _FORA_DO_ARQUIVO
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
        elif campo == 'incluir_simulados':
            if not isinstance(valor, bool):
                raise ConfiguracaoInvalidaError(
                    f'{caminho}: incluir_simulados deve ser true ou false, recebido {valor!r}'
                )
        elif not isinstance(valor, int | float) or not 0 <= valor <= 1:
            raise ConfiguracaoInvalidaError(
                f'{caminho}: {campo} deve ser um número entre 0 e 1, recebido {valor!r}'
            )
    return ConfiguracaoGlobal(**dados)
