"""Fachada pública da análise: orquestra etapas privadas em `pipeline.nucleo`.

Quem chama (aplicacao/, testes) importa só daqui. A eferência deste módulo fica baixa;
os imports pesados moram em `nucleo` e futuras `etapas/`.
"""

from concursos.artefatos import ARQUIVO_RESPOSTAS
from concursos.pipeline.nucleo import (
    COLUNAS_DICIONARIO,
    COLUNAS_QUESTOES,
    COLUNAS_RESPOSTAS,
    AnaliseCancelada,
    ConcursoNaoEncontradoError,
    analisar_concurso,
    analisar_todos,
    planejar,
    preparar_revisao,
)

__all__ = [
    'ARQUIVO_RESPOSTAS',
    'COLUNAS_DICIONARIO',
    'COLUNAS_QUESTOES',
    'COLUNAS_RESPOSTAS',
    'AnaliseCancelada',
    'ConcursoNaoEncontradoError',
    'analisar_concurso',
    'analisar_todos',
    'planejar',
    'preparar_revisao',
]
