from pathlib import Path

from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import ler_toml
from concursos.pratica.interno import CAMPOS_CONFIGURACAO
from concursos.pratica.tipos import ConfiguracaoPratica

SECAO = 'pratica'


def ler_configuracao(config_projeto: Path, raiz: Path) -> ConfiguracaoPratica | None:
    """A seção `[pratica]` do `config.toml` do projeto; sem ela, a prática fica de fora da análise."""
    secao = ler_toml(config_projeto).get(SECAO)
    if secao is None:
        return None
    if desconhecidos := sorted(set(secao) - CAMPOS_CONFIGURACAO):
        raise ConfiguracaoInvalidaError(
            f'{config_projeto}: [pratica] campos desconhecidos {", ".join(desconhecidos)} '
            f'(use {", ".join(sorted(CAMPOS_CONFIGURACAO))})'
        )
    entrada = secao.get('entrada_tec')
    if not isinstance(entrada, str) or not entrada.strip():
        raise ConfiguracaoInvalidaError(
            f'{config_projeto}: [pratica] entrada_tec é a pasta das exportações do TEC'
        )
    candidato = secao.get('candidato')
    if candidato is not None and (not isinstance(candidato, str) or not candidato.strip()):
        raise ConfiguracaoInvalidaError(f'{config_projeto}: [pratica] candidato deve ser o nome da subpasta')
    enviar = secao.get('open_notebook', False)
    if not isinstance(enviar, bool):
        raise ConfiguracaoInvalidaError(f'{config_projeto}: [pratica] open_notebook deve ser true ou false')
    caminho = Path(entrada).expanduser()
    return ConfiguracaoPratica(caminho if caminho.is_absolute() else raiz / caminho, candidato, enviar)
