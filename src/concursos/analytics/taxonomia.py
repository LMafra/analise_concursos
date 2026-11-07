"""Taxonomia de disciplinas: nome bruto da análise -> disciplina canônica e bloco (geral ou específico)."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from concursos.correcao import TOPICO_NAO_MAPEADO
from concursos.erros import avisar
from concursos.modelo import Bloco
from concursos.topicos import chave_de_palavras

logger = logging.getLogger(__name__)

ARQUIVO_TAXONOMIA = 'taxonomia.yaml'
BLOCO_DA_PROVA = {'cg': Bloco.GERAL, 'cb': Bloco.GERAL, 'ce': Bloco.ESPECIFICO}
_BLOCOS_DA_TAXONOMIA = (Bloco.GERAL, Bloco.ESPECIFICO)


class TaxonomiaInvalidaError(ValueError):
    pass


@dataclass(frozen=True)
class DisciplinaCanonica:
    nome: str
    bloco: Bloco


def carregar_taxonomia(caminho: Path) -> dict[str, DisciplinaCanonica]:
    """Mapa de cada nome bruto (e do próprio nome canônico) para a sua disciplina canônica; vazio sem o
    arquivo."""
    if not caminho.exists():
        return {}
    dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    if not isinstance(dados, dict):
        raise TaxonomiaInvalidaError(f'{caminho}: esperado um mapa de disciplina canônica para bloco e nomes')
    taxonomia: dict[str, DisciplinaCanonica] = {}
    for nome, entrada in dados.items():
        entrada = entrada or {}
        disciplina = DisciplinaCanonica(nome, _bloco(nome, entrada.get('bloco')))
        for bruto in dict.fromkeys([nome, *entrada.get('nomes', [])]):
            if bruto in taxonomia:
                raise TaxonomiaInvalidaError(f"nome '{bruto}' mapeado em mais de uma disciplina")
            taxonomia[bruto] = disciplina
    return taxonomia


def classificar(questoes: pd.DataFrame, taxonomia: dict[str, DisciplinaCanonica]) -> pd.DataFrame:
    """Acrescenta disciplina canônica, bloco e chave de tópico.

    Nas provas divididas o bloco vem da prova. Na prova única vem da taxonomia, e uma questão que o pipeline
    não classificou (`nao_mapeado`) fica com bloco `nao_informado`. Disciplina fora da taxonomia é canônica
    de si mesma, com bloco `nao_informado` fora das provas divididas. Tópico não classificado fica sem
    chave, para não virar um tópico comum a todos os concursos.
    """
    fora = sorted(set(questoes['disciplina']) - set(taxonomia) - {TOPICO_NAO_MAPEADO})
    if fora:
        avisar(
            logger,
            f'{", ".join(fora)}: fora da lista de disciplinas equivalentes; cada uma conta como uma disciplina '
            'à parte.',
            'junte as que forem a mesma disciplina em Disciplinas e temas.',
            f'disciplinas fora da taxonomia: {fora}; cada uma conta como canônica de si mesma',
        )
    canonicas = questoes['disciplina'].map(
        lambda bruto: taxonomia.get(bruto) or DisciplinaCanonica(bruto, Bloco.NAO_INFORMADO)
    )
    nomes = canonicas.map(lambda c: c.nome).astype('str')
    bloco_da_taxonomia = canonicas.map(lambda c: c.bloco.value)
    return questoes.assign(
        disciplina_canonica=nomes,
        bloco=questoes['prova'].map(BLOCO_DA_PROVA).fillna(bloco_da_taxonomia).astype('str'),
        chave_topico=[
            chave_topico(nome, topico)
            if pd.notna(nome) and TOPICO_NAO_MAPEADO not in (nome, topico)
            else pd.NA
            for nome, topico in zip(nomes, questoes['topico'], strict=True)
        ],
    ).astype({'chave_topico': 'str'})


def chave_topico(disciplina_canonica: str, topico: str) -> str:
    """Identidade do tópico entre editais: a disciplina canônica e as palavras-chave do nome do tópico."""
    return f'{disciplina_canonica} | {chave_de_palavras(topico)}'


def _bloco(nome: str, valor) -> Bloco:
    if valor not in _BLOCOS_DA_TAXONOMIA:
        opcoes = ', '.join(_BLOCOS_DA_TAXONOMIA)
        raise TaxonomiaInvalidaError(f"{nome}: bloco '{valor or ''}' inválido (use {opcoes})")
    return Bloco(valor)
