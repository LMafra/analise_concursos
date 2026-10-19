import argparse
import logging
from pathlib import Path

from concursos.pipeline import analisar_todos

logger = logging.getLogger('concursos')


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format='%(levelname)s %(message)s'
    )
    try:
        if args.comando == 'analisar':
            analisar_todos(Path(args.provas), Path(args.analises))
    except (ValueError, FileNotFoundError) as erro:
        logger.error('%s', erro)
        return 1
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='concursos', description='Análise de desempenho em concursos')
    parser.add_argument('-v', '--verbose', action='store_true', help='log detalhado')
    subcomandos = parser.add_subparsers(dest='comando', required=True)

    analisar = subcomandos.add_parser('analisar', help='processa os concursos e gera as análises')
    analisar.add_argument('--provas', default='provas', help='pasta com um subdiretório por concurso')
    analisar.add_argument('--analises', default='analises', help='pasta de saída')
    return parser
