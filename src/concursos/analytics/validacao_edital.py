"""Validação edital × prova × gabarito: o que o edital promete contra o que a prova entregou."""

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

import pandas as pd

from concursos.analytics.correcao import ConfiguracaoCorrecao
from concursos.analytics.regras_edital import Distribuicao, Pesos, RegrasEdital, TipoPeso
from concursos.analytics.taxonomia import BLOCO_DA_PROVA, DisciplinaCanonica
from concursos.concurso_config import ConcursoConfig, PesoItens, peso_da_questao
from concursos.modelo import Bloco

ARQUIVO_DISCREPANCIAS = 'discrepancias_edital.csv'
COLUNAS_DISCREPANCIAS = [
    'item',
    'esperado_edital',
    'observado_prova',
    'diferenca',
    'severidade',
    'acao_sugerida',
]


class Severidade(StrEnum):
    INFO = 'info'
    WARN = 'warn'
    ERROR = 'error'


@dataclass(frozen=True)
class Discrepancia:
    item: str
    esperado_edital: str
    observado_prova: str
    diferenca: float | None
    severidade: Severidade
    acao_sugerida: str


def validar_edital(
    config: ConcursoConfig,
    regras: RegrasEdital,
    questoes: pd.DataFrame | None = None,
    taxonomia: dict[str, DisciplinaCanonica] | None = None,
    correcoes: list[ConfiguracaoCorrecao] | None = None,
) -> pd.DataFrame:
    """Uma linha por divergência, com severidade e ação sugerida; vazia quando tudo confere. `questoes` tem
    uma linha por questão do concurso, com `prova` e `disciplina`; a `taxonomia` casa as disciplinas do
    edital com as das questões pela disciplina canônica e dá o bloco na prova única. As `correcoes` (uma por
    variante) têm os pesos realizados."""
    discrepancias = [*_cargo(config, regras), *_soma_dos_eixos(regras.pesos), *_data_da_prova(config, regras)]
    if correcoes is not None:
        discrepancias += _pesos_realizados(config, regras.pesos, correcoes)
    if questoes is not None:
        discrepancias += _contagens(regras.distribuicao, questoes, taxonomia or {})
    return pd.DataFrame([asdict(d) for d in discrepancias], columns=COLUNAS_DISCREPANCIAS)


def gravar_discrepancias(discrepancias: pd.DataFrame, destino: Path) -> None:
    discrepancias.to_csv(destino / ARQUIVO_DISCREPANCIAS, index=False)


def _cargo(config: ConcursoConfig, regras: RegrasEdital) -> list[Discrepancia]:
    identificacao = regras.identificacao
    if identificacao.cargo_casado or not identificacao.cargos_do_edital:
        return []
    return [
        Discrepancia(
            'cargo',
            '; '.join(identificacao.cargos_do_edital),
            config.cargo or '',
            None,
            Severidade.WARN,
            'Corrija o cargo no concurso.yaml com o nome (ou número) do cargo no edital; '
            'sem casamento, cortes e distribuição são lidos do concurso inteiro',
        )
    ]


def _data_da_prova(config: ConcursoConfig, regras: RegrasEdital) -> list[Discrepancia]:
    edital = regras.cronograma.objetiva.valor
    if config.data_prova is None or edital is None or config.data_prova == edital:
        return []
    return [
        Discrepancia(
            'data da prova objetiva',
            edital.isoformat(),
            config.data_prova.isoformat(),
            (config.data_prova - edital).days,
            Severidade.INFO,
            'Vale a data do concurso.yaml; confira se uma retificação mudou a data do edital',
        )
    ]


def _soma_dos_eixos(pesos: Pesos) -> list[Discrepancia]:
    declarada = pesos.soma_dos_eixos.valor
    if pesos.tipo.valor is not TipoPeso.POR_FAIXA_DE_ITENS or declarada is None:
        return []
    somas = {variante: sum(f.peso for f in campo.valor[1:]) for variante, campo in pesos.faixas.items()}
    return [
        _divergencia(
            f'soma dos pesos dos eixos: {variante}',
            declarada,
            soma,
            Severidade.ERROR,
            'Confira a linha da variante no quadro de pesos dos eixos do edital',
        )
        for variante, soma in somas.items()
        if soma != declarada
    ]


