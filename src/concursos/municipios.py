"""A lista de municípios do IBGE embutida no app (`dados/municipios_ibge.json`), para os filtros do PCI sem
rede. Ela é regenerada à mão por `scripts/atualizar_municipios.py` antes de uma release."""

import json
from functools import cache
from importlib import resources

from concursos.texto import normalizar

REGIAO_DA_UF = {
    **dict.fromkeys(('AC', 'AM', 'AP', 'PA', 'RO', 'RR', 'TO'), 'Norte'),
    **dict.fromkeys(('AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE'), 'Nordeste'),
    **dict.fromkeys(('DF', 'GO', 'MS', 'MT'), 'Centro-Oeste'),
    **dict.fromkeys(('ES', 'MG', 'RJ', 'SP'), 'Sudeste'),
    **dict.fromkeys(('PR', 'RS', 'SC'), 'Sul'),
}


@cache
def _por_uf() -> dict[str, tuple[str, ...]]:
    texto = resources.files('concursos').joinpath('dados/municipios_ibge.json').read_text(encoding='utf-8')
    return {uf: tuple(nomes) for uf, nomes in json.loads(texto).items()}


def ufs() -> list[str]:
    return sorted(_por_uf())


def municipios(uf: str | None) -> list[str]:
    """Os nomes da UF (sigla em qualquer caixa), em ordem alfabética; vazio para UF desconhecida ou vazia."""
    return list(_por_uf().get((uf or '').strip().upper(), ()))


def cidade_da_uf(cidade: str, uf: str | None) -> str | None:
    """O nome oficial da cidade na UF, sem diferença de acento e caixa; None se ela não for da UF."""
    procurada = normalizar(cidade.strip()).lower()
    return next((nome for nome in municipios(uf) if normalizar(nome).lower() == procurada), None)
