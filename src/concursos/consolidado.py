import logging
from collections import Counter
from pathlib import Path

import pandas as pd

from concursos.agregacao import COLUNAS_DESEMPENHO
from concursos.correcao import TOPICO_NAO_MAPEADO
from concursos.manifesto import ARQUIVO_MANIFESTO
from concursos.relatorio import tabela_markdown
from concursos.resultado_oficial import formatar, ler_validacao
from concursos.status import Situacao, StatusConcurso, avaliar, listar_concursos
from concursos.topicos import palavras_chave

logger = logging.getLogger(__name__)

PASTA_CONSOLIDADO = 'consolidado'
MINIMO_CONCURSOS = 2
_SOMAS = ['total', 'acertos', 'erros', 'em_branco', 'anuladas', 'nota_liquida']


def consolidar(raiz_provas: Path, raiz_analises: Path, limiar_topico_baixo: float) -> None:
    """Junta os desempenhos por tópico de todos os concursos analisados e gera o comparativo."""
    situacoes = {pasta.name: avaliar(pasta) for pasta in listar_concursos(raiz_provas)}
    analisados = {nome: s for nome, s in situacoes.items() if _analisado(raiz_analises / nome)}
    geral = _desempenho_geral(raiz_analises, list(analisados))
    destino = raiz_analises / PASTA_CONSOLIDADO
    destino.mkdir(parents=True, exist_ok=True)
    geral.to_csv(destino / 'desempenho_geral.csv', index=False)
    comparativo = _comparativo(geral, situacoes, analisados, raiz_analises, limiar_topico_baixo)
    (destino / 'comparativo_concursos.md').write_text(comparativo, encoding='utf-8')
    logger.info('Consolidado de %d concursos gravado em %s', len(analisados), destino)


def _analisado(destino: Path) -> bool:
    return (destino / ARQUIVO_MANIFESTO).exists() and (destino / 'desempenho_por_topico.csv').exists()


def _desempenho_geral(raiz_analises: Path, pastas: list[str]) -> pd.DataFrame:
    tabelas = [
        pd.read_csv(
            raiz_analises / nome / 'desempenho_por_topico.csv', keep_default_na=False, dtype={'prova': str}
        )
        for nome in pastas
    ]
    if not tabelas:
        return pd.DataFrame(columns=COLUNAS_DESEMPENHO)
    return pd.concat(tabelas, ignore_index=True)[COLUNAS_DESEMPENHO]


def _comparativo(
    geral: pd.DataFrame,
    situacoes: dict[str, StatusConcurso],
    analisados: dict[str, StatusConcurso],
    raiz_analises: Path,
    limiar: float,
) -> str:
    percentual_limiar = formatar(round(limiar * 100, 2))
    linhas = [
        '# Comparativo entre concursos',
        '',
        f'Limiar de desempenho baixo: {percentual_limiar}% de acertos (sem anuladas), '
        f'em pelo menos {MINIMO_CONCURSOS} concursos.',
        '',
        '## Desempenho por concurso',
        '',
        *_por_concurso(geral, list(analisados.values())),
        '## Tópicos consistentemente baixos',
        '',
        *_baixos(geral, ['disciplina', 'topico'], limiar, 'tópico'),
        '## Disciplinas consistentemente baixas',
        '',
        *_baixos(geral, ['disciplina'], limiar, 'disciplina'),
        '## Concursos incompletos ou desatualizados',
        '',
        *_pendentes(situacoes, set(analisados)),
        '## Validação com o resultado oficial',
        '',
        *_validacoes(analisados, raiz_analises),
    ]
    return '\n'.join(linhas)


def _por_concurso(geral: pd.DataFrame, analisados: list[StatusConcurso]) -> list[str]:
    if geral.empty:
        return ['Nenhum concurso analisado.', '']
    tabela = geral.groupby('concurso', sort=True)[_SOMAS].sum().reset_index()
    tabela['percentual'] = _percentual(tabela)
    gabaritos = {s.config.nome: s.gabarito for s in analisados}
    tabela.insert(1, 'gabarito', tabela['concurso'].map(gabaritos))
    linhas = [tabela_markdown(tabela, ['concurso', 'gabarito', *_SOMAS, 'percentual']), '']
    preliminares = sorted(s.config.nome for s in analisados if s.gabarito != 'definitivo')
    if preliminares:
        linhas += [
            f'Concursos com gabarito preliminar (resultados provisórios): {", ".join(preliminares)}.',
            '',
        ]
    return linhas


