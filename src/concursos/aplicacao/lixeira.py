"""Lixeira de sessão: move, restaura e esvazia na próxima abertura."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from concursos.config.contexto import Contexto

NOME_LIXEIRA = 'lixeira'
ARQUIVO_INDICE = 'indice.json'


@dataclass(frozen=True)
class ItemLixeira:
    id: str
    destino: Path
    origem: Path
    tipo: str


def _pasta(raiz: Path) -> Path:
    pasta = raiz / NOME_LIXEIRA
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _indice(pasta: Path) -> Path:
    return pasta / ARQUIVO_INDICE


def _ler(pasta: Path) -> list[dict]:
    caminho = _indice(pasta)
    if not caminho.exists():
        return []
    try:
        return json.loads(caminho.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []


def _gravar(pasta: Path, itens: list[dict]) -> None:
    _indice(pasta).write_text(json.dumps(itens, ensure_ascii=False, indent=2), encoding='utf-8')


def esvaziar(raiz: Path) -> None:
    """Apaga o conteúdo da lixeira; chamada na abertura do app."""
    pasta = raiz / NOME_LIXEIRA
    if not pasta.exists():
        return
    shutil.rmtree(pasta, ignore_errors=True)


def mover_para_lixeira(raiz: Path, origem: Path, *, tipo: str) -> ItemLixeira | None:
    """Move `origem` para a lixeira. Devolve o item para o toast Desfazer."""
    if not origem.exists():
        return None
    pasta = _pasta(raiz)
    identificador = uuid.uuid4().hex
    destino = pasta / identificador
    origem.rename(destino)
    item = {
        'id': identificador,
        'origem': str(origem),
        'destino': str(destino),
        'tipo': tipo,
        'quando': time.time(),
    }
    itens = _ler(pasta)
    itens.append(item)
    _gravar(pasta, itens)
    return ItemLixeira(identificador, destino, origem, tipo)


def restaurar(raiz: Path, identificador: str) -> Path | None:
    pasta = _pasta(raiz)
    itens = _ler(pasta)
    escolhido = next((i for i in itens if i['id'] == identificador), None)
    if escolhido is None:
        return None
    origem = Path(escolhido['origem'])
    destino = Path(escolhido['destino'])
    if not destino.exists():
        return None
    origem.parent.mkdir(parents=True, exist_ok=True)
    if origem.exists():
        shutil.rmtree(origem) if origem.is_dir() else origem.unlink()
    destino.rename(origem)
    _gravar(pasta, [i for i in itens if i['id'] != identificador])
    return origem


def snapshot_arquivo(caminho: Path) -> bytes | None:
    """Conteúdo anterior de um arquivo, para Desfazer um Salvar."""
    if not caminho.exists() or not caminho.is_file():
        return None
    return caminho.read_bytes()


def restaurar_arquivo(caminho: Path, conteudo: bytes | None) -> None:
    if conteudo is None:
        if caminho.exists():
            caminho.unlink()
        return
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(conteudo)


def lixeira_do_projeto(contexto: Contexto) -> Path:
    return contexto.projeto


def lixeira_global(contexto: Contexto) -> Path:
    return contexto.home
