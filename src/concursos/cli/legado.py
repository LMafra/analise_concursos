import argparse
import logging
from pathlib import Path

from concursos.assistente import InteracaoAutomatica, InteracaoConsole
from concursos.cadastro import cadastrar
from concursos.cli.erros import ajustar_nivel_console
from concursos.configuracao import carregar_configuracao_global
from concursos.pipeline import analisar_todos

logger = logging.getLogger('concursos')


def main(argv: list[str]) -> int:
    """Subcomandos da fase 1 (`adicionar`, `analisar`), mantidos até a fase 5."""
    args = _parser().parse_args(argv)
    ajustar_nivel_console(logging.DEBUG if args.verbose else logging.INFO)
    try:
        if args.comando == 'adicionar':
            interacao = InteracaoAutomatica() if args.aceitar_sugestoes else InteracaoConsole()
            return 0 if cadastrar(Path(args.pasta), interacao) else 1
        if args.comando == 'analisar':
            configuracao = carregar_configuracao_global(Path(args.config))
            sucesso = analisar_todos(
                Path(args.provas), Path(args.analises), args.forcar, args.concurso, configuracao
            )
            return 0 if sucesso else 1
    except (ValueError, FileNotFoundError) as erro:
        logger.error('%s', erro)
        return 1
    except EOFError:
        logger.error('entrada encerrada antes do fim das perguntas; nada foi gravado')
        return 1
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='concursos', description='Análise de desempenho em concursos')
    parser.add_argument('-v', '--verbose', action='store_true', help='log detalhado')
    subcomandos = parser.add_subparsers(dest='comando', required=True)

    adicionar = subcomandos.add_parser(
        'adicionar', help='cadastra a pasta de um concurso (gera concurso.yaml)'
    )
    adicionar.add_argument('pasta', help='pasta com os arquivos do concurso, ex.: provas/meu_concurso')
    adicionar.add_argument(
        '--aceitar-sugestoes', action='store_true', help='não pergunta; falha se algo for ambíguo'
    )

    analisar = subcomandos.add_parser('analisar', help='processa os concursos e gera as análises')
    analisar.add_argument('--provas', default='provas', help='pasta com um subdiretório por concurso')
    analisar.add_argument('--analises', default='analises', help='pasta de saída')
    analisar.add_argument('--forcar', action='store_true', help='reprocessa mesmo sem mudanças')
    analisar.add_argument('--concurso', help='processa apenas o concurso com este nome de pasta')
    analisar.add_argument('--config', default='config.yaml', help='limiares globais (opcional)')
    return parser