def _baixos(geral: pd.DataFrame, colunas: list[str], limiar: float, rotulo: str) -> list[str]:
    """Itens (tópico ou disciplina) abaixo do limiar em pelo menos MINIMO_CONCURSOS concursos.

    Nomes vindos de editais diferentes são comparados pelas palavras-chave (sem acento, caixa e palavras vazias).
    """
    mapeados = geral[(geral[colunas] != TOPICO_NAO_MAPEADO).all(axis=1)]
    if mapeados.empty:
        return [f'Nenhum {rotulo} classificado.', '']
    mapeados = mapeados.assign(chave=mapeados[colunas].apply(_chave, axis=1))
    por_concurso = mapeados.groupby(['chave', 'concurso'], sort=False)[_SOMAS].sum().reset_index()
    por_concurso['percentual'] = _percentual(por_concurso)
    nomes = mapeados.groupby('chave')[colunas].agg(lambda v: Counter(v).most_common(1)[0][0])

    linhas = []
    for chave, grupo in por_concurso.groupby('chave', sort=False):
        baixos = grupo[grupo['percentual'] < limiar * 100].sort_values('percentual')
        if baixos['concurso'].nunique() < MINIMO_CONCURSOS:
            continue
        linha = dict(nomes.loc[chave])
        linha['concursos abaixo do limiar'] = ', '.join(
            f'{c} ({formatar(p)}%)' for c, p in zip(baixos['concurso'], baixos['percentual'], strict=True)
        )
        linha['concursos com o item'] = grupo['concurso'].nunique()
        linha['questoes'] = int(grupo['total'].sum())
        linha['percentual geral'] = float(_percentual(grupo[_SOMAS].sum().to_frame().T).iloc[0])
        linha['_ordem'] = (-baixos['concurso'].nunique(), linha['percentual geral'])
        linhas.append(linha)
    if not linhas:
        return [f'Nenhum {rotulo} abaixo do limiar em {MINIMO_CONCURSOS} ou mais concursos.', '']
    tabela = pd.DataFrame(sorted(linhas, key=lambda linha: linha['_ordem']))
    exibidas = [
        *colunas,
        'concursos abaixo do limiar',
        'concursos com o item',
        'questoes',
        'percentual geral',
    ]
    return [tabela_markdown(tabela, exibidas), '']


def _chave(nomes: pd.Series) -> str:
    return ' | '.join(' '.join(sorted(palavras_chave(nome))) for nome in nomes)


def _percentual(tabela: pd.DataFrame) -> pd.Series:
    validas = tabela['total'] - tabela['anuladas']
    merito = tabela['acertos'] - tabela['anuladas']
    return (merito / validas.where(validas > 0) * 100).fillna(0).round(2)


def _pendentes(situacoes: dict[str, StatusConcurso], analisados: set[str]) -> list[str]:
    linhas = [
        {'concurso': s.nome, 'situacao': str(s.situacao), 'motivo': '; '.join(s.motivos)}
        for s in situacoes.values()
        if s.situacao is not Situacao.COMPLETO
    ]
    linhas += [
        {
            'concurso': s.nome,
            'situacao': 'sem análise',
            'motivo': 'a última análise falhou; veja o log de `analisar`',
        }
        for pasta, s in situacoes.items()
        if s.situacao is Situacao.COMPLETO and pasta not in analisados
    ]
    if not linhas:
        return ['Todos os concursos estão completos e analisados.', '']
    return [tabela_markdown(pd.DataFrame(linhas), ['concurso', 'situacao', 'motivo']), '']


def _validacoes(analisados: dict[str, StatusConcurso], raiz_analises: Path) -> list[str]:
    linhas = []
    for pasta, situacao in analisados.items():
        validacao = ler_validacao(raiz_analises / pasta)
        if validacao is not None:
            marcador = '**Atenção:** ' if validacao['alerta'] else ''
            linhas.append(f'- {situacao.nome}: {marcador}{validacao["descricao"]}')
    return [*linhas, ''] if linhas else ['Nenhum concurso com resultado oficial cadastrado.', '']
