"""Métricas da análise evolutiva: funções puras sobre o consolidado (uma linha por questão)."""

import pandas as pd

from concursos.analytics.consolidado import PREFIXO_PESO, VARIANTE_PADRAO, colunas_de_peso

VERSOES = ('bruta', 'corrigida', 'ajustada')
VERSOES_COMPARADAS_AO_BRUTO = ('corrigida', 'ajustada')
_CASAS_NO_EMPATE = 9


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
