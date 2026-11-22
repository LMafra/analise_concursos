import logging
import sys

import typer

from concursos.cli.comandos import app
from concursos.cli.erros import (
    CODIGO_USUARIO,
    ErroDoUsuario,
    configurar_log,
    mostrar_erro,
    mostrar_inesperado,
)
from concursos.config.contexto import resolver_home
from concursos.linguagem import erro_para_a_tela
from concursos.produto import COMANDO

logger = logging.getLogger('concursos')


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    arquivo_log = configurar_log(resolver_home() / 'logs')
    try:
        return app(args=argv, prog_name=COMANDO, standalone_mode=False) or 0
    except typer.Abort:
        mostrar_erro('interrompido antes do fim')
        return CODIGO_USUARIO
    except ErroDoUsuario as erro:
        logger.debug('erro do usuário', exc_info=True)
        mostrar_erro(erro.causa, erro.dica, erro.detalhe)
        return erro.codigo
    except (ValueError, FileNotFoundError) as erro:
        logger.debug('erro nos dados', exc_info=True)
        traduzido = erro_para_a_tela(erro)
        mostrar_erro(traduzido.causa, traduzido.dica, traduzido.detalhe)
        return CODIGO_USUARIO
    except typer.TyperException as erro:
        mostrar_erro(f'uso inválido: {erro.format_message()}', f'veja as opções com `{COMANDO} --help`')
        return erro.exit_code
    except Exception:
        logger.debug('falha inesperada', exc_info=True)
        mostrar_inesperado(arquivo_log)
        return CODIGO_USUARIO


def executar() -> None:
    sys.exit(main())


def executar_gui() -> None:
    sys.exit(main(['gui', *sys.argv[1:]]))
