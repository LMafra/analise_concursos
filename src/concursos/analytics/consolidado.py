"""Consolidado da análise evolutiva: uma linha por questão de todos os concursos analisados, cacheada em parquet."""

import logging
from enum import StrEnum
from pathlib import Path

import pandas as pd
from pandas.api import types

from concursos.analytics.correcao import ARQUIVO_CORRECAO, FonteCorrecao, aplicar_correcao, ler_correcao
from concursos.concurso_config import ARQUIVO_CONFIG, carregar_concurso
from concursos.consolidado import PASTA_CONSOLIDADO
from concursos.modelo import Escolaridade, Formato, ModeloCorrecao, Nivel, Resultado

logger = logging.getLogger(__name__)

ARQUIVO_PARQUET = 'consolidado.parquet'
ARQUIVO_QUESTOES = 'questoes.csv'
PREFIXO_PESO = 'peso__'
VARIANTE_PADRAO = 'padrao'

_TEXTO, _INTEIRO, _REAL, _LOGICO, _DATA = 'texto', 'inteiro', 'real', 'lógico', 'data'
COLUNAS = {
    'concurso': _TEXTO,
    'prova': _TEXTO,
    'questao': _INTEIRO,
    'disciplina': _TEXTO,
    'topico': _TEXTO,
    'gabarito': _TEXTO,
    'anulada': _LOGICO,
    'resposta': _TEXTO,
    'resultado': _TEXTO,
    'formato': _TEXTO,
    'banca': _TEXTO,
    'cargo': _TEXTO,
    'nivel': _TEXTO,
    'escolaridade': _TEXTO,
    'data_prova': _DATA,
    'ordem': _INTEIRO,
    'modelo_correcao': _TEXTO,
    'fator_penalidade': _REAL,
    'nota_maxima': _REAL,
    'nota_corte': _REAL,
    'fonte_correcao': _TEXTO,
    'confianca_correcao': _REAL,
    'pontos_bruta': _REAL,
    'pontos_corrigida': _REAL,
    'pontos_ajustada': _REAL,
    'n_topico': _INTEIRO,
}
DOMINIOS: dict[str, type[StrEnum]] = {
    'resultado': Resultado,
    'formato': Formato,
    'nivel': Nivel,
    'escolaridade': Escolaridade,
    'modelo_correcao': ModeloCorrecao,
    'fonte_correcao': FonteCorrecao,
}
_VERIFICA_TIPO = {
    _TEXTO: lambda serie: types.is_string_dtype(serie) or types.is_object_dtype(serie),
    _INTEIRO: types.is_integer_dtype,
    _REAL: types.is_float_dtype,
    _LOGICO: types.is_bool_dtype,
    _DATA: types.is_datetime64_any_dtype,
}
_CHAVE_TOPICO = ['concurso', 'prova', 'disciplina', 'topico']
CONFIANCA_MINIMA_SEM_AVISO = 0.8


class SchemaInvalidoError(ValueError):
    pass


def construir_consolidado(raiz_provas: Path, raiz_analises: Path) -> pd.DataFrame:
    """Junta as questões, a correção e os metadados de cada concurso com análise e arquivo de correção.

    O peso de cada item vem numa coluna por variante (`peso__<variante>`, ou `peso__padrao` sem
    variantes), vazia nos concursos que não têm aquela variante.
    """
    nomes = concursos_analisados(raiz_provas, raiz_analises)
    partes = [_questoes_do_concurso(raiz_provas / nome, raiz_analises / nome) for nome in nomes]
    if not partes:
        return pd.DataFrame(columns=list(COLUNAS))
    consolidado = pd.concat(partes, ignore_index=True)
    consolidado['data_prova'] = consolidado['data_prova'].astype('datetime64[ms]')
    consolidado['ordem'] = _ordem(consolidado)
    consolidado['n_topico'] = consolidado.groupby(_CHAVE_TOPICO, dropna=False)['questao'].transform('size')
    return consolidado[[*COLUNAS, *sorted(colunas_de_peso(consolidado))]]


