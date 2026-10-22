"""Métricas da análise evolutiva: funções puras sobre o consolidado (uma linha por questão)."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from itertools import permutations

import numpy as np
import pandas as pd
from scipy import stats

from concursos.analytics.consolidado import N_MINIMO_TOPICO, PREFIXO_PESO, VARIANTE_PADRAO, colunas_de_peso
from concursos.analytics.correcao import nota_normalizada
from concursos.configuracao import ConfiguracaoGlobal
from concursos.consolidado import MINIMO_CONCURSOS
from concursos.correcao import TOPICO_NAO_MAPEADO
from concursos.modelo import Resultado
from concursos.topicos import chave_de_palavras

VERSOES = ('bruta', 'corrigida', 'ajustada')
VERSOES_COMPARADAS_AO_BRUTO = ('corrigida', 'ajustada')
ESTRATOS = (None, 'banca')
MINIMO_PONTOS_TENDENCIA = 3
TENDENCIA = 'tendência'
AMOSTRA_INSUFICIENTE = 'amostra insuficiente'
MAXIMO_PONTOS_P_EXATO = 9
LIMIAR_TOPICO_FRACO = ConfiguracaoGlobal.limiar_topico_baixo
META_PADRAO = 0.7
_CASAS_NO_EMPATE = 9
_DISCIPLINA_NO_CONCURSO = ['concurso', 'banca', 'ordem', 'bloco', 'disciplina_canonica']
_TOPICO_NO_CONCURSO = ['concurso', 'banca', 'ordem', 'disciplina_canonica', 'chave_topico']
_LINHA_DA_DISCIPLINA = ['concurso', 'banca', 'ordem', 'bloco', 'disciplina']
_LINHA_DO_TOPICO = ['concurso', 'banca', 'ordem', 'disciplina', 'chave_topico', 'topico']
_SERIE_DA_DISCIPLINA = ['bloco', 'disciplina']
_SERIE_DO_TOPICO = ['disciplina', 'chave_topico', 'topico']
_COLUNAS_DA_TENDENCIA = ['slope', 'p_valor', 'situacao']


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
        for variante, peso in _variantes(concurso):
            peso = peso.loc[validas.index]
            linhas.append(
                {
                    **comum,
                    'variante': variante,
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


@dataclass(frozen=True)
class Correlacao:
    rho: float
    p_valor: float
    pontos: int


def comparar_com_meta(consolidado: pd.DataFrame, meta: float = META_PADRAO) -> pd.DataFrame:
    """Por concurso e variante: a nota pela regra do edital (peso da variante, anulada vale ponto), a nota
    normalizada (0–100 da nota máxima, truncada em 0) e a distância até a meta. `meta` é uma fração; a
    distância fica em pontos percentuais, positiva quando a meta foi batida."""
    linhas = []
    for nome, concurso in consolidado.groupby('concurso', sort=False):
        pelo_edital = _pontos_pelo_edital(concurso)
        for variante, peso in _variantes(concurso):
            nota = float((peso * pelo_edital).sum())
            nota_maxima = float(concurso['nota_maxima'].iloc[0])
            normalizada = nota_normalizada(nota, nota_maxima)
            linhas.append(
                {
                    'concurso': nome,
                    'variante': variante,
                    'ordem': concurso['ordem'].iloc[0],
                    'modelo_correcao': concurso['modelo_correcao'].iloc[0],
                    'nota': nota,
                    'nota_maxima': nota_maxima,
                    'nota_corte': concurso['nota_corte'].iloc[0],
                    'nota_normalizada': normalizada,
                    'meta': 100 * meta,
                    'distancia': normalizada - 100 * meta,
                    'atingiu': normalizada >= 100 * meta,
                }
            )
    return pd.DataFrame(linhas).sort_values(
        ['ordem', 'concurso', 'variante'], na_position='last', ignore_index=True
    )


def correlacao_tempo_percentual(consolidado: pd.DataFrame, usar: str = 'ajustada') -> Correlacao:
    """Spearman entre a ordem e o percentual de cada concurso na versão `usar` (sem anuladas): a medida
    única de tendência geral. Concursos sem data ficam fora; concursos na mesma ordem viram um ponto só."""
    validas = _validas(consolidado)
    validas = validas[validas['ordem'].notna()]
    por_ordem = 100 * validas.groupby('ordem')[_coluna_de_pontos(usar)].mean()
    return Correlacao(**_spearman(por_ordem), pontos=len(por_ordem))


def _variantes(concurso: pd.DataFrame) -> Iterator[tuple[str | None, pd.Series]]:
    """Cada variante com peso declarado (None no concurso sem variantes) e o peso de cada item."""
    for coluna in colunas_de_peso(concurso):
        if concurso[coluna].isna().all():
            continue
        variante = coluna.removeprefix(PREFIXO_PESO)
        yield (None if variante == VARIANTE_PADRAO else variante), concurso[coluna]


def _pontos_pelo_edital(tabela: pd.DataFrame) -> pd.Series:
    """Pontuação corrigida com a anulada valendo ponto, como o edital conta a nota."""
    return tabela['pontos_corrigida'].where(~tabela['anulada'], 1.0)


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
    nota = (
        _pontos_pelo_edital(consolidado)
        .groupby([consolidado[c] for c in _DISCIPLINA_NO_CONCURSO], dropna=False)
        .mean()
    )
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
    return _por_serie(
        _com_zscore(consolidado, usar),
        _SERIE_DA_DISCIPLINA,
        estrato,
        _tendencia('zscore'),
        _COLUNAS_DA_TENDENCIA,
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
        return _spearman(serie.groupby('ordem')['zscore'].mean())

    return _por_serie(
        _com_zscore(consolidado, usar), _SERIE_DA_DISCIPLINA, estrato, calcular, ['rho', 'p_valor']
    )


def modelos_distintos(consolidado: pd.DataFrame) -> list[str]:
    """Modelos de correção presentes na base; mais de um pede cautela ao comparar níveis entre concursos."""
    return sorted(consolidado['modelo_correcao'].unique())


def percentual_por_topico(
    consolidado: pd.DataFrame, usar: str = 'ajustada', min_n: int = N_MINIMO_TOPICO, min_concursos: int = 1
) -> pd.DataFrame:
    """Uma linha por concurso e tópico (disciplina canônica + palavras-chave do nome): acertos, erros,
    brancos, n e percentual na versão `usar`, sem anuladas e sem truncar. O bloco não separa tópicos: o
    mesmo tópico nas provas geral e específica de um concurso é uma linha só.

    Tópicos sem mapeamento ficam fora; o nome exibido é o do concurso datado mais recente. Só ficam
    tópicos cobrados em pelo menos `min_concursos` concursos.
    """
    coluna = _coluna_de_pontos(usar)
    validas = _validas(consolidado)
    validas = validas[validas['chave_topico'].notna()]
    contagens = {f'{resultado}s': validas['resultado'].eq(resultado) for resultado in Resultado}
    tabela = (
        validas.assign(**contagens)
        .groupby(_TOPICO_NO_CONCURSO, dropna=False)
        .agg(
            topico=('topico', 'first'),
            n=('questao', 'size'),
            **{nome: (nome, 'sum') for nome in contagens},
            percentual=(coluna, 'mean'),
        )
        .reset_index()
    )
    tabela['percentual'] *= 100
    tabela = _por_ordem(tabela, [*contagens, 'percentual'], _LINHA_DO_TOPICO, min_n)
    mais_recente = tabela.sort_values('ordem', na_position='first').groupby('chave_topico')['topico'].last()
    tabela['topico'] = tabela['chave_topico'].map(mais_recente)
    concursos = tabela.groupby('chave_topico')['concurso'].transform('nunique')
    return tabela[concursos >= min_concursos].reset_index(drop=True)


def cobertura_edital(consolidado: pd.DataFrame, topicos_edital: pd.DataFrame) -> pd.DataFrame:
    """Por concurso: tópicos distintos do edital estruturado, quantos foram cobrados na prova (questão
    anulada também cobra) e quantos tópicos da prova não casam com nenhum do edital.

    O casamento é só pelas palavras-chave do nome do tópico, dentro do concurso, porque a disciplina da
    prova nem sempre repete a do edital. Pelo mesmo motivo, um tópico repetido em duas disciplinas do
    edital conta uma vez. Concurso sem edital estruturado fica sem percentual.
    """
    do_edital = _palavras_por_concurso(topicos_edital)
    da_prova = _palavras_por_concurso(consolidado[consolidado['topico'] != TOPICO_NAO_MAPEADO])
    concursos = consolidado.drop_duplicates('concurso')
    linhas = []
    for concurso, ordem in zip(concursos['concurso'], concursos['ordem'], strict=True):
        edital, prova = do_edital.get(concurso, set()), da_prova.get(concurso, set())
        linhas.append(
            {
                'concurso': concurso,
                'ordem': ordem,
                'topicos_edital': len(edital),
                'topicos_cobrados': len(edital & prova),
                'percentual_cobertura': 100 * len(edital & prova) / len(edital) if edital else np.nan,
                'topicos_fora_do_edital': len(prova - edital),
            }
        )
    return pd.DataFrame(linhas).sort_values(['ordem', 'concurso'], na_position='last', ignore_index=True)


def evolucao_por_topico(
    consolidado: pd.DataFrame,
    usar: str = 'ajustada',
    min_n: int = N_MINIMO_TOPICO,
    estrato: str | None = None,
) -> pd.DataFrame:
    """Slope do percentual de cada tópico ao longo da ordem (regressão linear), com p-value, pontos e n.

    Só contam concursos com data e pontos com n de pelo menos `min_n`; com menos de
    MINIMO_PONTOS_TENDENCIA, o tópico fica como amostra insuficiente, sem slope. Tópico nunca cobrado
    não tem linha.
    """
    return _por_serie(
        percentual_por_topico(consolidado, usar, min_n),
        _SERIE_DO_TOPICO,
        estrato,
        _tendencia('percentual'),
        _COLUNAS_DA_TENDENCIA,
    )


def topicos_fracos_persistentes(
    consolidado: pd.DataFrame,
    limiar: float = LIMIAR_TOPICO_FRACO,
    min_concursos: int = MINIMO_CONCURSOS,
    min_n: int = N_MINIMO_TOPICO,
    usar: str = 'ajustada',
) -> pd.DataFrame:
    """Tópicos abaixo do limiar (fração) em pelo menos `min_concursos` concursos, com acertos, erros e
    brancos somados entre concursos e n agregado de pelo menos `min_n`.

    O n de cada concurso não importa: com a mediana de 2 questões por tópico e prova, só a soma dá amostra.
    `concursos_abaixo` lista, em ordem cronológica, os concursos em que o tópico ficou abaixo do limiar.
    """
    por_concurso = percentual_por_topico(consolidado, usar)
    tabela = (
        por_concurso.assign(soma_percentual=por_concurso['percentual'] * por_concurso['n'])
        .groupby('chave_topico')
        .agg(
            disciplina=('disciplina', 'first'),
            topico=('topico', 'first'),
            concursos=('concurso', 'nunique'),
            n=('n', 'sum'),
            acertos=('acertos', 'sum'),
            erros=('erros', 'sum'),
            brancos=('brancos', 'sum'),
            soma_percentual=('soma_percentual', 'sum'),
        )
    )
    tabela['percentual'] = tabela['soma_percentual'] / tabela['n']
    abaixo = por_concurso[por_concurso['percentual'] < 100 * limiar]
    tabela['concursos_abaixo'] = abaixo.groupby('chave_topico')['concurso'].agg(list).reindex(tabela.index)
    fracos = tabela[(tabela['n'] >= min_n) & (tabela['concursos_abaixo'].str.len() >= min_concursos)]
    colunas = ['disciplina', 'topico', 'chave_topico', 'concursos', 'concursos_abaixo', 'n']
    return fracos.reset_index().sort_values(['percentual', 'n'], ascending=[True, False], ignore_index=True)[
        [*colunas, 'acertos', 'erros', 'brancos', 'percentual']
    ]


def _com_zscore(consolidado: pd.DataFrame, usar: str) -> pd.DataFrame:
    zscores = zscore_por_disciplina(consolidado, usar)
    return zscores[zscores['zscore'].notna()]


def _tendencia(coluna: str) -> Callable[[pd.DataFrame], dict]:
    def calcular(serie: pd.DataFrame) -> dict:
        if serie['ordem'].nunique() < MINIMO_PONTOS_TENDENCIA:
            return {'slope': np.nan, 'p_valor': np.nan, 'situacao': AMOSTRA_INSUFICIENTE}
        regressao = stats.linregress(serie['ordem'].astype(float), serie[coluna])
        return {'slope': regressao.slope, 'p_valor': regressao.pvalue, 'situacao': TENDENCIA}

    return calcular


def _palavras_por_concurso(tabela: pd.DataFrame) -> dict[str, set[str]]:
    return {
        concurso: {chave_de_palavras(topico) for topico in grupo['topico']}
        for concurso, grupo in tabela.groupby('concurso')
    }


def _por_serie(
    tabela: pd.DataFrame,
    chaves_da_serie: list[str],
    estrato: str | None,
    calcular: Callable[[pd.DataFrame], dict],
    colunas_calculadas: list[str],
) -> pd.DataFrame:
    """Uma linha por série (chaves e estrato) com algum concurso datado. Só os pontos sem amostra
    insuficiente entram no cálculo, nos pontos e no n; `n_total` soma todos os pontos datados."""
    if estrato not in ESTRATOS:
        raise ValueError(f"estrato: '{estrato}' inválido (use banca ou nenhum)")
    chaves = [*chaves_da_serie, *([estrato] if estrato else [])]
    linhas = []
    for chave, serie in tabela[tabela['ordem'].notna()].groupby(chaves, sort=True):
        suficientes = serie[~serie['amostra_insuficiente']]
        linhas.append(
            {
                **dict(zip(chaves, chave, strict=True)),
                'pontos': suficientes['ordem'].nunique(),
                'n': int(suficientes['n'].sum()),
                'n_total': int(serie['n'].sum()),
                **calcular(suficientes),
            }
        )
    tabela = pd.DataFrame(linhas, columns=[*chaves, 'pontos', 'n', 'n_total', *colunas_calculadas])
    return tabela.sort_values('p_valor', na_position='last', kind='stable', ignore_index=True)


def _spearman(por_ordem: pd.Series) -> dict:
    """rho e p entre o índice (ordem) e os valores; sem 3 pontos distintos, ambos ficam vazios."""
    if len(por_ordem) < MINIMO_PONTOS_TENDENCIA or por_ordem.nunique() < 2:
        return {'rho': np.nan, 'p_valor': np.nan}
    resultado = stats.spearmanr(por_ordem.index.astype(float), por_ordem.to_numpy())
    p_valor = (
        _p_spearman_exato(por_ordem.to_numpy())
        if len(por_ordem) <= MAXIMO_PONTOS_P_EXATO
        else float(resultado.pvalue)
    )
    return {'rho': float(resultado.statistic), 'p_valor': p_valor}


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


def _por_ordem(
    tabela: pd.DataFrame,
    colunas: list[str],
    linha: list[str] = _LINHA_DA_DISCIPLINA,
    min_n: int = N_MINIMO_TOPICO,
) -> pd.DataFrame:
    """Uma linha por `linha` (disciplina ou tópico no concurso), em ordem cronológica, com n e a marca de
    amostra insuficiente antes de `colunas`."""
    tabela = tabela.rename(columns={'disciplina_canonica': 'disciplina'})
    tabela['amostra_insuficiente'] = tabela['n'] < min_n
    ordenacao = ['ordem', *(chave for chave in linha if chave != 'ordem')]
    return tabela.sort_values(ordenacao, na_position='last', ignore_index=True)[
        [*linha, 'n', 'amostra_insuficiente', *colunas]
    ]
