"""Constantes e funções puras compartilhadas por `topicos` e `dicionario_topicos`.

Sem lógica de TF-IDF nem de dicionário: só tipos, limiares e normalização de palavras.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from concursos.texto import normalizar

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

PALAVRAS_VAZIAS = frozenset(
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


@dataclass(frozen=True)
class Sugestao:
    disciplina: str | None
    topico: str
    score: float
    topico_tfidf: str | None = None
    """Com o dicionário de temas: o tópico e o score sem ele, para comparar."""
    score_tfidf: float | None = None


class ExpansaoProtocol(Protocol):
    """Contrato mínimo que `topicos._sugerir` precisa da expansão do dicionário."""

    @property
    def por_topico(self) -> dict: ...

    def documento(self, disciplina: str, topico: str, documento: str) -> str: ...

    def texto(self, texto: str, aceitas: set[str] | None = None) -> str: ...


def palavras_chave(texto: str) -> set[str]:
    return set(re.findall(r'\w+', normalizar(texto).lower())) - set(PALAVRAS_VAZIAS)


def chave_de_palavras(texto: str) -> str:
    """Palavras-chave em ordem alfabética: iguala nomes que só diferem em acento, caixa e palavras vazias."""
    return ' '.join(sorted(palavras_chave(texto)))
