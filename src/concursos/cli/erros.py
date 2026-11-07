import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from concursos.erros import (
    CODIGO_AMBIENTE,
    CODIGO_USUARIO,
    ErroDoAmbiente,
    ErroDoUsuario,
    FormatoComDica,
    linhas_extras,
)

__all__ = [
    'ARQUIVO_LOG',
    'CODIGO_AMBIENTE',
    'CODIGO_USUARIO',
    'ErroDoAmbiente',
    'ErroDoUsuario',
    'FormatoDoConsole',
    'ajustar_nivel_console',
    'configurar_log',
    'mostrar_erro',
    'mostrar_inesperado',
]

ARQUIVO_LOG = 'concurso-analise.log'
_MARCA_HANDLER = '_concurso_analise'

logger = logging.getLogger('concursos')


def configurar_log(pasta_logs: Path, nivel: int = logging.INFO) -> Path | None:
    """Console no nível pedido e arquivo técnico sempre em DEBUG; devolve o arquivo, se gravável."""
    for handler in [h for h in logger.handlers if getattr(h, _MARCA_HANDLER, False)]:
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(nivel)
    console.setFormatter(FormatoDoConsole())
    _adicionar(console)

    caminho = pasta_logs / ARQUIVO_LOG
    try:
        pasta_logs.mkdir(parents=True, exist_ok=True)
        arquivo = RotatingFileHandler(caminho, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    except OSError:
        return None
    arquivo.setLevel(logging.DEBUG)
    arquivo.setFormatter(FormatoComDica('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    _adicionar(arquivo)
    return caminho


class FormatoDoConsole(logging.Formatter):
    """`aviso:` ou `erro:` na primeira linha (INFO sem prefixo) e, quando o registro traz, `dica:` e
    `detalhe:` nas seguintes; o `--quiet` corta pelo nível, nunca o detalhe de um aviso que aparece."""

    _PREFIXOS = {logging.DEBUG: 'debug: ', logging.WARNING: 'aviso: ', logging.ERROR: 'erro: '}

    def format(self, record: logging.LogRecord) -> str:
        prefixo = self._PREFIXOS.get(min(record.levelno, logging.ERROR) // 10 * 10, '')
        linhas = [prefixo + record.getMessage(), *linhas_extras(record)]
        if record.exc_info:
            linhas.append(self.formatException(record.exc_info))
        return '\n'.join(linhas)


def ajustar_nivel_console(nivel: int) -> None:
    for handler in logger.handlers:
        if getattr(handler, _MARCA_HANDLER, False) and not isinstance(handler, RotatingFileHandler):
            handler.setLevel(nivel)


def mostrar_erro(causa: str, dica: str | None = None, detalhe: str | None = None) -> None:
    sys.stderr.write(f'erro: {causa}\n')
    if dica:
        sys.stderr.write(f'dica: {dica}\n')
    if detalhe:
        sys.stderr.write(f'detalhe: {detalhe}\n')


def mostrar_inesperado(arquivo_log: Path | None) -> None:
    onde = f'detalhes em {arquivo_log}' if arquivo_log else 'rode de novo com --verbose para ver os detalhes'
    mostrar_erro('falha inesperada', onde)


def _adicionar(handler: logging.Handler) -> None:
    setattr(handler, _MARCA_HANDLER, True)
    logger.addHandler(handler)
