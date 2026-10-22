"""Perfis de banca e de OCR: YAML embutido no pacote ou registrado por outro pacote num entry point
(`concurso.banca`, `concurso.ocr`)."""

import importlib
from collections.abc import Callable
from functools import cache
from importlib.metadata import entry_points
from importlib.resources import files
from pathlib import Path

import yaml

from concursos.perfis.banca import FORMATOS, SEGMENTACOES, PerfilBanca, PerfilInvalidoError, de_dict
from concursos.perfis.ocr import PerfilOcr, de_dict_ocr

__all__ = [
    'FORMATOS',
    'SEGMENTACOES',
    'PerfilBanca',
    'PerfilInvalidoError',
    'PerfilOcr',
    'de_dict',
    'de_dict_ocr',
    'ids_de_banca',
    'ids_de_ocr',
    'perfil_da_banca',
    'perfil_ocr',
    'perfis_de_banca',
    'perfis_de_ocr',
    'resolver_funcao',
]

GRUPO_BANCA = 'concurso.banca'
GRUPO_OCR = 'concurso.ocr'


@cache
def perfis_de_banca() -> tuple[PerfilBanca, ...]:
    """Embutidos e instalados, na ordem de detecção; um instalado com o id de um embutido o substitui."""
    por_id = _carregar('bancas', GRUPO_BANCA, PerfilBanca, de_dict)
    return tuple(sorted(por_id.values(), key=lambda perfil: (perfil.ordem, perfil.id)))


@cache
def perfis_de_ocr() -> tuple[PerfilOcr, ...]:
    return tuple(_carregar('folhas', GRUPO_OCR, PerfilOcr, de_dict_ocr).values())


def ids_de_banca() -> tuple[str, ...]:
    return tuple(perfil.id for perfil in perfis_de_banca())


def ids_de_ocr() -> tuple[str, ...]:
    return tuple(perfil.id for perfil in perfis_de_ocr())


def perfil_da_banca(banca: str) -> PerfilBanca:
    for perfil in perfis_de_banca():
        if perfil.id == banca:
            return perfil
    raise PerfilInvalidoError(f"banca '{banca}' sem perfil (use {', '.join(ids_de_banca())})")


def perfil_ocr(identificador: str) -> PerfilOcr:
    for perfil in perfis_de_ocr():
        if perfil.id == identificador:
            return perfil
    raise PerfilInvalidoError(f"perfil de OCR '{identificador}' desconhecido (use {', '.join(ids_de_ocr())})")


def resolver_funcao(nome: str, embutidos: dict[str, Callable]) -> Callable:
    """Um leitor embutido pelo nome, ou o de outro pacote por `modulo:funcao`."""
    if nome in embutidos:
        return embutidos[nome]
    if ':' in nome:
        modulo, funcao = nome.split(':', 1)
        try:
            return getattr(importlib.import_module(modulo), funcao)
        except (ImportError, AttributeError) as erro:
            raise PerfilInvalidoError(f'leitor {nome!r} não encontrado: {erro}') from erro
    raise PerfilInvalidoError(f'leitor desconhecido: {nome!r} (use {", ".join(embutidos)} ou modulo:funcao)')


def _carregar(pasta: str, grupo: str, tipo: type, montar: Callable[[dict, str], object]) -> dict:
    """Os YAML da pasta embutida, na ordem dos nomes, e depois os do entry point."""
    embutidos = files('concursos.perfis') / pasta
    por_id = {}
    for arquivo in sorted(embutidos.iterdir(), key=lambda a: a.name):
        if arquivo.name.endswith('.yaml'):
            perfil = montar(_ler_yaml(arquivo.read_text(encoding='utf-8'), arquivo.name), arquivo.name)
            por_id[perfil.id] = perfil
    for ponto in entry_points(group=grupo):
        perfil = _do_objeto(ponto.load(), ponto.name, tipo, montar)
        por_id[perfil.id] = perfil
    return por_id


def _do_objeto(objeto: object, origem: str, tipo: type, montar: Callable[[dict, str], object]):
    if isinstance(objeto, tipo):
        return objeto
    if isinstance(objeto, dict):
        return montar(objeto, origem)
    if isinstance(objeto, str | Path):
        return montar(_ler_yaml(Path(objeto).read_text(encoding='utf-8'), str(objeto)), str(objeto))
    raise PerfilInvalidoError(
        f'{origem}: o entry point deve devolver um {tipo.__name__}, um dict ou um caminho de YAML'
    )


def _ler_yaml(texto: str, origem: str) -> dict:
    try:
        dados = yaml.safe_load(texto)
    except yaml.YAMLError as erro:
        raise PerfilInvalidoError(f'{origem}: {erro}') from erro
    if not isinstance(dados, dict):
        raise PerfilInvalidoError(f'{origem}: o perfil deve ser um mapeamento')
    return dados
