"""Identidade de produto (exibição e CLI). O pacote Python continua `concursos`."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

# Nome mostrado na janela, Sobre, relatórios e instaladores.
NOME = 'Gabarito Vivo'

# Distribuição no PyPI/uv (importlib.metadata).
PACOTE = 'gabarito-vivo'

# Comando principal.
COMANDO = 'gabarito-vivo'
COMANDO_GUI = 'gabarito-vivo-gui'

# Prefixo de artefatos de release (instalador, AppImage).
PREFIXO_ARTEFATO = 'gabarito-vivo'

MUTEX = 'gabarito-vivo'

SERVICO_KEYRING = 'gabarito-vivo'

ARQUIVO_LOG = 'gabarito-vivo.log'

USER_AGENT = 'gabarito-vivo'


def versao_do_pacote() -> str:
    try:
        return version(PACOTE)
    except PackageNotFoundError:
        return 'desconhecida'
