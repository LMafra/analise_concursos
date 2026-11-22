"""Excluir concurso: pasta de provas e análises de todos os candidatos."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from concursos.aplicacao.lixeira import ItemLixeira, lixeira_do_projeto, mover_para_lixeira, restaurar
from concursos.config.contexto import Contexto
from concursos.integracoes.sincronizacao_notebook import ARQUIVO_ESTADO
from concursos.integracoes.sincronizacao_pci import ARQUIVO_INTERESSES


def excluir_concurso(contexto: Contexto, nome: str) -> list[ItemLixeira]:
    """Move provas/<nome> e analises/*/nome para a lixeira; tira o concurso dos arquivos compartilhados."""
    movidos: list[ItemLixeira] = []
    raiz = lixeira_do_projeto(contexto)
    pasta = contexto.provas / nome
    if item := mover_para_lixeira(raiz, pasta, tipo='prova'):
        movidos.append(item)
    if contexto.analises.is_dir():
        for candidato in contexto.analises.iterdir():
            destino = candidato / nome
            if destino.is_dir() and (item := mover_para_lixeira(raiz, destino, tipo='analise')):
                movidos.append(item)
    _tirar_dos_interesses(contexto.projeto / ARQUIVO_INTERESSES, nome)
    _tirar_do_open_notebook(contexto.projeto / ARQUIVO_ESTADO, nome)
    return movidos


def desfazer_exclusao(contexto: Contexto, itens: list[ItemLixeira]) -> None:
    for item in reversed(itens):
        restaurar(lixeira_do_projeto(contexto), item.id)


def _tirar_dos_interesses(caminho: Path, nome: str) -> None:
    if not caminho.exists():
        return
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError:
        return
    itens = dados.get('interesses') if isinstance(dados, dict) else None
    if not isinstance(itens, list):
        return
    filtrados = [i for i in itens if not (isinstance(i, dict) and i.get('concurso') == nome)]
    if len(filtrados) == len(itens):
        return
    dados['interesses'] = filtrados
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding='utf-8')


def _tirar_do_open_notebook(caminho: Path, nome: str) -> None:
    if not caminho.exists():
        return
    try:
        dados = json.loads(caminho.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return
    instancias = dados.get('instancias')
    if not isinstance(instancias, dict):
        return
    mudou = False
    for instancia in instancias.values():
        notebooks = instancia.get('notebooks') if isinstance(instancia, dict) else None
        if not isinstance(notebooks, dict):
            continue
        for chave in [k for k in notebooks if nome in k]:
            del notebooks[chave]
            mudou = True
    if mudou:
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
