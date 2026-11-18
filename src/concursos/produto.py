"""Identidade de produto (exibição e CLI). O pacote Python continua `concursos`."""

from __future__ import annotations

import logging
import sys
from importlib.metadata import PackageNotFoundError, version

# Nome mostrado na janela, Sobre, relatórios e instaladores.
NOME = 'Gabarito Vivo'

# Distribuição no PyPI/uv (importlib.metadata). Não renomear nesta leva.
PACOTE = 'concurso-analise'

# Comando principal e alias legado até a próxima major.
COMANDO = 'gabarito-vivo'
COMANDO_LEGADO = 'concurso-analise'
COMANDO_GUI = 'gabarito-vivo-gui'
COMANDO_GUI_LEGADO = 'concurso-analise-gui'

# Prefixo de artefatos de release (instalador, AppImage). O atualizador aceita os dois.
PREFIXO_ARTEFATO = 'gabarito-vivo'
PREFIXO_ARTEFATO_LEGADO = 'concurso-analise'

MUTEX = 'gabarito-vivo'
MUTEX_LEGADO = 'concurso-analise'

SERVICO_KEYRING = 'gabarito-vivo'
SERVICO_KEYRING_LEGADO = 'concurso-analise'

ARQUIVO_LOG = 'gabarito-vivo.log'
ARQUIVO_LOG_LEGADO = 'concurso-analise.log'

USER_AGENT = 'gabarito-vivo'

_DEPRECATION = 'aviso: o comando `{antigo}` continua funcionando, mas está obsoleto; use `{novo}`.'

logger = logging.getLogger(__name__)


def versao_do_pacote() -> str:
    try:
        return version(PACOTE)
    except PackageNotFoundError:
        return 'desconhecida'


def aviso_comando_legado(argv0: str | None = None) -> None:
    """Registra deprecation quando o entry point legado é o que iniciou o processo."""
    nome = (argv0 or (sys.argv[0] if sys.argv else '')).rsplit('/', 1)[-1]
    nome = nome.rsplit('\\', 1)[-1]
    if nome in {COMANDO_LEGADO, COMANDO_GUI_LEGADO, f'{COMANDO_LEGADO}.exe', f'{COMANDO_GUI_LEGADO}.exe'}:
        logger.warning(_DEPRECATION.format(antigo=COMANDO_LEGADO, novo=COMANDO))
