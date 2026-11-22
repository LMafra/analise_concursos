import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from concursos.analytics.tipos_topicos import (
    ARQUIVO_REVISAO,
    COLUNAS_REVISAO,
    NAO_MAPEADO,
    PALAVRAS_VAZIAS,
    SCORE_BAIXO,
    TAMANHO_ENUNCIADO,
    ExpansaoProtocol,
    Sugestao,
    chave_de_palavras,
    palavras_chave,
)
from concursos.edital import Edital

logger = logging.getLogger(__name__)

__all__ = [
    'ARQUIVO_REVISAO',
    'COLUNAS_REVISAO',
    'NAO_MAPEADO',
    'SCORE_BAIXO',
    'Sugestao',
    'chave_de_palavras',
    'gravar_revisao',
    'gravar_revisao_editada',
    'ler_revisao',
    'palavras_chave',
    'sugerir_topicos',
]


@dataclass(frozen=True)
class _Candidato:
    disciplina: str
    topico: str
    documento: str


def sugerir_topicos(
    edital: Edital | None,
    textos: dict[int, str],
    disciplinas: dict[int, str],
    expansao: ExpansaoProtocol | None = None,
    canonicas: Mapping[str, str] | None = None,
) -> dict[int, Sugestao]:
    """Tópico do edital mais parecido (TF-IDF, cosseno) com o texto de cada questão.

    A disciplina vinda do caderno ou do mapeamento manual restringe os candidatos: se ela corresponde a uma
    disciplina do edital, só os tópicos dela; senão, os das disciplinas que nenhuma outra do caderno casou.
    Com expansão do dicionário de temas, o tópico e o score vêm da versão expandida, e os de sem ela ficam ao lado.
    `canonicas` é aceito por compatibilidade com chamadas antigas e ignorado (a expansão já vem pronta).
    """
    del canonicas  # a expansão já incorpora o mapeamento canônico
    candidatos = [
        _Candidato(disciplina.nome, topico.nome, f'{disciplina.nome} {topico.descricao or topico.nome}')
        for conhecimento in (edital.conhecimentos if edital else ())
        for disciplina in conhecimento.disciplinas
        for topico in disciplina.topicos
    ]
    sugestoes = _sugerir(candidatos, textos, disciplinas)
    if expansao is None:
        return sugestoes
    expandidas = _sugerir(candidatos, textos, disciplinas, expansao) if expansao.por_topico else sugestoes
    return {
        questao: replace(expandidas[questao], topico_tfidf=base.topico, score_tfidf=base.score)
        for questao, base in sugestoes.items()
    }


def _aplicar_expansao(
    candidatos: list[_Candidato],
    textos: dict[int, str],
    disciplinas: dict[int, str],
    expansao: ExpansaoProtocol,
) -> tuple[list[_Candidato], dict[int, str]]:
    permitidas = _disciplinas_permitidas({c.disciplina for c in candidatos}, set(disciplinas.values()))
    candidatos_exp = [
        replace(c, documento=expansao.documento(c.disciplina, c.topico, c.documento)) for c in candidatos
    ]
    textos_exp = {
        questao: expansao.texto(
            texto, permitidas.get(disciplinas[questao]) if questao in disciplinas else None
        )
        if texto.strip()
        else texto
        for questao, texto in textos.items()
    }
    return candidatos_exp, textos_exp


def _sugestao_por_similaridade(
    questao: int,
    texto: str,
    disciplina: str | None,
    candidatos: list[_Candidato],
    vetorizador: TfidfVectorizer,
    matriz,
    permitidas: dict[str, set[str]],
) -> Sugestao:
    if not texto.strip():
        return Sugestao(disciplina, NAO_MAPEADO, 0.0)
    similaridades = cosine_similarity(vetorizador.transform([texto]), matriz)[0]
    aceitas = permitidas.get(disciplina) if disciplina else None
    indice = max(
        (i for i, c in enumerate(candidatos) if aceitas is None or c.disciplina in aceitas),
        key=lambda i: similaridades[i],
    )
    score = round(float(similaridades[indice]), 3)
    topico = candidatos[indice].topico if score > 0 else NAO_MAPEADO
    return Sugestao(disciplina or candidatos[indice].disciplina, topico, score)


def _sugerir(
    candidatos: list[_Candidato],
    textos: dict[int, str],
    disciplinas: dict[int, str],
    expansao: ExpansaoProtocol | None = None,
) -> dict[int, Sugestao]:
    permitidas = _disciplinas_permitidas({c.disciplina for c in candidatos}, set(disciplinas.values()))
    if expansao is not None:
        candidatos, textos = _aplicar_expansao(candidatos, textos, disciplinas, expansao)
    preenchidos = [texto for texto in textos.values() if texto.strip()]
    if not candidatos or not preenchidos:
        return {questao: Sugestao(disciplinas.get(questao), NAO_MAPEADO, 0.0) for questao in textos}

    vetorizador = TfidfVectorizer(
        strip_accents='unicode', ngram_range=(1, 2), sublinear_tf=True, stop_words=sorted(PALAVRAS_VAZIAS)
    )
    vetorizador.fit([c.documento for c in candidatos] + preenchidos)
    matriz = vetorizador.transform([c.documento for c in candidatos])

    return {
        questao: _sugestao_por_similaridade(
            questao, texto, disciplinas.get(questao), candidatos, vetorizador, matriz, permitidas
        )
        for questao, texto in textos.items()
    }


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


def gravar_revisao(caminho: Path, linhas: list[dict]) -> bool:
    """Cria o CSV de revisão (sugestões + colunas vazias a preencher); nunca sobrescreve o do usuário."""
    if caminho.exists():
        return False
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tabela = pd.DataFrame(linhas).assign(disciplina='', topico='')
    tabela['enunciado'] = tabela['enunciado'].str.slice(0, TAMANHO_ENUNCIADO)
    tabela[COLUNAS_REVISAO].to_csv(caminho, index=False)
    logger.info(
        'Criei a lista para conferir os tópicos das questões (%s); confira em Concursos > Conferir > '
        'Tópicos das questões.',
        caminho,
    )
    return True


def gravar_revisao_editada(caminho: Path, edicoes: dict[tuple[int, str], tuple[str, str]]) -> bool:
    """Troca `disciplina` e `topico` só das linhas editadas; as outras linhas e as colunas ficam como estão."""
    bruto = caminho.read_bytes()
    tabela = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    for indice, linha in tabela.iterrows():
        chave = (int(linha['questao']), linha['prova'])
        if chave in edicoes:
            tabela.loc[indice, ['disciplina', 'topico']] = list(edicoes[chave])
    fim_de_linha = '\r\n' if b'\r\n' in bruto else '\n'
    texto = tabela.to_csv(index=False, lineterminator=fim_de_linha)
    if texto.encode('utf-8') == bruto:
        return False
    caminho.write_bytes(texto.encode('utf-8'))
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
