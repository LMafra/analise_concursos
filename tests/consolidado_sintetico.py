"""Consolidado em memória para os testes de análise: uma linha por questão, já pontuada."""

import pandas as pd

ALTERNATIVAS = {'certo_errado': 2, 'multipla_escolha': 5}


def concurso(
    nome: str,
    resultados: list[str],
    formato: str = 'certo_errado',
    anuladas: tuple[int, ...] = (),
    pesos: dict[str, list[float]] | None = None,
    ordem: int | None = None,
    disciplinas: list[str] | None = None,
    blocos: list[str] | None = None,
    topicos: list[str] | None = None,
    banca: str | None = None,
    escolaridade: str = 'superior',
) -> pd.DataFrame:
    """Linhas mínimas do consolidado: Cebraspe líquida (fator 1) ou FGV bruta, com pontuação por item."""
    fator = 1.0 if formato == 'certo_errado' else 0.0
    k = ALTERNATIVAS[formato]
    anulada = [i + 1 in anuladas for i in range(len(resultados))]
    pontos = {
        'bruta': {'acerto': 1.0, 'erro': 0.0, 'branco': 0.0},
        'corrigida': {'acerto': 1.0, 'erro': -fator, 'branco': 0.0},
        'ajustada': {'acerto': 1.0, 'erro': -1 / (k - 1), 'branco': 0.0},
    }
    tabela = pd.DataFrame(
        {
            'concurso': nome,
            'banca': banca or ('cebraspe' if formato == 'certo_errado' else 'fgv'),
            'escolaridade': escolaridade,
            'prova': 'unica',
            'questao': range(1, len(resultados) + 1),
            'disciplina_canonica': disciplinas or ['Português'] * len(resultados),
            'bloco': blocos or ['geral'] * len(resultados),
            'topico': topicos or ['Crase'] * len(resultados),
            'anulada': anulada,
            'resultado': resultados,
            'modelo_correcao': 'liquida' if fator else ('ponderada' if pesos else 'bruta'),
            'fator_penalidade': fator,
            'nota_maxima': float(len(resultados)),
            'ordem': pd.array([ordem] * len(resultados), dtype='Int64'),
        }
    )
    tabela['disciplina'] = tabela['disciplina_canonica']
    tabela['chave_topico'] = (tabela['disciplina_canonica'] + ' | ' + tabela['topico']).mask(
        tabela['topico'] == 'nao_mapeado'
    )
    for versao, valores in pontos.items():
        tabela[f'pontos_{versao}'] = tabela['resultado'].map(valores).mask(tabela['anulada'])
    for variante, valores in (pesos or {'padrao': [1.0] * len(resultados)}).items():
        tabela[f'peso__{variante}'] = valores
    return tabela


def consolidado(*concursos: pd.DataFrame) -> pd.DataFrame:
    return pd.concat(concursos, ignore_index=True)
