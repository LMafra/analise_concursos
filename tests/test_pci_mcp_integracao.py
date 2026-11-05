"""Contrato com o servidor real do PCI: rode com `PCI_MCP_INTEGRACAO=1 uv run --extra pci pytest -m pci_mcp`."""

import os

import pytest
from transporte_pci import fixture

from concursos.integracoes.pci_mcp import URL_PADRAO, ProvaAnteriorPci, TransporteSdk, ler_concurso, ler_prova

pytestmark = [
    pytest.mark.pci_mcp,
    pytest.mark.skipif(
        os.environ.get('PCI_MCP_INTEGRACAO') != '1',
        reason='defina PCI_MCP_INTEGRACAO=1 para usar o servidor real',
    ),
]


@pytest.fixture(scope='module')
def transporte():
    pytest.importorskip('mcp')
    with TransporteSdk(URL_PADRAO, timeout=30) as aberto:
        yield aberto


def test_tools_list_real_igual_ao_gravado(transporte):
    """Se falhar, o servidor mudou: rode scripts/gravar_fixtures_pci.py e revise o diff."""
    assert transporte.ferramentas() == frozenset(f['name'] for f in fixture('tools_list'))


def test_busca_por_cargo_real_tem_o_formato_esperado(transporte):
    dados = transporte.chamar('buscar_por_cargo', {'cargo': 'analista'})
    assert dados['meta']['data_atual']
    for item in dados['data']:
        ler_concurso(item, dados['meta']['data_atual'])


def test_pesquisa_de_provas_real_tem_link_de_pagina(transporte):
    dados = transporte.chamar('pesquisar_provas', {'termo': 'auditor fiscal'})
    provas: list[ProvaAnteriorPci] = [ler_prova(item) for item in dados['data']]
    assert provas and all(p.link.startswith('https://www.pciconcursos.com.br/provas/') for p in provas)
