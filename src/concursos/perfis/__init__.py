"""Perfis de banca: YAML embutido no pacote ou registrado por outro pacote no entry point `concurso.banca`."""

import importlib
from collections.abc import Callable
from functools import cache
from importlib.metadata import entry_points
from importlib.resources import files
from pathlib import Path

import yaml

from concursos.perfis.banca import FORMATOS, SEGMENTACOES, PerfilBanca, PerfilInvalidoError, de_dict

__all__ = [
    'FORMATOS',
    'SEGMENTACOES',
    'PerfilBanca',
    'PerfilInvalidoError',
    'de_dict',
    'ids_de_banca',
    'perfil_da_banca',
    'perfis_de_banca',
    'resolver_funcao',
]

GRUPO_BANCA = 'concurso.banca'
PASTA_EMBUTIDOS = 'bancas'


@cache
def perfis_de_banca() -> tuple[PerfilBanca, ...]:
    """Embutidos e instalados, na ordem de detecção; um instalado com o id de um embutido o substitui."""
    por_id = {perfil.id: perfil for perfil in _embutidos()}
    for ponto in entry_points(group=GRUPO_BANCA):
        perfil = _perfil_do_objeto(ponto.load(), ponto.name)
        por_id[perfil.id] = perfil
    return tuple(sorted(por_id.values(), key=lambda perfil: (perfil.ordem, perfil.id)))


def ids_de_banca() -> tuple[str, ...]:
    return tuple(perfil.id for perfil in perfis_de_banca())


def perfil_da_banca(banca: str) -> PerfilBanca:
    for perfil in perfis_de_banca():
        if perfil.id == banca:
            return perfil
    raise PerfilInvalidoError(f"banca '{banca}' sem perfil (use {', '.join(ids_de_banca())})")


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


def _embutidos() -> list[PerfilBanca]:
    pasta = files('concursos.perfis') / PASTA_EMBUTIDOS
    return [
        _perfil_do_yaml(arquivo.read_text(encoding='utf-8'), arquivo.name)
        for arquivo in sorted(pasta.iterdir(), key=lambda a: a.name)
        if arquivo.name.endswith('.yaml')
    ]


def _perfil_do_objeto(objeto: object, origem: str) -> PerfilBanca:
    if isinstance(objeto, PerfilBanca):
        return objeto
    if isinstance(objeto, dict):
        return de_dict(objeto, origem)
    if isinstance(objeto, str | Path):
        return _perfil_do_yaml(Path(objeto).read_text(encoding='utf-8'), str(objeto))
    raise PerfilInvalidoError(
        f'{origem}: o entry point deve devolver um PerfilBanca, um dict ou um caminho de YAML'
    )


def _perfil_do_yaml(texto: str, origem: str) -> PerfilBanca:
    try:
        dados = yaml.safe_load(texto)
    except yaml.YAMLError as erro:
        raise PerfilInvalidoError(f'{origem}: {erro}') from erro
    if not isinstance(dados, dict):
        raise PerfilInvalidoError(f'{origem}: o perfil deve ser um mapeamento')
    return de_dict(dados, origem)
