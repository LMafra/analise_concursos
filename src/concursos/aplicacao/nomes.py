"""O nome mostrado de cada concurso nas telas: pelo edital estruturado da última análise ou, antes dela,
pela leitura rápida do edital (sem OCR nem IA)."""

import json
from dataclasses import asdict

from concursos.analytics.nome_concurso import NomeDoConcurso, nome_do_concurso
from concursos.analytics.regras_edital import identificar_edital
from concursos.concurso_config import ConcursoConfig, ConfiguracaoInvalidaError, carregar_concurso
from concursos.config.contexto import Contexto
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO
from concursos.status import listar_concursos
from concursos.texto import extrair_paginas


def _do_estruturado(contexto: Contexto, concurso: str) -> dict | None:
    candidatos = []
    if contexto.candidato:
        candidatos.append(contexto.analises / contexto.candidato / concurso / ARQUIVO_EDITAL_ESTRUTURADO)
    if contexto.analises.is_dir():
        candidatos += sorted(contexto.analises.glob(f'**/{concurso}/{ARQUIVO_EDITAL_ESTRUTURADO}'))
    for caminho in candidatos:
        try:
            identificacao = json.loads(caminho.read_text(encoding='utf-8')).get('identificacao')
        except (OSError, ValueError):
            continue
        if identificacao:
            return identificacao
    return None


def _da_leitura_rapida(config: ConcursoConfig) -> dict | None:
    if config.edital is None:
        return None
    documentos = {}
    for nome in config.edital.documentos:
        try:
            documentos[nome] = extrair_paginas(config.pasta / nome, ocr=False)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
    return asdict(identificar_edital(documentos)) if documentos else None


def identificacao_do_concurso(contexto: Contexto, config: ConcursoConfig) -> dict | None:
    return _do_estruturado(contexto, config.nome) or _da_leitura_rapida(config)


def nome_no_projeto(contexto: Contexto, config: ConcursoConfig) -> NomeDoConcurso:
    return nome_do_concurso(config, identificacao_do_concurso(contexto, config))


def opcoes_de_concurso(contexto: Contexto) -> dict[str, str]:
    """`{pasta: nome mostrado}` de cada concurso, para os selects; a pasta sem `concurso.yaml` aparece pelo
    próprio nome."""
    if not contexto.provas.is_dir():
        return {}
    opcoes = {}
    for pasta in listar_concursos(contexto.provas):
        try:
            opcoes[pasta.name] = nome_no_projeto(contexto, carregar_concurso(pasta)).titulo
        except (ConfiguracaoInvalidaError, FileNotFoundError):
            opcoes[pasta.name] = pasta.name
    return opcoes
