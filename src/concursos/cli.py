import argparse
import logging
import sys
from pathlib import Path

from concursos.assistente import InteracaoAutomatica, InteracaoConsole
from concursos.cadastro import cadastrar
from concursos.pipeline import analisar_todos, listar_concursos
from concursos.status import avaliar, formatar_tabela

logger = logging.getLogger('concursos')


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format='%(levelname)s %(message)s'
    )
    try:
        if args.comando == 'adicionar':
            interacao = InteracaoAutomatica() if args.aceitar_sugestoes else InteracaoConsole()
            return 0 if cadastrar(Path(args.pasta), interacao) else 1
        if args.comando == 'analisar':
            sucesso = analisar_todos(Path(args.provas), Path(args.analises), args.forcar, args.concurso)
            return 0 if sucesso else 1
        if args.comando == 'status':
            situacoes = [avaliar(pasta) for pasta in listar_concursos(Path(args.provas))]
            sys.stdout.write(formatar_tabela(situacoes) + '\n')
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
    adicionar.add_argument('pasta', help='pasta com os arquivos do concurso, ex.: provas/tcu_25')
    adicionar.add_argument(
        '--aceitar-sugestoes', action='store_true', help='não pergunta; falha se algo for ambíguo'
    )

    analisar = subcomandos.add_parser('analisar', help='processa os concursos e gera as análises')
    analisar.add_argument('--provas', default='provas', help='pasta com um subdiretório por concurso')
    analisar.add_argument('--analises', default='analises', help='pasta de saída')
    analisar.add_argument('--forcar', action='store_true', help='reprocessa mesmo sem mudanças')
    analisar.add_argument('--concurso', help='processa apenas o concurso com este nome de pasta')

    status = subcomandos.add_parser('status', help='mostra a situação de cada concurso')
    status.add_argument('--provas', default='provas', help='pasta com um subdiretório por concurso')
    return parser
