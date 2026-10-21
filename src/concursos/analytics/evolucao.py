"""Métricas da análise evolutiva: funções puras sobre o consolidado (uma linha por questão)."""

from collections.abc import Callable
from itertools import permutations

import numpy as np
import pandas as pd
from scipy import stats

from concursos.analytics.consolidado import N_MINIMO_TOPICO, PREFIXO_PESO, VARIANTE_PADRAO, colunas_de_peso

VERSOES = ('bruta', 'corrigida', 'ajustada')
VERSOES_COMPARADAS_AO_BRUTO = ('corrigida', 'ajustada')
ESTRATOS = (None, 'banca')
MINIMO_PONTOS_TENDENCIA = 3
TENDENCIA = 'tendência'
AMOSTRA_INSUFICIENTE = 'amostra insuficiente'
MAXIMO_PONTOS_P_EXATO = 9
_CASAS_NO_EMPATE = 9
_DISCIPLINA_NO_CONCURSO = ['concurso', 'banca', 'ordem', 'bloco', 'disciplina_canonica']
_CHAVES_DA_SERIE = ['bloco', 'disciplina']


def comparar_bruto_vs_corrigido(consolidado: pd.DataFrame) -> pd.DataFrame:
    """Ranking dos concursos pelo percentual bruto, corrigido pela regra do edital e ajustado ao acaso.

    Uma linha por concurso e variante, sem as anuladas. Só o corrigido usa o peso da variante (é a regra do
    edital); bruto e ajustado contam cada item uma vez. A posição 1 é o maior percentual e empates dividem a
    posição. As posições contam concursos, não linhas: cada variante é posicionada contra os outros
    concursos, e um concurso com variantes entra no ranking dos outros pela sua melhor variante. O
    deslocamento é quantas posições a linha sobe em relação ao bruto.
    """
    linhas = []
    for nome, concurso in consolidado.groupby('concurso', sort=True):
        validas = concurso[~concurso['anulada']]
        comum = {
            'concurso': nome,
            'modelo_correcao': concurso['modelo_correcao'].iloc[0],
            'fator_penalidade': concurso['fator_penalidade'].iloc[0],
            'n': len(validas),
            'percentual_bruta': 100 * validas['pontos_bruta'].sum() / len(validas),
            'percentual_ajustada': 100 * validas['pontos_ajustada'].sum() / len(validas),
        }
        for coluna in colunas_de_peso(concurso):
            if concurso[coluna].isna().all():
                continue
            peso = validas[coluna]
            variante = coluna.removeprefix(PREFIXO_PESO)
            linhas.append(
                {
                    **comum,
                    'variante': None if variante == VARIANTE_PADRAO else variante,
                    'percentual_corrigida': 100 * (peso * validas['pontos_corrigida']).sum() / peso.sum(),
                }
            )
    tabela = pd.DataFrame(linhas)
    for versao in VERSOES:
        tabela[f'posicao_{versao}'] = _posicoes(tabela, f'percentual_{versao}')
    for versao in VERSOES_COMPARADAS_AO_BRUTO:
        tabela[f'deslocamento_{versao}'] = tabela['posicao_bruta'] - tabela[f'posicao_{versao}']
    colunas = [
        'concurso',
        'variante',
        'modelo_correcao',
        'fator_penalidade',
        'n',
        *(f'percentual_{versao}' for versao in VERSOES),
        *(f'posicao_{versao}' for versao in VERSOES),
        *(f'deslocamento_{versao}' for versao in VERSOES_COMPARADAS_AO_BRUTO),
    ]
    return tabela.sort_values(['posicao_ajustada', 'concurso', 'variante'], ignore_index=True)[colunas]


def _posicoes(tabela: pd.DataFrame, coluna: str) -> pd.Series:
    percentuais = tabela[coluna].round(_CASAS_NO_EMPATE)
    melhor_por_concurso = percentuais.groupby(tabela['concurso']).max()
    return pd.Series(
        [
            1 + int((melhor_por_concurso.drop(concurso) > percentual).sum())
            for concurso, percentual in zip(tabela['concurso'], percentuais, strict=True)
        ],
        index=tabela.index,
    )


