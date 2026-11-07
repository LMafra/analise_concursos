import logging
import sys

import typer

from concursos.cli import legado
from concursos.cli.comandos import app
from concursos.cli.erros import (
    CODIGO_USUARIO,
    ErroDoUsuario,
    configurar_log,
    mostrar_erro,
    mostrar_inesperado,
)
from concursos.config.contexto import resolver_home

COMANDOS_LEGADOS = {'adicionar': 'add', 'analisar': 'analyze'}

logger = logging.getLogger('concursos')


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    arquivo_log = configurar_log(resolver_home() / 'logs')
    try:
        if argv and argv[0] in COMANDOS_LEGADOS:
            logger.warning(
                '`%s` está obsoleto e sai na fase 5; use `concurso-analise %s`',
                argv[0],
                COMANDOS_LEGADOS[argv[0]],
            )
            return legado.main(argv)
        return app(args=argv, prog_name='concurso-analise', standalone_mode=False) or 0
    except typer.Abort:
        mostrar_erro('interrompido antes do fim')
        return CODIGO_USUARIO
    except ErroDoUsuario as erro:
        logger.debug('erro do usuário', exc_info=True)
        mostrar_erro(erro.causa, erro.dica, erro.detalhe)
        return erro.codigo
    except (ValueError, FileNotFoundError) as erro:
        logger.debug('erro nos dados', exc_info=True)
        mostrar_erro(str(erro))
        return CODIGO_USUARIO
    except typer.TyperException as erro:
        mostrar_erro(f'uso inválido: {erro.format_message()}', 'veja as opções com `concurso-analise --help`')
        return erro.exit_code
    except Exception:
        logger.debug('falha inesperada', exc_info=True)
        mostrar_inesperado(arquivo_log)
        return CODIGO_USUARIO


def executar() -> None:
    sys.exit(main())


def executar_gui() -> None:
    sys.exit(main(['gui', *sys.argv[1:]]))


def executar_legado() -> None:
    argv = sys.argv[1:]
    if not (argv and argv[0] in COMANDOS_LEGADOS):
        sys.stderr.write(
            'aviso: o executável `concursos` está obsoleto e sai na fase 5; use `concurso-analise`\n'
        )
    sys.exit(main(argv))
