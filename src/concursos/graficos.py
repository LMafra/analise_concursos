from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from concursos.correcao import TOPICO_NAO_MAPEADO  # noqa: E402

PASTA_GRAFICOS = 'graficos'
MAXIMO_TOPICOS = 25
_ALTURA_POR_BARRA = 0.35


def gerar_graficos(por_disciplina: pd.DataFrame, por_topico: pd.DataFrame, destino: Path) -> dict[str, str]:
    """Gráficos de barras do percentual de acertos; devolve título → caminho relativo ao destino."""
    pasta = destino / PASTA_GRAFICOS
    pasta.mkdir(parents=True, exist_ok=True)
    rotulos_disciplina = _rotulos(por_disciplina, ['disciplina'])
    topicos = por_topico[por_topico['topico'] != TOPICO_NAO_MAPEADO].nsmallest(MAXIMO_TOPICOS, 'percentual')
    graficos = {
        'Desempenho por disciplina': ('desempenho_por_disciplina.png', por_disciplina, rotulos_disciplina),
        f'Tópicos com menor desempenho (até {MAXIMO_TOPICOS})': (
            'desempenho_por_topico.png',
            topicos,
            _rotulos(topicos, ['disciplina', 'topico']),
        ),
    }
    gerados = {}
    for titulo, (arquivo, dados, rotulos) in graficos.items():
        _barras(dados['percentual'].tolist(), rotulos, titulo, pasta / arquivo)
        gerados[titulo] = f'{PASTA_GRAFICOS}/{arquivo}'
    return gerados


def _rotulos(dados: pd.DataFrame, colunas: list[str]) -> list[str]:
    varias_provas = dados['prova'].nunique() > 1 if not dados.empty else False
    prefixo = ['prova'] if varias_provas else []
    return [
        ' · '.join(_encurtar(str(v)) for v in linha)
        for linha in dados[prefixo + colunas].itertuples(index=False)
    ]


def _encurtar(texto: str, limite: int = 50) -> str:
    return texto if len(texto) <= limite else texto[: limite - 1] + '…'


def _barras(valores: list[float], rotulos: list[str], titulo: str, caminho: Path) -> None:
    figura, eixo = plt.subplots(figsize=(10, max(2.5, _ALTURA_POR_BARRA * len(valores) + 1.2)))
    try:
        if valores:
            posicoes = range(len(valores))
            cores = ['#c0392b' if v < 50 else '#e67e22' if v < 70 else '#27ae60' for v in valores]
            eixo.barh(posicoes, valores, color=cores)
            eixo.set_yticks(list(posicoes), rotulos, fontsize=8)
            eixo.invert_yaxis()
            for posicao, valor in zip(posicoes, valores, strict=True):
                eixo.text(valor + 1, posicao, f'{valor:g}%', va='center', fontsize=7)
        else:
            eixo.text(0.5, 0.5, 'Sem dados', ha='center', va='center', transform=eixo.transAxes)
            eixo.set_yticks([])
        eixo.set_xlim(0, 105)
        eixo.set_xlabel('% de acertos (sem anuladas)')
        eixo.set_title(titulo)
        figura.tight_layout()
        figura.savefig(caminho, dpi=110)
    finally:
        plt.close(figura)
