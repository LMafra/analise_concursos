import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

ARQUIVO_LOG = 'concurso-analise.log'
CODIGO_USUARIO = 1
CODIGO_AMBIENTE = 2
_MARCA_HANDLER = '_concurso_analise'

logger = logging.getLogger('concursos')


class ErroDoUsuario(Exception):
    """Falha que o usuário resolve sozinho: a mensagem diz a causa e a dica diz o comando."""

    codigo = CODIGO_USUARIO

    def __init__(self, causa: str, dica: str | None = None) -> None:
        super().__init__(causa)
        self.causa = causa
        self.dica = dica


class ErroDoAmbiente(ErroDoUsuario):
    codigo = CODIGO_AMBIENTE


def configurar_log(pasta_logs: Path, nivel: int = logging.INFO) -> Path | None:
    """Console no nível pedido e arquivo técnico sempre em DEBUG; devolve o arquivo, se gravável."""
    for handler in [h for h in logger.handlers if getattr(h, _MARCA_HANDLER, False)]:
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(nivel)
    console.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
    _adicionar(console)

    caminho = pasta_logs / ARQUIVO_LOG
    try:
        pasta_logs.mkdir(parents=True, exist_ok=True)
        arquivo = RotatingFileHandler(caminho, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    except OSError:
        return None
    arquivo.setLevel(logging.DEBUG)
    arquivo.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    _adicionar(arquivo)
    return caminho


def ajustar_nivel_console(nivel: int) -> None:
    for handler in logger.handlers:
        if getattr(handler, _MARCA_HANDLER, False) and not isinstance(handler, RotatingFileHandler):
            handler.setLevel(nivel)


def mostrar_erro(causa: str, dica: str | None = None) -> None:
    sys.stderr.write(f'erro: {causa}\n')
    if dica:
        sys.stderr.write(f'dica: {dica}\n')


def mostrar_inesperado(arquivo_log: Path | None) -> None:
    onde = f'detalhes em {arquivo_log}' if arquivo_log else 'rode de novo com --verbose para ver os detalhes'
    mostrar_erro('falha inesperada', onde)


def _adicionar(handler: logging.Handler) -> None:
    setattr(handler, _MARCA_HANDLER, True)
    logger.addHandler(handler)
