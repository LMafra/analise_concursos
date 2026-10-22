"""Apresentação para os notebooks; cada função recebe um DataFrame já calculado."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from plotly.colors import qualitative
from plotly.subplots import make_subplots

from concursos.analytics.consolidado import N_MINIMO_TOPICO
from concursos.analytics.evolucao import MINIMO_PONTOS_TENDENCIA

OPACIDADE_AMOSTRA_INSUFICIENTE = 0.35
TAMANHO_ROTULO_TOPICO = 50
_VERSOES_DO_PAINEL = (('bruta', 'bruto'), ('corrigida', 'corrigido'), ('ajustada', 'ajustado'))
ESCALA_PERCENTUAL = 'RdYlGn'
LIMITES_PERCENTUAL = (-100, 100)
DPI_EXPORTACAO = 120
_CORES_DOS_RESULTADOS = (('acertos', 'seagreen'), ('erros', 'indianred'), ('brancos', 'lightgray'))
_CORES_DO_GAP = ((True, 'no ritmo do corte', 'seagreen'), (False, 'abaixo do corte', 'indianred'))
_METRICAS_DA_LINHA = (('percentual', 'percentual'), ('zscore', 'z-score'))
_COLUNAS_DO_HOVER = ['concurso', 'banca', 'n']

# O Cursor e o VS Code sem a extensão de renderers não exibem o mimetype do plotly; HTML com o plotly.js do CDN
# funciona neles e no Jupyter.
RENDERIZADOR_NOTEBOOK = 'notebook_connected'
pio.renderers.default = RENDERIZADOR_NOTEBOOK


@dataclass(frozen=True)
class Resumo:
    """Tabela longa resumida para uma célula: o total, as primeiras linhas e, opcionalmente, contagens."""

    total: int
    primeiras: pd.DataFrame
    contagens: pd.Series | None = None

    def _repr_html_(self) -> str:
        partes = [f'<p>{self.total} linhas; mostrando {len(self.primeiras)}.</p>', self.primeiras.to_html()]
        if self.contagens is not None:
            partes.append(self.contagens.to_frame('n').to_html())
        return '\n'.join(partes)


@dataclass(frozen=True)
class Aviso:
    """Texto em markdown no topo de uma célula do notebook."""

    texto: str

    def _repr_markdown_(self) -> str:
        return self.texto


def aviso_modelos(modelos: list[str]) -> Aviso:
    """O aviso de `modelos_distintos`: comparar níveis entre modelos de correção distintos pede cautela."""
    if len(modelos) > 1:
        return Aviso(
            f'> **⚠ modelos de correção distintos** ({", ".join(modelos)}): compare níveis pelo ajustado ao '
            'acaso ou pelo z-score, nunca pelo bruto ou pelo corrigido.'
        )
    return Aviso(f'Um só modelo de correção na base ({", ".join(modelos)}).')


def painel_correcao(comparacao: pd.DataFrame) -> go.Figure:
    """Barras agrupadas de bruto, corrigido e ajustado por concurso (e variante), a partir da tabela de
    `comparar_bruto_vs_corrigido`, com modelo, fator e n no hover."""
    rotulos = _rotulos_da_comparacao(comparacao)
    detalhes = comparacao[['modelo_correcao', 'fator_penalidade', 'n']].to_numpy()
    figura = go.Figure()
    for versao, nome in _VERSOES_DO_PAINEL:
        figura.add_bar(
            name=nome,
            x=rotulos,
            y=comparacao[f'percentual_{versao}'],
            customdata=detalhes,
            hovertemplate=(
                f'%{{x}}<br>{nome}: %{{y:.1f}}%<br>'
                'modelo %{customdata[0]}, fator %{customdata[1]:g}<br>n = %{customdata[2]}<extra></extra>'
            ),
        )
    figura.update_layout(
        barmode='group',
        title='Percentual por concurso em cada versão da correção',
        yaxis_title='percentual (sem anuladas)',
        legend_title='versão',
    )
    return figura


def linha_evolucao(zscores: pd.DataFrame, estrato: str | None = None) -> go.Figure:
    """Percentual e z-score de cada disciplina ao longo da ordem, a partir de `zscore_por_disciplina`.

    Pontos com amostra insuficiente ficam soltos e transparentes, fora da linha contínua. Sem estrato, há
    uma série por disciplina com a banca como cor dos pontos; com `estrato='banca'`, uma linha por banca.
    Um menu filtra a disciplina, e o tamanho do ponto cresce com o n.
    """
    datadas = zscores[zscores['ordem'].notna()].sort_values('ordem').assign(rotulo=_rotulo_disciplina)
    cores = _cores_por_banca(datadas['banca'])
    figura = make_subplots(
        rows=2, cols=1, shared_xaxes=True, subplot_titles=[t for _, t in _METRICAS_DA_LINHA]
    )
    rotulos = sorted(datadas['rotulo'].unique())
    for rotulo in rotulos:
        disciplina = datadas[datadas['rotulo'] == rotulo]
        series = disciplina.groupby('banca') if estrato else [(rotulo, disciplina)]
        for nome, serie in series:
            for linha, (coluna, _) in enumerate(_METRICAS_DA_LINHA, start=1):
                for insuficiente, pontos in serie.groupby('amostra_insuficiente'):
                    figura.add_scatter(
                        **_pontos_da_linha(
                            pontos, coluna, cores, insuficiente, cor_da_linha=cores[nome] if estrato else None
                        ),
                        name=nome,
                        meta=rotulo,
                        legendgroup=nome,
                        showlegend=bool(estrato) and linha == 1 and not insuficiente,
                        visible=rotulo == rotulos[0],
                        row=linha,
                        col=1,
                    )
    figura.update_layout(
        title='Evolução por disciplina',
        updatemenus=[
            {
                'buttons': [
                    {
                        'label': rotulo,
                        'method': 'update',
                        'args': [{'visible': [t.meta == rotulo for t in figura.data]}],
                    }
                    for rotulo in rotulos
                ],
                'x': 1.0,
                'y': 1.15,
            }
        ],
    )
    figura.update_xaxes(title_text='ordem cronológica', row=2, col=1)
    return figura


def box_por_disciplina(zscores: pd.DataFrame, coluna: str = 'zscore') -> go.Figure:
    """Distribuição de cada disciplina entre concursos, com cada concurso como ponto sobreposto."""
    tabela = zscores.assign(rotulo=_rotulo_disciplina)
    figura = go.Figure()
    for rotulo, disciplina in tabela.groupby('rotulo', sort=True):
        figura.add_box(
            y=disciplina[coluna],
            name=rotulo,
            boxpoints='all',
            jitter=0.4,
            pointpos=0,
            customdata=disciplina[_COLUNAS_DO_HOVER].to_numpy(),
            hovertemplate=_hover('%{x}') + '<extra></extra>',
        )
    figura.update_layout(title=f'Distribuição por disciplina entre concursos ({coluna})', showlegend=False)
    return figura


def heatmap_topicos(percentuais: pd.DataFrame, min_n: int = N_MINIMO_TOPICO) -> go.Figure:
    """Tópicos (linhas, por disciplina) por concurso (colunas, em ordem cronológica), a partir de
    `percentual_por_topico`. Só as células com n ≥ `min_n` têm cor e percentual anotado; as outras ficam
    cinza com "n<`min_n`", e as de tópico não cobrado, em branco."""
    grade = _GradeDeTopicos.de(percentuais, min_n)
    eixos_e_n = {'x': grade.concursos, 'y': grade.rotulos, 'customdata': grade.n, 'xgap': 1}
    figura = go.Figure()
    figura.add_heatmap(
        **eixos_e_n,
        colorscale=ESCALA_PERCENTUAL,
        zmin=LIMITES_PERCENTUAL[0],
        zmax=LIMITES_PERCENTUAL[1],
        z=grade.percentual,
        text=grade.textos_percentual,
        texttemplate='%{text}',
        colorbar={'title': '%'},
        hovertemplate='%{y}<br>%{x}: %{z:.0f}%<br>n = %{customdata}<extra></extra>',
    )
    figura.add_heatmap(
        **eixos_e_n,
        z=np.where(grade.insuficiente, 1.0, np.nan),
        text=grade.textos_insuficiente,
        texttemplate='%{text}',
        colorscale=[[0, 'lightgray'], [1, 'lightgray']],
        showscale=False,
        hovertemplate='%{y}<br>%{x}: n = %{customdata}<extra></extra>',
    )
    figura.update_layout(
        title='Percentual por tópico e concurso',
        height=200 + 22 * len(grade.rotulos),
        yaxis={'autorange': 'reversed'},
    )
    return figura


def barras_fracos(fracos: pd.DataFrame) -> go.Figure:
    """Barras horizontais empilhadas de acertos, erros e brancos somados entre concursos, a partir de
    `topicos_fracos_persistentes`, com o n anotado e os concursos abaixo do limiar no hover."""
    tabela = fracos.assign(rotulo=_rotulo_topico)
    detalhes = np.column_stack([tabela['concursos_abaixo'].map(', '.join), tabela['percentual']])
    figura = go.Figure()
    for coluna, cor in _CORES_DOS_RESULTADOS:
        figura.add_bar(
            name=coluna,
            x=tabela[coluna],
            y=tabela['rotulo'],
            orientation='h',
            marker_color=cor,
            customdata=detalhes,
            hovertemplate=(
                f'%{{y}}<br>{coluna}: %{{x}}<br>percentual %{{customdata[1]:.0f}}%<br>'
                'abaixo do limiar em %{customdata[0]}<extra></extra>'
            ),
        )
    for rotulo, n in zip(tabela['rotulo'], tabela['n'], strict=True):
        figura.add_annotation(x=n, y=rotulo, text=f'n = {n}', xanchor='left', showarrow=False)
    figura.update_layout(
        barmode='stack',
        title='Tópicos fracos persistentes',
        xaxis_title='questões somadas entre concursos',
        yaxis={'autorange': 'reversed'},
        height=200 + 30 * len(tabela),
    )
    return figura


def barras_gap_por_disciplina(gaps: pd.DataFrame) -> go.Figure:
    """Barras horizontais do gap percentual de cada disciplina, a partir de `gap_por_disciplina`, coloridas
    por `no_ritmo` e transparentes com amostra insuficiente, com o percentual, a exigência, o que falta e o n
    no hover."""
    tabela = gaps.assign(rotulo=_rotulo_do_gap)
    figura = go.Figure()
    for no_ritmo, nome, cor in _CORES_DO_GAP:
        parte = tabela[tabela['no_ritmo'] == no_ritmo]
        if parte.empty:
            continue
        figura.add_bar(
            name=nome,
            x=parte['gap_percentual'],
            y=parte['rotulo'],
            orientation='h',
            marker={
                'color': cor,
                'opacity': parte['amostra_suficiente'].map(
                    {True: 1.0, False: OPACIDADE_AMOSTRA_INSUFICIENTE}
                ),
            },
            customdata=parte[['percentual', 'exigido', 'falta', 'unidade', 'n']].to_numpy(),
            hovertemplate=(
                '%{y}<br>gap %{x:+.1f} p.p.<br>%{customdata[0]:.1f}% contra %{customdata[1]:.1f}% exigidos'
                '<br>falta %{customdata[2]:.1f} %{customdata[3]}<br>n = %{customdata[4]}<extra></extra>'
            ),
        )
    figura.update_layout(
        title='Gap para o corte por disciplina',
        xaxis_title='gap (pontos percentuais da nota máxima da disciplina)',
        yaxis={'autorange': 'reversed', 'categoryorder': 'array', 'categoryarray': list(tabela['rotulo'])},
        height=200 + 25 * len(tabela),
    )
    return figura


def _rotulo_do_gap(tabela: pd.DataFrame) -> pd.Series:
    concursos = [
        rotulo_com_variante(c, v) for c, v in zip(tabela['concurso'], tabela['variante'], strict=True)
    ]
    return pd.Series(concursos, index=tabela.index) + ' · ' + tabela['disciplina']


def rotulo_com_variante(concurso: str, variante: object) -> str:
    return concurso if pd.isna(variante) else f'{concurso} ({variante})'


def exportar_linha_evolucao(
    zscores: pd.DataFrame, caminho: Path, min_pontos: int = MINIMO_PONTOS_TENDENCIA
) -> Figure:
    """PNG do z-score ao longo da ordem, a partir de `zscore_por_disciplina`, só das disciplinas com pelo
    menos `min_pontos` concursos de n suficiente (as que podem ter tendência). Pontos com amostra
    insuficiente ficam soltos e vazados."""
    datadas = zscores[zscores['ordem'].notna() & zscores['zscore'].notna()].sort_values('ordem')
    datadas = datadas.assign(rotulo=_rotulo_disciplina)
    suficientes = datadas[~datadas['amostra_insuficiente']]
    pontos = suficientes.groupby('rotulo')['ordem'].nunique()
    figura = Figure(figsize=(10, 6))
    eixo = figura.subplots()
    eixo.axhline(0, color='gray', linewidth=0.8)
    for rotulo in sorted(pontos[pontos >= min_pontos].index):
        serie = suficientes[suficientes['rotulo'] == rotulo]
        (linha,) = eixo.plot(serie['ordem'].astype(int), serie['zscore'], marker='o', label=rotulo)
        soltos = datadas[(datadas['rotulo'] == rotulo) & datadas['amostra_insuficiente']]
        eixo.scatter(
            soltos['ordem'].astype(int), soltos['zscore'], facecolors='none', edgecolors=linha.get_color()
        )
    eixo.set(
        xlabel='ordem cronológica',
        ylabel='z-score',
        title=(
            f'Evolução do z-score por disciplina ({min_pontos} concursos ou mais com n ≥ {N_MINIMO_TOPICO})'
        ),
    )
    if (pontos >= min_pontos).any():
        eixo.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=8)
    else:
        eixo.text(
            0.5, 0.5, 'nenhuma disciplina com pontos suficientes', transform=eixo.transAxes, ha='center'
        )
    return _salvar(figura, caminho)


def exportar_heatmap_topicos(
    percentuais: pd.DataFrame, caminho: Path, min_n: int = N_MINIMO_TOPICO
) -> Figure:
    """PNG do heatmap de `heatmap_topicos`, com as mesmas regras de anotação."""
    grade = _GradeDeTopicos.de(percentuais, min_n)
    figura = Figure(figsize=(2 + 0.9 * len(grade.concursos), 1.5 + 0.35 * len(grade.rotulos)))
    eixo = figura.subplots()
    eixo.imshow(np.where(grade.insuficiente, 1.0, np.nan), cmap=ListedColormap(['lightgray']), aspect='auto')
    minimo, maximo = LIMITES_PERCENTUAL
    imagem = eixo.imshow(grade.percentual, cmap=ESCALA_PERCENTUAL, vmin=minimo, vmax=maximo, aspect='auto')
    figura.colorbar(imagem, ax=eixo, label='%')
    for textos in (grade.textos_percentual, grade.textos_insuficiente):
        for (linha, coluna), texto in np.ndenumerate(np.array(textos, dtype=object)):
            if texto:
                eixo.text(coluna, linha, texto, ha='center', va='center', fontsize=8)
    eixo.set_xticks(range(len(grade.concursos)), grade.concursos, rotation=45, ha='right')
    eixo.set_yticks(range(len(grade.rotulos)), grade.rotulos, fontsize=8)
    eixo.set_title('Percentual por tópico e concurso')
    return _salvar(figura, caminho)


def exportar_painel_correcao(comparacao: pd.DataFrame, caminho: Path) -> Figure:
    """PNG das barras de `painel_correcao`: bruto, corrigido e ajustado por concurso e variante."""
    rotulos = _rotulos_da_comparacao(comparacao)
    posicoes = np.arange(len(rotulos))
    largura = 0.8 / len(_VERSOES_DO_PAINEL)
    figura = Figure(figsize=(max(6, 0.9 * len(rotulos)), 5))
    eixo = figura.subplots()
    for i, (versao, nome) in enumerate(_VERSOES_DO_PAINEL):
        eixo.bar(posicoes + (i - 1) * largura, comparacao[f'percentual_{versao}'], largura, label=nome)
    eixo.axhline(0, color='gray', linewidth=0.8)
    eixo.set_xticks(posicoes, rotulos, rotation=45, ha='right')
    eixo.set(ylabel='percentual (sem anuladas)', title='Percentual por concurso em cada versão da correção')
    eixo.legend(title='versão')
    return _salvar(figura, caminho)


@dataclass(frozen=True)
class _GradeDeTopicos:
    """Tópicos por concursos: percentual só onde n ≥ min_n e texto de n pequeno onde há questões de menos."""

    concursos: list[str]
    rotulos: list[str]
    n: np.ndarray
    percentual: np.ndarray
    insuficiente: np.ndarray
    textos_percentual: list[list[str]]
    textos_insuficiente: list[list[str]]

    @classmethod
    def de(cls, percentuais: pd.DataFrame, min_n: int) -> '_GradeDeTopicos':
        tabela = percentuais.sort_values(['disciplina', 'topico']).assign(rotulo=_rotulo_topico)
        concursos = (
            tabela.sort_values(['ordem', 'concurso'], na_position='last')['concurso'].unique().tolist()
        )
        topicos = tabela.drop_duplicates('chave_topico')

        def grade(coluna: str) -> np.ndarray:
            return (
                tabela.pivot(index='chave_topico', columns='concurso', values=coluna)
                .reindex(index=topicos['chave_topico'], columns=concursos)
                .to_numpy(dtype=float)
            )

        n = grade('n')
        percentual = grade('percentual')
        insuficiente = n < min_n
        return cls(
            concursos=concursos,
            rotulos=topicos['rotulo'].tolist(),
            n=n,
            percentual=np.where(n >= min_n, percentual, np.nan),
            insuficiente=insuficiente,
            textos_percentual=np.where(
                n >= min_n, np.char.mod('%.0f%%', np.nan_to_num(percentual)), ''
            ).tolist(),
            textos_insuficiente=np.where(insuficiente, f'n<{min_n}', '').tolist(),
        )


def _salvar(figura: Figure, caminho: Path) -> Figure:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(caminho, dpi=DPI_EXPORTACAO, bbox_inches='tight')
    return figura


def _rotulos_da_comparacao(comparacao: pd.DataFrame) -> list[str]:
    return [
        f'{concurso} ({variante})' if pd.notna(variante) else concurso
        for concurso, variante in zip(comparacao['concurso'], comparacao['variante'], strict=True)
    ]


def _pontos_da_linha(
    pontos: pd.DataFrame, coluna: str, cores: dict[str, str], insuficiente: bool, cor_da_linha: str | None
) -> dict:
    marcador = {
        'size': 6 + 2 * np.sqrt(pontos['n'].to_numpy()),
        'color': [cores[banca] for banca in pontos['banca']],
        'opacity': OPACIDADE_AMOSTRA_INSUFICIENTE if insuficiente else 1.0,
    }
    return {
        'x': pontos['ordem'].astype(int),
        'y': pontos[coluna],
        'mode': 'markers' if insuficiente else 'lines+markers',
        'marker': marcador,
        'line': {'color': cor_da_linha or 'gray'},
        'customdata': pontos[_COLUNAS_DO_HOVER].to_numpy(),
        'hovertemplate': _hover('ordem %{x}') + '<extra>%{meta}</extra>',
    }


def _hover(eixo_x: str) -> str:
    """Concurso, banca e n vêm de `customdata`, na ordem de _COLUNAS_DO_HOVER."""
    return f'%{{customdata[0]}} (%{{customdata[1]}})<br>{eixo_x}: %{{y:.2f}}<br>n = %{{customdata[2]}}'


def _rotulo_disciplina(tabela: pd.DataFrame) -> pd.Series:
    return tabela['disciplina'] + ' (' + tabela['bloco'] + ')'


def _rotulo_topico(tabela: pd.DataFrame) -> pd.Series:
    topico = tabela['topico'].where(
        tabela['topico'].str.len() <= TAMANHO_ROTULO_TOPICO,
        tabela['topico'].str.slice(0, TAMANHO_ROTULO_TOPICO - 1) + '…',
    )
    return topico + ' (' + tabela['disciplina'] + ')'


def _cores_por_banca(bancas: pd.Series) -> dict[str, str]:
    return {
        banca: qualitative.Plotly[i % len(qualitative.Plotly)]
        for i, banca in enumerate(sorted(bancas.unique()))
    }


def resumir(tabela: pd.DataFrame, n: int = 10, contar: str | None = None) -> Resumo:
    contagens = tabela[contar].value_counts(sort=False) if contar else None
    return Resumo(len(tabela), tabela.head(n), contagens)
