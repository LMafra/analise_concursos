import pandas as pd

from concursos.modelo import Pontuacao, Resultado

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
    'anuladas',
    'nota_liquida',
]
TODOS = 'todos'


class TotaisInconsistentesError(ValueError):
    pass


def agregar(resultados: pd.DataFrame, por: list[str], pontuacao: Pontuacao) -> pd.DataFrame:
    """Agrega resultados por questão nas chaves pedidas; chaves de desempenho ausentes viram 'todos'.

    Anuladas contam como acerto, mas ficam fora do percentual (de mérito).
    """
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
            anuladas=('anulada', 'sum'),
        )
        .reset_index()
    )
    validas = agregado['total'] - agregado['anuladas']
    acertos_merito = agregado['acertos'] - agregado['anuladas']
    agregado['percentual'] = (acertos_merito / validas.where(validas > 0) * 100).fillna(0).round(2)
    agregado['nota_liquida'] = (
        agregado['acertos'] - agregado['erros'] if pontuacao.fator_penalidade else agregado['acertos']
    )
    for coluna in ('concurso', 'prova', 'disciplina', 'topico'):
        if coluna not in agregado:
            agregado[coluna] = TODOS
    _verificar_fechamento(agregado)
    return agregado[COLUNAS_DESEMPENHO]


def _verificar_fechamento(agregado: pd.DataFrame) -> None:
    soma = agregado['acertos'] + agregado['erros'] + agregado['em_branco']
    inconsistentes = agregado[soma != agregado['total']]
    if not inconsistentes.empty:
        raise TotaisInconsistentesError(f'totais não fecham: {inconsistentes.to_dict("records")}')