def _pesos_realizados(
    config: ConcursoConfig, pesos: Pesos, correcoes: list[ConfiguracaoCorrecao]
) -> list[Discrepancia]:
    """O peso de cada item no edital contra o do correcao.json; uma variante fora do quadro de eixos não é
    comparada."""
    if pesos.tipo.valor is None:
        return []
    divergencias = []
    for cfg in correcoes:
        variante = cfg.variante or ''
        if variante in pesos.faixas:
            esperado = pesos.faixas[variante].valor
        elif pesos.tipo.valor is TipoPeso.POR_FAIXA_DE_ITENS:
            continue
        else:
            esperado = ()
        itens = range(1, config.total_itens + 1)
        if any(peso_da_questao(esperado, q) != peso_da_questao(cfg.pesos, q) for q in itens):
            divergencias.append(
                Discrepancia(
                    f'pesos dos itens: {variante}' if variante else 'pesos dos itens',
                    _faixas(esperado),
                    _faixas(cfg.pesos),
                    None,
                    Severidade.WARN,
                    'A nota usa o realizado (correcao.json); '
                    'confira os pesos do concurso.yaml contra o edital',
                )
            )
    return divergencias


def _faixas(pesos: tuple[PesoItens, ...]) -> str:
    return '; '.join(f'{f.inicio}-{f.fim}: {f.peso:g}' for f in pesos) or 'todos os itens: 1'


def _contagens(
    distribuicao: Distribuicao, questoes: pd.DataFrame, taxonomia: dict[str, DisciplinaCanonica]
) -> list[Discrepancia]:
    divergencias = []
    total = distribuicao.total.valor
    if total is not None and total != len(questoes):
        divergencias.append(
            _divergencia(
                'total de itens',
                total,
                len(questoes),
                Severidade.ERROR,
                'Confira as faixas de itens das provas no concurso.yaml e o gabarito',
            )
        )
    blocos = _blocos_observados(questoes, taxonomia)
    rotulos = {
        Bloco.GERAL: 'itens de conhecimentos gerais',
        Bloco.ESPECIFICO: 'itens de conhecimentos específicos',
    }
    for bloco, campo in ((Bloco.GERAL, distribuicao.geral), (Bloco.ESPECIFICO, distribuicao.especifico)):
        if blocos is not None and campo.valor is not None and campo.valor != blocos.get(bloco, 0):
            divergencias.append(
                _divergencia(
                    rotulos[bloco],
                    campo.valor,
                    blocos.get(bloco, 0),
                    Severidade.ERROR,
                    'Confira as faixas de itens das provas e o bloco das disciplinas na taxonomia',
                )
            )
    if distribuicao.por_disciplina.valor:

        def canonica(nome: str) -> str:
            return taxonomia[nome].nome if nome in taxonomia else nome

        observadas = questoes['disciplina'].map(canonica).value_counts()
        for nome, esperado in distribuicao.por_disciplina.valor.items():
            observado = int(observadas.get(canonica(nome), 0))
            if observado != esperado:
                divergencias.append(
                    _divergencia(
                        f'disciplina: {nome}',
                        esperado,
                        observado,
                        Severidade.WARN,
                        'Revise as faixas de disciplina do concurso.yaml e, se o nome do edital for outro, '
                        'acrescente-o à disciplina canônica na taxonomia',
                    )
                )
    return divergencias


def _blocos_observados(questoes: pd.DataFrame, taxonomia: dict[str, DisciplinaCanonica]) -> dict | None:
    """Questões por bloco: pela prova nas provas divididas, pela taxonomia na prova única; nenhum quando
    alguma questão fica sem bloco conhecido."""
    blocos = questoes['prova'].map(BLOCO_DA_PROVA)
    if blocos.isna().any():
        if questoes['prova'].nunique() != 1:
            return None
        blocos = questoes['disciplina'].map(lambda nome: taxonomia[nome].bloco if nome in taxonomia else None)
        if blocos.isna().any():
            return None
    return blocos.value_counts().to_dict()


def _divergencia(
    item: str, esperado: float, observado: float, severidade: Severidade, acao: str
) -> Discrepancia:
    return Discrepancia(item, f'{esperado:g}', f'{observado:g}', observado - esperado, severidade, acao)