def carregar_consolidado(raiz_provas: Path | None = None, raiz_analises: Path | None = None) -> pd.DataFrame:
    """Lê o parquet em cache ou o reconstrói quando alguma entrada (questões, correção, concurso.yaml) é mais
    nova que ele, ou quando o conjunto de concursos analisados mudou. Sem raízes, usa as do projeto."""
    raiz = raiz_do_projeto()
    raiz_provas, raiz_analises = raiz_provas or raiz / 'provas', raiz_analises or raiz / 'analises'
    cache = raiz_analises / PASTA_CONSOLIDADO / ARQUIVO_PARQUET
    nomes = concursos_analisados(raiz_provas, raiz_analises)
    if cache.exists() and not _alguma_mais_nova(cache, _entradas(raiz_provas, raiz_analises, nomes)):
        consolidado = pd.read_parquet(cache)
        if sorted(consolidado['concurso'].unique()) == nomes:
            return consolidado
    consolidado = construir_consolidado(raiz_provas, raiz_analises)
    cache.parent.mkdir(parents=True, exist_ok=True)
    consolidado.to_parquet(cache, index=False)
    logger.info('Consolidado de %d questões gravado em %s', len(consolidado), cache)
    return consolidado


def concursos_analisados(raiz_provas: Path, raiz_analises: Path) -> list[str]:
    if not raiz_analises.exists():
        return []
    return sorted(
        pasta.name
        for pasta in raiz_analises.iterdir()
        if (pasta / ARQUIVO_QUESTOES).exists()
        and (pasta / ARQUIVO_CORRECAO).exists()
        and (raiz_provas / pasta.name / ARQUIVO_CONFIG).exists()
    )


def contar_questoes(raiz_analises: Path) -> int:
    """Soma das linhas de todos os questoes.csv, inclusive de concursos que ficaram fora do consolidado."""
    return sum(len(pd.read_csv(arquivo)) for arquivo in raiz_analises.glob(f'*/{ARQUIVO_QUESTOES}'))


def validar_schema(consolidado: pd.DataFrame, linhas_esperadas: int) -> None:
    """Colunas, tipos, domínios e número de linhas; levanta SchemaInvalidoError com todos os problemas."""
    problemas = [f'coluna ausente: {coluna}' for coluna in COLUNAS if coluna not in consolidado]
    for coluna, tipo in COLUNAS.items():
        if coluna in consolidado and not _VERIFICA_TIPO[tipo](consolidado[coluna]):
            problemas.append(f'{coluna}: tipo {consolidado[coluna].dtype}, esperado {tipo}')
    for coluna, dominio in DOMINIOS.items():
        if coluna in consolidado:
            fora = sorted(set(consolidado[coluna].dropna()) - {item.value for item in dominio})
            if fora:
                problemas.append(f'{coluna}: valores fora do domínio {fora}')
    if not colunas_de_peso(consolidado):
        problemas.append(f'nenhuma coluna de peso ({PREFIXO_PESO}<variante>)')
    if len(consolidado) != linhas_esperadas:
        problemas.append(f'linhas: {len(consolidado)}, esperadas {linhas_esperadas}')
    if problemas:
        raise SchemaInvalidoError('consolidado inválido:\n- ' + '\n- '.join(problemas))


def avisos_do_consolidado(consolidado: pd.DataFrame) -> pd.DataFrame:
    """Concursos sem data, com regra de correção no default ou extraída com confiança baixa."""
    avisos = []
    for nome, concurso in _por_concurso(consolidado).iterrows():
        if pd.isna(concurso['data_prova']):
            avisos.append((nome, 'data', 'sem data da prova; fora das análises de tendência'))
        if concurso['fonte_correcao'] == FonteCorrecao.DEFAULT:
            avisos.append((nome, 'correcao', 'regra de correção no default (bruta, fator 0)'))
        elif concurso['confianca_correcao'] < CONFIANCA_MINIMA_SEM_AVISO:
            avisos.append(
                (
                    nome,
                    'correcao',
                    f'regra extraída com confiança {concurso["confianca_correcao"]:.2f}; confira o trecho',
                )
            )
    return pd.DataFrame(avisos, columns=['concurso', 'tipo', 'aviso'])


