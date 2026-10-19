import pandas as pd

from concursos.concurso_config import ConcursoConfig


def gerar_relatorio(config: ConcursoConfig, por_disciplina: pd.DataFrame, geral: pd.DataFrame) -> str:
    linhas = [
        f'# Relatório de desempenho: {config.nome}',
        '',
        f'- Banca: {config.banca}',
        f'- Formato: {config.formato}',
        f'- Pontuação: {config.pontuacao}',
        '',
        '## Resumo por prova',
        '',
        _tabela(geral, ['prova', 'total', 'acertos', 'erros', 'em_branco', 'percentual']),
        '',
        '## Desempenho por disciplina',
        '',
        _tabela(
            por_disciplina, ['prova', 'disciplina', 'total', 'acertos', 'erros', 'em_branco', 'percentual']
        ),
        '',
    ]
    return '\n'.join(linhas)


def _tabela(dados: pd.DataFrame, colunas: list[str]) -> str:
    cabecalho = '| ' + ' | '.join(colunas) + ' |'
    separador = '|' + '|'.join('---' for _ in colunas) + '|'
    corpo = [
        '| ' + ' | '.join(str(valor) for valor in linha) + ' |'
        for linha in dados[colunas].itertuples(index=False)
    ]
    return '\n'.join([cabecalho, separador, *corpo])