def percentual_por_disciplina_ao_longo_do_tempo(consolidado: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por concurso, bloco e disciplina canônica: percentual nas três versões (sem anuladas, sem
    truncar), nota normalizada, n e a regra de correção do concurso.

    A nota normalizada segue o edital: anulada vale ponto e o resultado é truncado em 0. Os pesos não
    entram porque cada disciplina tem um peso só dentro da prova.
    """
    validas = _validas(consolidado)
    tabela = validas.groupby(_DISCIPLINA_NO_CONCURSO, dropna=False).agg(
        n=('questao', 'size'),
        **{f'percentual_{versao}': (f'pontos_{versao}', 'mean') for versao in VERSOES},
        modelo_correcao=('modelo_correcao', 'first'),
        fator_penalidade=('fator_penalidade', 'first'),
    )
    for versao in VERSOES:
        tabela[f'percentual_{versao}'] *= 100
    pelo_edital = consolidado['pontos_corrigida'].where(~consolidado['anulada'], 1.0)
    nota = pelo_edital.groupby([consolidado[c] for c in _DISCIPLINA_NO_CONCURSO], dropna=False).mean()
    tabela['nota_normalizada'] = (100 * nota).clip(lower=0)
    colunas = [
        *(f'percentual_{versao}' for versao in VERSOES),
        'nota_normalizada',
        'modelo_correcao',
        'fator_penalidade',
    ]
    return _por_ordem(tabela.reset_index(), colunas)


def zscore_por_disciplina(consolidado: pd.DataFrame, usar: str = 'ajustada') -> pd.DataFrame:
    """z da disciplina dentro do seu concurso: (média da disciplina - média do concurso) / (desvio do
    concurso / raiz do n da disciplina), sobre a pontuação de cada item não anulado na versão `usar`.

    O desvio é o populacional (os itens são a prova inteira). Concurso com todos os itens iguais não tem z.
    """
    coluna = _coluna_de_pontos(usar)
    validas = _validas(consolidado)
    concurso = validas.groupby('concurso')[coluna].agg(
        media_concurso='mean', desvio_concurso=lambda s: s.std(ddof=0)
    )
    tabela = (
        validas.groupby(_DISCIPLINA_NO_CONCURSO, dropna=False)[coluna]
        .agg(n='size', media='mean')
        .reset_index()
        .merge(concurso, on='concurso')
    )
    erro_padrao = (tabela['desvio_concurso'] / np.sqrt(tabela['n'])).replace(0, np.nan)
    tabela['zscore'] = (tabela['media'] - tabela['media_concurso']) / erro_padrao
    tabela['percentual'] = 100 * tabela['media']
    return _por_ordem(tabela, ['percentual', 'zscore'])


def tendencia_por_disciplina(
    consolidado: pd.DataFrame, usar: str = 'ajustada', estrato: str | None = None
) -> pd.DataFrame:
    """Slope do z-score ao longo da ordem (regressão linear), com p-value, pontos e n somado.

    Só entram concursos com data e pontos com n de pelo menos N_MINIMO_TOPICO. Com menos de
    MINIMO_PONTOS_TENDENCIA ordens distintas, a série fica como amostra insuficiente, sem slope.
    """

    def calcular(serie: pd.DataFrame) -> dict:
        if serie['ordem'].nunique() < MINIMO_PONTOS_TENDENCIA:
            return {'slope': np.nan, 'p_valor': np.nan, 'situacao': AMOSTRA_INSUFICIENTE}
        regressao = stats.linregress(serie['ordem'].astype(float), serie['zscore'])
        return {'slope': regressao.slope, 'p_valor': regressao.pvalue, 'situacao': TENDENCIA}

    return _por_serie(
        zscore_por_disciplina(consolidado, usar), estrato, calcular, ['slope', 'p_valor', 'situacao']
    )


def correlacao_tempo_zscore(
    consolidado: pd.DataFrame, usar: str = 'ajustada', estrato: str | None = None
) -> pd.DataFrame:
    """Spearman entre a ordem e o z-score de cada disciplina, com p-value e pontos. Entram os mesmos
    concursos da tendência; concursos na mesma ordem viram um ponto só, pela média dos z.

    É por disciplina porque o z é relativo ao próprio concurso: a média dos z de todas as disciplinas de um
    concurso fica perto de 0 por construção e não mede tendência.
    """

    def calcular(serie: pd.DataFrame) -> dict:
        por_ordem = serie.groupby('ordem')['zscore'].mean()
        if len(por_ordem) < MINIMO_PONTOS_TENDENCIA or por_ordem.nunique() < 2:
            return {'rho': np.nan, 'p_valor': np.nan}
        resultado = stats.spearmanr(por_ordem.index.astype(float), por_ordem.to_numpy())
        p_valor = (
            _p_spearman_exato(por_ordem.to_numpy())
            if len(por_ordem) <= MAXIMO_PONTOS_P_EXATO
            else float(resultado.pvalue)
        )
        return {'rho': float(resultado.statistic), 'p_valor': p_valor}

    return _por_serie(zscore_por_disciplina(consolidado, usar), estrato, calcular, ['rho', 'p_valor'])


def modelos_distintos(consolidado: pd.DataFrame) -> list[str]:
    """Modelos de correção presentes na base; mais de um pede cautela ao comparar níveis entre concursos."""
    return sorted(consolidado['modelo_correcao'].unique())


def _por_serie(
    zscores: pd.DataFrame,
    estrato: str | None,
    calcular: Callable[[pd.DataFrame], dict],
    colunas_calculadas: list[str],
) -> pd.DataFrame:
    if estrato not in ESTRATOS:
        raise ValueError(f"estrato: '{estrato}' inválido (use banca ou nenhum)")
    chaves = [*_CHAVES_DA_SERIE, *([estrato] if estrato else [])]
    datadas = zscores[zscores['ordem'].notna() & zscores['zscore'].notna() & ~zscores['amostra_insuficiente']]
    linhas = [
        {
            **dict(zip(chaves, chave, strict=True)),
            'pontos': serie['ordem'].nunique(),
            'n': int(serie['n'].sum()),
            **calcular(serie),
        }
        for chave, serie in datadas.groupby(chaves, sort=True)
    ]
    tabela = pd.DataFrame(linhas, columns=[*chaves, 'pontos', 'n', *colunas_calculadas])
    return tabela.sort_values('p_valor', na_position='last', kind='stable', ignore_index=True)


def _p_spearman_exato(valores_em_ordem: np.ndarray) -> float:
    """p bilateral por permutação de todas as ordenações: com poucos pontos a aproximação t do scipy dá
    p = 0 para correlação perfeita, mas com 3 pontos uma ordenação perfeita acontece por acaso 1 vez em 3."""
    posicoes = np.arange(len(valores_em_ordem), dtype=float)
    postos = stats.rankdata(valores_em_ordem)
    todas = np.array(list(permutations(postos)))
    centradas = todas - todas.mean(axis=1, keepdims=True)
    referencia = posicoes - posicoes.mean()
    rhos = centradas @ referencia / (np.linalg.norm(centradas, axis=1) * np.linalg.norm(referencia))
    observado = abs(rhos[0])
    return float(np.mean(np.abs(rhos) >= observado - 1e-12))


def _validas(consolidado: pd.DataFrame) -> pd.DataFrame:
    return consolidado[~consolidado['anulada']]


def _coluna_de_pontos(usar: str) -> str:
    if usar not in VERSOES:
        raise ValueError(f"usar: '{usar}' inválido (use {', '.join(VERSOES)})")
    return f'pontos_{usar}'


def _por_ordem(tabela: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Uma linha por disciplina no concurso, com n e a marca de amostra insuficiente antes de `colunas`."""
    tabela = tabela.rename(columns={'disciplina_canonica': 'disciplina'})
    tabela['amostra_insuficiente'] = tabela['n'] < N_MINIMO_TOPICO
    chaves = ['concurso', 'banca', 'ordem', 'bloco', 'disciplina']
    return tabela.sort_values(
        ['ordem', 'concurso', 'bloco', 'disciplina'], na_position='last', ignore_index=True
    )[[*chaves, 'n', 'amostra_insuficiente', *colunas]]
