import logging
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from concursos.edital import Edital
from concursos.texto import normalizar

logger = logging.getLogger(__name__)

NAO_MAPEADO = 'nao_mapeado'
SCORE_BAIXO = 0.05
ARQUIVO_REVISAO = 'revisao/questoes_revisado.csv'
COLUNAS_REVISAO = [
    'questao',
    'prova',
    'disciplina_sugerida',
    'topico_sugerido',
    'score',
    'enunciado',
    'disciplina',
    'topico',
]
TAMANHO_ENUNCIADO = 300

_PALAVRAS_VAZIAS = sorted(
    set(
        [
            'a',
            'ao',
            'aos',
            'as',
            'com',
            'como',
            'da',
            'das',
            'de',
            'do',
            'dos',
            'e',
            'em',
            'entre',
            'na',
            'nas',
            'no',
            'nos',
            'o',
            'os',
            'ou',
            'para',
            'pela',
            'pelas',
            'pelo',
            'pelos',
            'por',
            'que',
            'se',
            'sem',
            'sob',
            'sobre',
            'um',
            'uma',
            'umas',
            'uns',
            'nao',
            'mais',
            'ja',
            'sua',
            'suas',
            'seu',
            'seus',
            'esta',
            'este',
            'estas',
            'estes',
            'essa',
            'esse',
            'isso',
            'aquele',
            'aquela',
            'foi',
            'ser',
            'sao',
            'ha',
            'tem',
            'ter',
            'cada',
            'qual',
            'quais',
            'quando',
            'onde',
            'acerca',
            'considerando',
            'considere',
            'julgue',
            'item',
            'itens',
            'seguir',
            'seguinte',
            'seguintes',
            'seguem',
            'subsequentes',
            'assinale',
            'opcao',
            'alternativa',
            'correta',
            'incorreta',
            'texto',
            'relacao',
            'respeito',
            'referente',
            'refere',
            'afirmativa',
        ]
    )
)


@dataclass(frozen=True)
class Sugestao:
    disciplina: str | None
    topico: str
    score: float


@dataclass(frozen=True)
class _Candidato:
    disciplina: str
    topico: str
    documento: str


def sugerir_topicos(
    edital: Edital | None, textos: dict[int, str], disciplinas: dict[int, str]
) -> dict[int, Sugestao]:
    """Tópico do edital mais parecido (TF-IDF, cosseno) com o texto de cada questão.

    A disciplina vinda do caderno ou do mapeamento manual restringe os candidatos: se ela corresponde a uma
    disciplina do edital, só os tópicos dela; senão, os das disciplinas que nenhuma outra do caderno casou.
    """
    candidatos = [
        _Candidato(disciplina.nome, topico.nome, f'{disciplina.nome} {topico.descricao or topico.nome}')
        for conhecimento in (edital.conhecimentos if edital else ())
        for disciplina in conhecimento.disciplinas
        for topico in disciplina.topicos
    ]
    preenchidos = [texto for texto in textos.values() if texto.strip()]
    if not candidatos or not preenchidos:
        return {questao: Sugestao(disciplinas.get(questao), NAO_MAPEADO, 0.0) for questao in textos}

    vetorizador = TfidfVectorizer(
        strip_accents='unicode', ngram_range=(1, 2), sublinear_tf=True, stop_words=_PALAVRAS_VAZIAS
    )
    vetorizador.fit([c.documento for c in candidatos] + preenchidos)
    matriz = vetorizador.transform([c.documento for c in candidatos])
    permitidas = _disciplinas_permitidas({c.disciplina for c in candidatos}, set(disciplinas.values()))

    sugestoes = {}
    for questao, texto in textos.items():
        disciplina = disciplinas.get(questao)
        if not texto.strip():
            sugestoes[questao] = Sugestao(disciplina, NAO_MAPEADO, 0.0)
            continue
        similaridades = cosine_similarity(vetorizador.transform([texto]), matriz)[0]
        aceitas = permitidas.get(disciplina) if disciplina else None
        indice = max(
            (i for i, c in enumerate(candidatos) if aceitas is None or c.disciplina in aceitas),
            key=lambda i: similaridades[i],
        )
        score = round(float(similaridades[indice]), 3)
        topico = candidatos[indice].topico if score > 0 else NAO_MAPEADO
        sugestoes[questao] = Sugestao(disciplina or candidatos[indice].disciplina, topico, score)
    return sugestoes


def _disciplinas_permitidas(do_edital: set[str], do_caderno: set[str]) -> dict[str, set[str]]:
    casadas = {
        caderno: {edital for edital in do_edital if _equivalentes(caderno, edital)} for caderno in do_caderno
    }
    usadas = set().union(*casadas.values())
    restantes = (do_edital - usadas) or do_edital
    return {caderno: edital or restantes for caderno, edital in casadas.items()}


def _equivalentes(uma: str, outra: str) -> bool:
    a, b = palavras_chave(uma), palavras_chave(outra)
    return bool(a and b) and (a <= b or b <= a)


def palavras_chave(texto: str) -> set[str]:
    return set(re.findall(r'\w+', normalizar(texto).lower())) - set(_PALAVRAS_VAZIAS)


def chave_de_palavras(texto: str) -> str:
    """Palavras-chave em ordem alfabética: iguala nomes que só diferem em acento, caixa e palavras vazias."""
    return ' '.join(sorted(palavras_chave(texto)))


def gravar_revisao(caminho: Path, linhas: list[dict]) -> bool:
    """Cria o CSV de revisão (sugestões + colunas vazias a preencher); nunca sobrescreve o do usuário."""
    if caminho.exists():
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tabela = pd.DataFrame(linhas).assign(disciplina='', topico='')
    tabela['enunciado'] = tabela['enunciado'].str.slice(0, TAMANHO_ENUNCIADO)
    tabela[COLUNAS_REVISAO].to_csv(caminho, index=False)
    logger.info(
        'Revisão de tópicos criada em %s: preencha disciplina/topico para corrigir sugestões', caminho
    )
    return True


def ler_revisao(caminho: Path) -> dict[tuple[int, str], tuple[str, str]]:
    """(questao, prova) -> (disciplina, topico) revisados; células vazias mantêm a sugestão."""
    if not caminho.exists():
        return {}
    tabela = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    faltando = {'questao', 'prova', 'disciplina', 'topico'} - set(tabela.columns)
    if faltando:
        raise ValueError(f'{caminho}: colunas ausentes na revisão: {", ".join(sorted(faltando))}')
    return {
        (int(linha.questao), linha.prova): (linha.disciplina.strip(), linha.topico.strip())
        for linha in tabela.itertuples()
        if linha.disciplina.strip() or linha.topico.strip()
    }
