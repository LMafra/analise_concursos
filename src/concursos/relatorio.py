import pandas as pd

from concursos.atualizacao import COLUNAS_DIFF, impacto
from concursos.concurso_config import ConcursoConfig
from concursos.resultado_oficial import Validacao, formatar


def gerar_relatorio(
    config: ConcursoConfig,
    por_disciplina: pd.DataFrame,
    geral: pd.DataFrame,
    validacao: Validacao | None = None,
    diff: pd.DataFrame | None = None,
) -> str:
    linhas = [
        f'# Relatório de desempenho: {config.nome}',
        '',
        f'- Banca: {config.banca}',
        f'- Formato: {config.formato}',
        f'- Pontuação: {config.pontuacao}',
        '',
        *_selo_preliminar(config),
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
        *_secao_troca(config, geral, diff),
    ]
    return '\n'.join(linhas)


def _selo_preliminar(config: ConcursoConfig) -> list[str]:
    preliminares = [p.chave for p in config.provas if p.gabarito.status == 'preliminar']
    if not preliminares:
        return []
    return [
        f'> **Gabarito preliminar (provisório)** nas provas {", ".join(preliminares)}: '
        'os resultados podem mudar quando o definitivo sair.',
        '',
    ]


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


def _secao_troca(config: ConcursoConfig, geral: pd.DataFrame, diff: pd.DataFrame | None) -> list[str]:
    if diff is None:
        return []
    acertos, nota = int(geral['acertos'].sum()), float(geral['nota_liquida'].sum())
    delta_acertos, delta_nota = impacto(diff, config.pontuacao)
    anuladas = int((diff['mudanca'] == 'anulada').sum())
    linhas = [
        '## Preliminar → Definitivo',
        '',
        f'{len(diff)} questões mudaram ({anuladas} anuladas). '
        f'Acertos: {acertos - delta_acertos} → {acertos}; '
        f'nota líquida: {formatar(nota - delta_nota)} → {formatar(nota)}.',
        '',
    ]
    if not diff.empty:
        linhas += [_tabela(diff, COLUNAS_DIFF), '']
    return linhas


def _tabela(dados: pd.DataFrame, colunas: list[str]) -> str:
    cabecalho = '| ' + ' | '.join(colunas) + ' |'
    separador = '|' + '|'.join('---' for _ in colunas) + '|'
    corpo = [
        '| ' + ' | '.join(str(valor) for valor in linha) + ' |'
        for linha in dados[colunas].itertuples(index=False)
    ]
    return '\n'.join([cabecalho, separador, *corpo])
