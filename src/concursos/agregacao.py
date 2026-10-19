import pandas as pd

from concursos.modelo import Resultado

COLUNAS_DESEMPENHO = [
    'concurso',
    'prova',
    'disciplina',
    'topico',
    'total',
    'acertos',
    'erros',
    'percentual',
    'em_branco',
]
TODOS = 'todos'


def agregar(resultados: pd.DataFrame, por: list[str]) -> pd.DataFrame:
    """Agrega resultados por questão nas chaves pedidas; chaves de desempenho ausentes viram 'todos'."""
    contagem = resultados.assign(
        acerto=resultados['resultado'] == Resultado.ACERTO,
        erro=resultados['resultado'] == Resultado.ERRO,
        branco=resultados['resultado'] == Resultado.BRANCO,
    )
    agregado = (
        contagem.groupby(por, sort=False)
        .agg(
            total=('questao', 'size'),
            acertos=('acerto', 'sum'),
            erros=('erro', 'sum'),
            em_branco=('branco', 'sum'),
        )
        .reset_index()
    )
    agregado['percentual'] = (agregado['acertos'] / agregado['total'] * 100).round(2)
    for coluna in ('concurso', 'prova', 'disciplina', 'topico'):
        if coluna not in agregado:
            agregado[coluna] = TODOS
    return agregado[COLUNAS_DESEMPENHO]
