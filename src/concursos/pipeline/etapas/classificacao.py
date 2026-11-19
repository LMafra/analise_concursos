"""Classificação de tópicos das questões (edital + dicionário + revisão manual)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from concursos.concurso_config import ConcursoConfig
from concursos.correcao import TOPICO_NAO_MAPEADO
from concursos.edital import Edital
from concursos.pipeline.etapas.leitura import textos_das_questoes
from concursos.topicos import ARQUIVO_REVISAO, gravar_revisao, ler_revisao, sugerir_topicos

if TYPE_CHECKING:
    from concursos.analytics.dicionario_topicos import Dicionario
    from concursos.analytics.taxonomia import DisciplinaCanonica


def classificar_topicos(
    config: ConcursoConfig,
    edital: Edital | None,
    resultados: pd.DataFrame,
    dicionario: Dicionario | None = None,
    taxonomia: dict[str, DisciplinaCanonica] | None = None,
) -> pd.DataFrame:
    """Tópico sugerido por similaridade com o edital; a revisão manual (revisao/) tem prioridade.

    Sem tópicos no edital, a revisão sai do mesmo jeito, com a disciplina das faixas e o tópico nao_mapeado.
    """
    resultados = resultados.assign(topico_sugerido=TOPICO_NAO_MAPEADO, score=0.0, revisado=False)
    textos = textos_das_questoes(config)
    conhecidas = {
        q: d
        for q, d in zip(resultados['questao'], resultados['disciplina'], strict=True)
        if d != TOPICO_NAO_MAPEADO
    }
    canonicas = {bruto: disciplina.nome for bruto, disciplina in (taxonomia or {}).items()}
    textos_questoes = {q: textos.get(q, '') for q in resultados['questao']}
    sugestoes = sugerir_com_ou_sem_dicionario(edital, textos_questoes, conhecidas, dicionario, canonicas)
    aplicar_sugestoes(resultados, sugestoes, dicionario is not None)
    aplicar_revisao_manual(config, resultados, textos)
    return resultados


def sugerir_com_ou_sem_dicionario(edital, textos_questoes, conhecidas, dicionario, canonicas):
    if dicionario is None:
        return sugerir_topicos(edital, textos_questoes, conhecidas)
    from concursos.analytics.dicionario_topicos import sugerir_com_dicionario

    return sugerir_com_dicionario(
        edital, textos_questoes, conhecidas, dicionario, sugerir_topicos, canonicas
    )


def aplicar_sugestoes(resultados: pd.DataFrame, sugestoes: dict, com_dicionario: bool) -> None:
    resultados['disciplina'] = [sugestoes[q].disciplina or TOPICO_NAO_MAPEADO for q in resultados['questao']]
    resultados['topico_sugerido'] = [sugestoes[q].topico for q in resultados['questao']]
    resultados['score'] = [sugestoes[q].score for q in resultados['questao']]
    resultados['topico'] = resultados['topico_sugerido']
    if not com_dicionario:
        return
    resultados['score_tfidf'] = [sugestoes[q].score_tfidf for q in resultados['questao']]
    resultados['topico_tfidf'] = [sugestoes[q].topico_tfidf for q in resultados['questao']]
    resultados['score_expandido'] = resultados['score']


def aplicar_revisao_manual(config: ConcursoConfig, resultados: pd.DataFrame, textos: dict[int, str]) -> None:
    caminho = config.caminho(ARQUIVO_REVISAO)
    revisao = ler_revisao(caminho)
    for indice, linha in resultados.iterrows():
        disciplina, topico = revisao.get((linha['questao'], linha['prova']), ('', ''))
        if disciplina or topico:
            resultados.loc[indice, ['disciplina', 'topico', 'revisado']] = [
                disciplina or linha['disciplina'],
                topico or linha['topico'],
                True,
            ]
    gravar_revisao(
        caminho,
        [
            {
                'questao': linha.questao,
                'prova': linha.prova,
                'disciplina_sugerida': linha.disciplina,
                'topico_sugerido': linha.topico_sugerido,
                'score': linha.score,
                'enunciado': textos.get(linha.questao, ''),
            }
            for linha in resultados.itertuples()
        ],
    )
