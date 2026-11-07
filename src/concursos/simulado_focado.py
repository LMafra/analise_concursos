"""Simulado focado: as questões das provas anteriores importadas que caem nos tópicos fracos do candidato.

As questões vêm da revisão de tópicos de cada simulado (`revisao/questoes_revisado.csv`), que existe mesmo
antes de o candidato responder a prova; a correção manual da revisão vence a sugestão.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from concursos.arquivos import gravar_se_mudou
from concursos.concurso_config import ler_dados
from concursos.consolidado import MINIMO_CONCURSOS
from concursos.correcao import ARQUIVO_QUESTOES, TOPICO_NAO_MAPEADO
from concursos.linguagem import plural
from concursos.modelo import Resultado
from concursos.texto import abreviar, normalizar
from concursos.topicos import ARQUIVO_REVISAO

ARQUIVO_SIMULADO_FOCADO = 'consolidado/simulado_focado.md'
MAXIMO_QUESTOES = 30
MAXIMO_POR_TOPICO = 5
TAMANHO_ENUNCIADO = 160


@dataclass(frozen=True)
class QuestaoDoSimulado:
    pasta: str
    nome: str
    prova: str
    questao: int
    disciplina: str
    topico: str
    enunciado: str


@dataclass(frozen=True)
class SimuladoFocado:
    questoes: list[tuple[pd.Series, list[QuestaoDoSimulado]]]
    simulados: int
    sem_revisao: list[str]

    @property
    def total(self) -> int:
        return sum(len(questoes) for _, questoes in self.questoes)


def pastas_de_simulado(raiz_provas: Path) -> list[Path]:
    if not raiz_provas.is_dir():
        return []
    return sorted(
        p for p in raiz_provas.iterdir() if p.is_dir() and isinstance(ler_dados(p).get('simulado'), dict)
    )


def _chave(texto: str) -> str:
    return normalizar(str(texto)).lower().strip()


def _acertadas(pasta_analise: Path) -> set[tuple[str, int]]:
    """As questões que o candidato já acertou no simulado, se ele já o respondeu."""
    caminho = pasta_analise / ARQUIVO_QUESTOES
    if not caminho.exists():
        return set()
    tabela = pd.read_csv(caminho, usecols=['prova', 'questao', 'resultado'])
    acertos = tabela[tabela['resultado'] == Resultado.ACERTO.value]
    return {(str(p), int(q)) for p, q in zip(acertos['prova'], acertos['questao'], strict=True)}


def questoes_dos_simulados(
    raiz_provas: Path, pasta_candidato: Path
) -> tuple[list[QuestaoDoSimulado], list[str]]:
    """As questões classificadas de cada simulado, sem as já acertadas; e os simulados ainda sem revisão."""
    questoes, sem_revisao = [], []
    for pasta in pastas_de_simulado(raiz_provas):
        caminho = pasta / ARQUIVO_REVISAO
        if not caminho.exists():
            sem_revisao.append(pasta.name)
            continue
        nome = str(ler_dados(pasta).get('nome') or pasta.name)
        acertadas = _acertadas(pasta_candidato / pasta.name)
        revisao = pd.read_csv(caminho, dtype=str, keep_default_na=False)
        for linha in revisao.itertuples():
            disciplina = linha.disciplina or linha.disciplina_sugerida
            topico = linha.topico or linha.topico_sugerido
            if not topico or topico == TOPICO_NAO_MAPEADO or (linha.prova, int(linha.questao)) in acertadas:
                continue
            questoes.append(
                QuestaoDoSimulado(
                    pasta.name, nome, linha.prova, int(linha.questao), disciplina, topico, linha.enunciado
                )
            )
    return questoes, sem_revisao


def montar(raiz_provas: Path, pasta_candidato: Path, fracos: pd.DataFrame) -> SimuladoFocado:
    """Na ordem dos tópicos fracos, até `MAXIMO_POR_TOPICO` questões por tópico e `MAXIMO_QUESTOES` no total.
    O tópico casa com a disciplina quando a questão tem uma; sem ela, só pelo tópico."""
    questoes, sem_revisao = questoes_dos_simulados(raiz_provas, pasta_candidato)
    escolhidas: list[tuple[pd.Series, list[QuestaoDoSimulado]]] = []
    restantes = MAXIMO_QUESTOES
    for _, fraco in fracos.iterrows():
        if restantes <= 0:
            break
        topico, disciplina = _chave(fraco['topico']), _chave(fraco['disciplina'])
        do_topico = [
            q
            for q in questoes
            if _chave(q.topico) == topico
            and (not q.disciplina or q.disciplina == TOPICO_NAO_MAPEADO or _chave(q.disciplina) == disciplina)
        ][: min(MAXIMO_POR_TOPICO, restantes)]
        if do_topico:
            escolhidas.append((fraco, do_topico))
            restantes -= len(do_topico)
    return SimuladoFocado(escolhidas, len(pastas_de_simulado(raiz_provas)), sem_revisao)


def formatar(simulado: SimuladoFocado, limiar: float) -> str:
    linhas = [
        '# Simulado focado',
        '',
        f'{plural(simulado.total, "questão", "questões")} de provas anteriores nos tópicos em que você ficou '
        f'abaixo de {limiar:.0%} (descontado o chute) em pelo menos {MINIMO_CONCURSOS} concursos. O app '
        'escolheu as questões pelo tópico de cada uma: resolva no caderno da prova e confira no gabarito dela.',
        '',
    ]
    if simulado.sem_revisao:
        linhas += [
            'Provas ainda sem tópicos (analise de novo para o app classificar): '
            + ', '.join(simulado.sem_revisao)
            + '.',
            '',
        ]
    if not simulado.questoes:
        linhas += ['Nenhuma questão das provas anteriores caiu nos seus tópicos fracos.', '']
        return '\n'.join(linhas)
    for fraco, questoes in simulado.questoes:
        linhas += [
            f'## {fraco["disciplina"]}: {fraco["topico"]} ({_acertos(fraco)})',
            '',
        ]
        for questao in questoes:
            enunciado = abreviar(' '.join(questao.enunciado.split()), TAMANHO_ENUNCIADO)
            linhas.append(
                f'- {questao.nome}, questão {questao.questao} (prova {questao.prova})'
                + (f': {enunciado}' if enunciado else '')
            )
        linhas.append('')
    return '\n'.join(linhas)


def _acertos(fraco: pd.Series) -> str:
    """Pelos acertos quando o consolidado os traz; o percentual descontado o chute, quando não."""
    if 'acertos' in fraco and pd.notna(fraco['acertos']):
        return f'acertou {int(fraco["acertos"])} de {int(fraco["n"])}'
    return f'{fraco["percentual"]:.0f}% descontado o chute, em {int(fraco["n"])} questões'


def gravar(pasta_candidato: Path, texto: str) -> bool:
    caminho = pasta_candidato / ARQUIVO_SIMULADO_FOCADO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return gravar_se_mudou(caminho, texto)
