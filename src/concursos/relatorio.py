import pandas as pd

from concursos.concurso_config import ConcursoConfig
from concursos.resultado_oficial import Validacao


def gerar_relatorio(
    config: ConcursoConfig,
    por_disciplina: pd.DataFrame,
    geral: pd.DataFrame,
    validacao: Validacao | None = None,
) -> str:
    linhas = [
        f'# Relatório de desempenho: {config.nome}',
        '',
        f'- Banca: {config.banca}',
        f'- Formato: {config.formato}',
        f'- Pontuação: {config.pontuacao}',
        '',
        *_secao_validacao(validacao),
        '## Resumo por prova',
        '',
        _tabela(
            geral,
            ['prova', 'total', 'acertos', 'erros', 'em_branco', 'anuladas', 'nota_liquida', 'percentual'],
        ),
        '',
        '_Anuladas contam como acerto e ficam fora do percentual (de mérito)._',
        '',
        '## Desempenho por disciplina',
        '',
        _tabela(
            por_disciplina, ['prova', 'disciplina', 'total', 'acertos', 'erros', 'em_branco', 'percentual']
        ),
        '',
    ]
    return '\n'.join(linhas)


def _secao_validacao(validacao: Validacao | None) -> list[str]:
    if validacao is None:
        return []
    texto = validacao.descricao
    if validacao.erro or validacao.divergente:
        texto = f'> **Atenção:** {texto}'
    linhas = ['## Validação com o resultado oficial', '', texto, '']
    if validacao.oficial is not None:
        linhas += [f'_Fonte: {validacao.arquivo}, página {validacao.oficial.pagina}._', '']
    return linhas


def _tabela(dados: pd.DataFrame, colunas: list[str]) -> str:
    cabecalho = '| ' + ' | '.join(colunas) + ' |'
    separador = '|' + '|'.join('---' for _ in colunas) + '|'
    corpo = [
        '| ' + ' | '.join(str(valor) for valor in linha) + ' |'
        for linha in dados[colunas].itertuples(index=False)
    ]
    return '\n'.join([cabecalho, separador, *corpo])
