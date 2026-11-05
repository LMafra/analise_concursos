"""Regrava as respostas reais do servidor MCP da PCI Concursos em tests/fixtures/pci/.

Uso (precisa do extra `pci` e de rede):
    uv run --extra pci python scripts/gravar_fixtures_pci.py

Grava o `tools/list` (nome e schema de cada ferramenta), uma resposta de cada ferramenta como o SDK a entrega
(`is_error` e o texto) e a página HTML de uma prova, onde ficam os `data-arquivo`. Nunca chama `/provas/link`
nem baixa PDF. Depois de regravar, confira com `git diff tests/fixtures/pci` o que mudou no contrato.
"""

import asyncio
import json
import sys
import urllib.request
from pathlib import Path

from mcp import Client

URL = 'https://mcp.pciconcursos.com.br/mcp'
DESTINO = Path(__file__).resolve().parent.parent / 'tests' / 'fixtures' / 'pci'
CHAMADAS = {
    'listar_concursos': {'regiao': 'sudeste'},
    'pesquisar_concursos': {'termo': 'receita', 'uf': 'sp'},
    'buscar_por_cargo': {'cargo': 'analista', 'uf': 'mg'},
    'buscar_por_cidade': {'uf': 'sp', 'cidade': 'campinas'},
    'pesquisar_provas': {'termo': 'auditor fiscal receita'},
}
EXTRAS = {
    'pesquisar_provas_vazio': ('pesquisar_provas', {'termo': 'xyzw inexistente 1901'}),
    'buscar_por_cargo_uf_invalida': ('buscar_por_cargo', {'cargo': 'analista', 'uf': 'xyz'}),
}
AGENTE = 'concurso-analise (fixtures de teste)'


def _gravar(nome: str, dados: object) -> None:
    caminho = DESTINO / f'{nome}.json'
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sys.stdout.write(f'gravado: {caminho.relative_to(DESTINO.parent.parent.parent)}\n')


async def _gravar_ferramentas() -> str:
    async with Client(URL, mode='legacy', read_timeout_seconds=30, cache=None) as cliente:
        ferramentas = (await cliente.list_tools()).tools
        _gravar(
            'tools_list',
            [
                {'name': f.name, 'inputSchema': f.input_schema}
                for f in sorted(ferramentas, key=lambda f: f.name)
            ],
        )
        chamadas = {nome: (nome, argumentos) for nome, argumentos in CHAMADAS.items()} | EXTRAS
        link_prova = ''
        for nome, (ferramenta, argumentos) in chamadas.items():
            resultado = await cliente.call_tool(ferramenta, argumentos)
            texto = resultado.content[0].text
            _gravar(
                nome,
                {
                    'ferramenta': ferramenta,
                    'argumentos': argumentos,
                    'is_error': bool(resultado.is_error),
                    'texto': texto,
                },
            )
            if nome == 'pesquisar_provas' and not resultado.is_error:
                link_prova = json.loads(texto)['data'][0]['link']
        return link_prova


def _gravar_pagina(link: str) -> None:
    requisicao = urllib.request.Request(link, headers={'User-Agent': AGENTE})
    with urllib.request.urlopen(requisicao, timeout=30) as resposta:
        html = resposta.read().decode('utf-8', errors='replace')
    caminho = DESTINO / 'pagina_prova.html'
    caminho.write_text(html, encoding='utf-8')
    sys.stdout.write(f'gravado: {caminho.name} ({link})\n')


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    link = asyncio.run(_gravar_ferramentas())
    if link:
        _gravar_pagina(link)
    return 0


if __name__ == '__main__':
    sys.exit(main())