def perfil_por_concurso(consolidado: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por concurso, em ordem cronológica: metadados, n de questões e anuladas, correção e variantes."""
    pesos = colunas_de_peso(consolidado)
    contagens = consolidado.groupby('concurso').agg(questoes=('questao', 'size'), anuladas=('anulada', 'sum'))
    variantes = consolidado.groupby('concurso')[pesos].apply(lambda g: int(g.notna().any().sum()))
    colunas = [
        'banca',
        'formato',
        'escolaridade',
        'data_prova',
        'ordem',
        'modelo_correcao',
        'fator_penalidade',
        'nota_maxima',
        'fonte_correcao',
    ]
    perfil = _por_concurso(consolidado)[colunas].join(contagens).assign(variantes=variantes)
    return perfil.sort_values(['ordem', 'data_prova'], na_position='last').reset_index()


def colunas_de_peso(consolidado: pd.DataFrame) -> list[str]:
    return [coluna for coluna in consolidado.columns if coluna.startswith(PREFIXO_PESO)]


def _questoes_do_concurso(pasta_provas: Path, pasta_analise: Path) -> pd.DataFrame:
    config = carregar_concurso(pasta_provas)
    correcoes = ler_correcao(pasta_analise)
    questoes = pd.read_csv(
        pasta_analise / ARQUIVO_QUESTOES,
        keep_default_na=False,
        dtype={'prova': str, 'disciplina': str, 'topico': str, 'gabarito': str, 'resposta': str},
    )
    regra = correcoes[0]
    itens = aplicar_correcao(questoes, regra, config.formato).itens
    pesos = {
        f'{PREFIXO_PESO}{cfg.variante or VARIANTE_PADRAO}': questoes['questao'].map(cfg.peso_de).astype(float)
        for cfg in correcoes
    }
    return itens.assign(
        concurso=pasta_provas.name,
        formato=config.formato.value,
        banca=config.banca,
        cargo=config.cargo or '',
        nivel=config.nivel.value,
        escolaridade=config.escolaridade.value,
        data_prova=pd.Timestamp(regra.data_prova) if regra.data_prova else pd.NaT,
        modelo_correcao=regra.modelo.value,
        fator_penalidade=float(regra.fator_penalidade),
        nota_maxima=_real(regra.nota_maxima),
        nota_corte=_real(regra.nota_corte),
        fonte_correcao=regra.fonte.value,
        confianca_correcao=float(regra.confianca),
        **pesos,
    )


def _ordem(consolidado: pd.DataFrame) -> pd.Series:
    """Datas iguais empatam."""
    datas = _por_concurso(consolidado)['data_prova'].dropna()
    return consolidado['concurso'].map(datas.rank(method='dense')).astype('Int64')


def _por_concurso(consolidado: pd.DataFrame) -> pd.DataFrame:
    return consolidado.drop_duplicates('concurso').set_index('concurso')


def _entradas(raiz_provas: Path, raiz_analises: Path, nomes: list[str]) -> list[Path]:
    return [
        caminho
        for nome in nomes
        for caminho in (
            raiz_analises / nome / ARQUIVO_QUESTOES,
            raiz_analises / nome / ARQUIVO_CORRECAO,
            raiz_provas / nome / ARQUIVO_CONFIG,
        )
    ]


def _alguma_mais_nova(cache: Path, entradas: list[Path]) -> bool:
    limite = cache.stat().st_mtime
    return any(entrada.stat().st_mtime > limite for entrada in entradas)


def raiz_do_projeto() -> Path:
    for pasta in (Path.cwd(), *Path.cwd().parents):
        if (pasta / 'pyproject.toml').exists():
            return pasta
    return Path.cwd()


def _real(valor: float | None) -> float:
    return float('nan') if valor is None else float(valor)
