"""O painel de gestão do `index.html`: status de cada prova, cards, pontos fortes e a melhorar, frase de
evolução e ações sugeridas. Funções puras, sem HTML; as regras estão em `docs/spec-linguagem.md`."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import pandas as pd

from concursos.analytics.consolidado import N_MINIMO_TOPICO
from concursos.analytics.evolucao import MINIMO_PONTOS_TENDENCIA, TENDENCIA, Correlacao
from concursos.analytics.insights import P_SIGNIFICATIVO
from concursos.correcao import TOPICO_NAO_MAPEADO
from concursos.linguagem import percentual, plural
from concursos.modelo import Resultado

FAIXA_NO_LIMITE = 2.0
RHO_LEVE = 0.3
MAXIMO_FORTES = 5
MAXIMO_ACOES = 5


class StatusProva(StrEnum):
    ACIMA = 'acima'
    LIMITE = 'limite'
    ABAIXO = 'abaixo'
    SEM_CORTE = 'sem_corte'
    NAO_CALCULAVEL = 'nao_calculavel'


def status_da_prova(gap: float | None, atingido: bool | None, corte_calculavel: bool = True) -> StatusProva:
    """Pelo corte mais distante (gap = nota − corte, em p.p.): a até `FAIXA_NO_LIMITE` de distância, no
    limite; fora dela, o "atingido" de todos os cortes decide."""
    if gap is None or pd.isna(gap):
        return StatusProva.SEM_CORTE if corte_calculavel else StatusProva.NAO_CALCULAVEL
    if abs(gap) <= FAIXA_NO_LIMITE:
        return StatusProva.LIMITE
    return StatusProva.ACIMA if atingido else StatusProva.ABAIXO


@dataclass(frozen=True)
class Prova:
    """Uma prova é um concurso, ou uma opção de cargo (variante) de um concurso."""

    concurso: str
    titulo: str
    percentual: float
    variante: str | None = None
    data: str | None = None
    gap: float | None = None
    atingido: bool | None = None
    corte_calculavel: bool = True

    @property
    def status(self) -> StatusProva:
        return status_da_prova(self.gap, self.atingido, self.corte_calculavel)

    @property
    def rotulo(self) -> str:
        return f'{self.titulo} ({self.variante})' if self.variante else self.titulo

    @property
    def quanto_falta(self) -> str:
        if self.gap is None or pd.isna(self.gap):
            return ''
        if self.gap < 0:
            return f'faltam {_pp(-self.gap)}'
        return f'+{_pp(self.gap)} de folga'


@dataclass(frozen=True)
class Tendencia:
    chave: str
    rotulo: str
    icone: str
    frase: str


def tendencia_geral(correlacao: Correlacao | None) -> Tendencia:
    """Melhorando ou piorando só com p < 0,05; sem significância, "leve" a partir de |ρ| = `RHO_LEVE`."""
    if correlacao is None or correlacao.pontos < MINIMO_PONTOS_TENDENCIA or pd.isna(correlacao.rho):
        return Tendencia(
            'indefinida',
            'Ainda não dá para afirmar',
            '–',
            'Ainda não dá para afirmar se você está melhorando ou piorando: são poucos concursos com data.',
        )
    subindo = correlacao.rho > 0
    if correlacao.p_valor < P_SIGNIFICATIVO:
        if subindo:
            return Tendencia('melhorando', 'Melhorando', '↑', 'Seu desempenho geral está melhorando.')
        return Tendencia('piorando', 'Piorando', '↓', 'Seu desempenho geral está piorando.')
    if abs(correlacao.rho) >= RHO_LEVE:
        if subindo:
            return Tendencia(
                'leve_alta', 'Leve alta', '↗', 'Leve tendência de alta, ainda dentro da variação normal.'
            )
        return Tendencia(
            'leve_queda', 'Leve queda', '↘', 'Leve tendência de queda, ainda dentro da variação normal.'
        )
    return Tendencia('estavel', 'Estável', '→', 'Seu desempenho geral está estável.')


@dataclass(frozen=True)
class SituacaoDaDisciplina:
    disciplina: str
    situacao: str


def situacao_por_disciplina(tendencias: pd.DataFrame) -> list[SituacaoDaDisciplina]:
    """Só as disciplinas com tendência calculável; "melhorando" e "precisa de atenção" exigem p < 0,05."""
    if tendencias.empty:
        return []
    com_tendencia = tendencias[tendencias['situacao'] == TENDENCIA]
    situacoes = []
    for linha in com_tendencia.sort_values('disciplina').itertuples():
        significativa = linha.p_valor < P_SIGNIFICATIVO
        if significativa and linha.slope > 0:
            situacao = 'melhorando'
        elif significativa and linha.slope < 0:
            situacao = 'precisa de atenção'
        else:
            situacao = 'estável'
        situacoes.append(SituacaoDaDisciplina(str(linha.disciplina), situacao))
    return situacoes


def frase_de_evolucao(situacoes: list[SituacaoDaDisciplina]) -> str:
    if not situacoes:
        return 'Ainda não dá para afirmar melhora ou piora: o volume de dados é pequeno.'
    melhorando = [s.disciplina for s in situacoes if s.situacao == 'melhorando']
    atencao = [s.disciplina for s in situacoes if s.situacao == 'precisa de atenção']
    partes = []
    if melhorando:
        partes.append(f'Você está melhorando em {_lista(melhorando)}')
    if atencao:
        partes.append(
            f'piorando em {_lista(atencao)}' if partes else f'Você está piorando em {_lista(atencao)}'
        )
    if not partes:
        return 'Nenhuma disciplina mostrou melhora ou piora consistente entre os concursos.'
    return ', '.join(partes) + (
        '; estável no restante.' if len(melhorando) + len(atencao) < len(situacoes) else '.'
    )


@dataclass(frozen=True)
class PontoForte:
    disciplina: str
    acertos: int
    n: int
    percentual: float

    @property
    def frase(self) -> str:
        return (
            f'Você vai bem em {self.disciplina}: acertou {self.acertos} de {self.n}; '
            f'descontado o chute, {percentual(self.percentual, 0)}.'
        )


def _validas_com_disciplina(consolidado: pd.DataFrame) -> pd.DataFrame:
    return consolidado[
        ~consolidado['anulada'].astype(bool) & consolidado['disciplina_canonica'].ne(TOPICO_NAO_MAPEADO)
    ]


def ha_amostra_por_disciplina(consolidado: pd.DataFrame) -> bool:
    """Alguma disciplina com n ≥ `N_MINIMO_TOPICO` questões não anuladas: sem isso, nenhuma pode ser forte."""
    if consolidado.empty:
        return False
    validas = _validas_com_disciplina(consolidado)
    return bool((validas.groupby('disciplina_canonica').size() >= N_MINIMO_TOPICO).any())


def pontos_fortes(consolidado: pd.DataFrame, limiar: float, maximo: int = MAXIMO_FORTES) -> list[PontoForte]:
    """Disciplinas com n ≥ `N_MINIMO_TOPICO` e percentual ajustado (sem anuladas) ≥ limiar."""
    validas = _validas_com_disciplina(consolidado)
    if validas.empty:
        return []
    tabela = (
        validas.assign(acerto=validas['resultado'].eq(Resultado.ACERTO))
        .groupby('disciplina_canonica')
        .agg(n=('questao', 'size'), acertos=('acerto', 'sum'), percentual=('pontos_ajustada', 'mean'))
    )
    tabela['percentual'] *= 100
    fortes = tabela[(tabela['n'] >= N_MINIMO_TOPICO) & (tabela['percentual'] >= 100 * limiar)]
    fortes = fortes.sort_values(['percentual', 'n'], ascending=[False, False]).head(maximo)
    return [
        PontoForte(str(disciplina), int(linha.acertos), int(linha.n), float(linha.percentual))
        for disciplina, linha in fortes.iterrows()
    ]


@dataclass(frozen=True)
class TopicoFraco:
    disciplina: str
    topico: str
    acertos: int
    n: int
    percentual: float
    concursos: int
    concursos_abaixo: tuple[str, ...]
    prioridade: float

    @property
    def abaixo_em_todos(self) -> bool:
        return len(self.concursos_abaixo) >= self.concursos

    def frase(self, limiar: float) -> str:
        """Por acertos: com o ajustado negativo, a pessoa acertou menos de n/k, o que o chute daria."""
        if self.percentual < 0:
            texto = f'Acertou {self.acertos} de {self.n} questões, menos do que acertaria chutando.'
        else:
            texto = (
                f'Acertou {self.acertos} de {self.n}; descontado o chute, ficou em '
                f'{percentual(self.percentual, 0)}, abaixo do mínimo de {percentual(100 * limiar, 0)} '
                'que você definiu.'
            )
        onde = ', '.join(self.concursos_abaixo)
        if self.abaixo_em_todos:
            return f'{texto} Ficou abaixo em todos os concursos em que apareceu ({onde}).'
        return f'{texto} Ficou abaixo em {len(self.concursos_abaixo)} de {self.concursos} concursos ({onde}).'


@dataclass(frozen=True)
class GrupoFraco:
    disciplina: str
    topicos: tuple[TopicoFraco, ...]
    forte_no_geral: bool = False

    @property
    def prioridade(self) -> float:
        return max(topico.prioridade for topico in self.topicos)

    @property
    def concursos(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(c for topico in self.topicos for c in topico.concursos_abaixo))

    @property
    def titulo(self) -> str:
        return f'{self.disciplina}: {plural(len(self.topicos), "tópico")} abaixo do esperado'

    @property
    def sugestao(self) -> str:
        if self.forte_no_geral:
            return (
                f'Mesmo indo bem no geral, {plural(len(self.topicos), "tópico ficou", "tópicos ficaram")} '
                f'abaixo. Considere revisá-{"lo" if len(self.topicos) == 1 else "los"} antes do próximo '
                'concurso.'
            )
        return f'Considere revisar {self.disciplina} antes do próximo concurso.'


def fracos_priorizados(
    fracos: pd.DataFrame, limiar: float, fortes: list[PontoForte] | None = None
) -> list[GrupoFraco]:
    """Os tópicos de `topicos_fracos_persistentes` com prioridade = concursos abaixo × (limiar − percentual),
    agrupados por disciplina; os grupos vêm pelo item de maior prioridade."""
    if fracos.empty:
        return []
    nomes_fortes = {forte.disciplina for forte in fortes or []}
    por_disciplina: dict[str, list[TopicoFraco]] = {}
    for linha in fracos.itertuples():
        abaixo = tuple(linha.concursos_abaixo)
        topico = TopicoFraco(
            disciplina=str(linha.disciplina),
            topico=str(linha.topico),
            acertos=int(linha.acertos),
            n=int(linha.n),
            percentual=float(linha.percentual),
            concursos=int(linha.concursos),
            concursos_abaixo=abaixo,
            prioridade=len(abaixo) * (limiar - float(linha.percentual) / 100),
        )
        por_disciplina.setdefault(topico.disciplina, []).append(topico)
    grupos = [
        GrupoFraco(
            disciplina,
            tuple(sorted(topicos, key=lambda t: t.prioridade, reverse=True)),
            disciplina in nomes_fortes,
        )
        for disciplina, topicos in por_disciplina.items()
    ]
    return sorted(grupos, key=lambda grupo: (-grupo.prioridade, grupo.disciplina))


@dataclass(frozen=True)
class Kpis:
    concursos: int
    provas: int
    acima: int
    abaixo: int
    no_limite: int
    com_corte: int
    melhor: Prova | None
    mais_fraco: GrupoFraco | None
    tendencia: Tendencia


def kpis(provas: list[Prova], grupos: list[GrupoFraco], tendencia: Tendencia) -> Kpis:
    """ "Acima" e "abaixo" pelo atingido de todos os cortes; "no limite" conta à parte, de qualquer lado."""
    com_corte = [p for p in provas if p.status not in (StatusProva.SEM_CORTE, StatusProva.NAO_CALCULAVEL)]
    mais_fraco = max(grupos, key=lambda g: (len(g.topicos), g.prioridade), default=None)
    return Kpis(
        concursos=len({p.concurso for p in provas}),
        provas=len(provas),
        acima=sum(1 for p in com_corte if p.atingido),
        abaixo=sum(1 for p in com_corte if not p.atingido),
        no_limite=sum(1 for p in com_corte if p.status is StatusProva.LIMITE),
        com_corte=len(com_corte),
        melhor=max(provas, key=lambda p: p.percentual, default=None),
        mais_fraco=mais_fraco,
        tendencia=tendencia,
    )


def resumo_executivo(indicadores: Kpis) -> str:
    if not indicadores.provas:
        return 'Ainda não há concursos analisados.'
    concursos = plural(indicadores.concursos, 'concurso')
    frases = [
        f'Você fez {concursos} ({plural(indicadores.provas, "prova")}).'
        if indicadores.provas != indicadores.concursos
        else f'Você fez {concursos}.'
    ]
    if indicadores.com_corte:
        total = (
            f'das {indicadores.com_corte} provas'
            if indicadores.com_corte == indicadores.provas
            else f'das {indicadores.com_corte} provas com corte no edital'
        )
        if indicadores.com_corte == 1:
            total = 'na única prova com corte' if indicadores.provas > 1 else 'na prova'
            frases.append(f'Ficou {"acima" if indicadores.acima else "abaixo"} do corte {total}.')
        else:
            frases.append(f'Ficou acima do corte em {indicadores.acima} {total}.')
    if indicadores.melhor is not None and indicadores.provas > 1:
        melhor = indicadores.melhor
        frases.append(f'Seu melhor desempenho foi em {melhor.rotulo} ({percentual(melhor.percentual)}).')
    if indicadores.mais_fraco is not None:
        grupo = indicadores.mais_fraco
        frases.append(
            f'O ponto mais fraco é {grupo.disciplina}, com '
            f'{plural(len(grupo.topicos), "tópico")} abaixo do esperado.'
        )
    if indicadores.tendencia.chave != 'indefinida':
        frases.append(indicadores.tendencia.frase)
    return ' '.join(frases)


@dataclass(frozen=True)
class FontesDasAcoes:
    simulado_focado: Path | None = None
    recomendacoes: Path | None = None
    radar: Path | None = None
    pratica: Path | None = None
    leituras_a_conferir: int = 0
    topicos_a_conferir: int = 0


@dataclass(frozen=True)
class Acao:
    texto: str
    link: str | None = None


@dataclass(frozen=True)
class Painel:
    provas: list[Prova]
    kpis: Kpis
    fortes: list[PontoForte]
    grupos: list[GrupoFraco]
    situacoes: list[SituacaoDaDisciplina]
    limiar: float
    acoes: list[Acao] = field(default_factory=list)

    @property
    def frase_de_evolucao(self) -> str:
        return frase_de_evolucao(self.situacoes)

    @property
    def resumo(self) -> str:
        return resumo_executivo(self.kpis)


def acoes_sugeridas(painel: Painel, fontes: FontesDasAcoes) -> list[Acao]:
    """De 3 a 5 ações tiradas dos dados, na ordem de prioridade; com poucos dados, podem ser menos."""
    acoes = []
    grupos = painel.grupos
    if grupos:
        grupo = grupos[0]
        acoes.append(
            Acao(
                f'Foque em {grupo.disciplina}: {plural(len(grupo.topicos), "tópico")} abaixo do esperado, '
                f'em {plural(len(grupo.concursos), "concurso")}.'
            )
        )
    em_todos = [t for grupo in grupos for t in grupo.topicos if t.abaixo_em_todos]
    if em_todos:
        topico = max(em_todos, key=lambda t: t.prioridade)
        quantos = 'no concurso' if topico.concursos == 1 else f'em todos os {topico.concursos} concursos'
        acoes.append(
            Acao(f'Revise {topico.topico} ({topico.disciplina}): ficou abaixo {quantos} em que apareceu.')
        )
    if len(grupos) > 1:
        segundo = grupos[1]
        exemplos = ', '.join(t.topico for t in segundo.topicos[:2])
        acoes.append(
            Acao(
                f'Refaça questões de {segundo.disciplina} ({exemplos}): abaixo do esperado em mais de um concurso.'
            )
        )
    no_limite = [p for p in painel.provas if p.status is StatusProva.LIMITE]
    if no_limite:
        prova = min(no_limite, key=lambda p: abs(p.gap))
        lado = 'abaixo' if prova.gap < 0 else 'acima'
        acoes.append(
            Acao(
                f'Você ficou {_pp(abs(prova.gap))} {lado} do corte em {prova.rotulo}: '
                'pequenos ganhos já mudam o resultado.'
            )
        )
    if fontes.leituras_a_conferir:
        acoes.append(
            Acao(
                f'Confira {plural(fontes.leituras_a_conferir, "resposta")} da folha com leitura incerta '
                '(tela Analisar).'
            )
        )
    if fontes.topicos_a_conferir:
        acoes.append(
            Acao(
                f'Confira {plural(fontes.topicos_a_conferir, "questão", "questões")} em que o app escolheu o '
                'tópico (tela Conferir).'
            )
        )
    if fontes.simulado_focado is not None:
        acoes.append(Acao('Faça o simulado focado nos seus tópicos fracos.', '#simulado-focado'))
    elif grupos:
        acoes.append(
            Acao(
                'Considere um simulado focado nos tópicos fracos antes do próximo concurso '
                '(Concursos > Provas anteriores).'
            )
        )
    if fontes.recomendacoes is not None:
        acoes.append(Acao('Veja onde estudar cada tópico fraco.', '#onde-estudar'))
    if fontes.radar is not None:
        acoes.append(Acao('Confira os prazos dos editais que você acompanha.', '#prazos'))
    return acoes[:MAXIMO_ACOES]


def montar_painel(
    provas: list[Prova],
    consolidado: pd.DataFrame,
    fracos: pd.DataFrame,
    tendencias: pd.DataFrame,
    correlacao: Correlacao | None,
    limiar: float,
    fontes: FontesDasAcoes,
) -> Painel:
    fortes = pontos_fortes(consolidado, limiar) if not consolidado.empty else []
    grupos = fracos_priorizados(fracos, limiar, fortes)
    painel = Painel(
        provas=provas,
        kpis=kpis(provas, grupos, tendencia_geral(correlacao)),
        fortes=fortes,
        grupos=grupos,
        situacoes=situacao_por_disciplina(tendencias),
        limiar=limiar,
    )
    return Painel(**{**painel.__dict__, 'acoes': acoes_sugeridas(painel, fontes)})


def _pp(valor: float) -> str:
    return f'{valor:.1f}'.replace('.', ',') + ' p.p.'


def _lista(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else f'{", ".join(itens[:-1])} e {itens[-1]}'
