from hashlib import sha256
from pathlib import Path

from nicegui import app, ui

PREFIXO = '/_analises'
_SERVIDAS: dict[Path, str] = {}


def endereco_da_pasta(pasta: Path) -> str:
    """Cada pasta de análises é servida uma vez (só em 127.0.0.1), num endereço que não mostra o caminho.

    Sem cache: o relatório e os gráficos mudam a cada análise."""
    pasta = pasta.resolve()
    if pasta not in _SERVIDAS:
        url = f'{PREFIXO}/{sha256(str(pasta).encode()).hexdigest()[:16]}'
        app.add_static_files(url, pasta, max_cache_age=0)
        _SERVIDAS[pasta] = url
    return _SERVIDAS[pasta]


def relatorio(indice: Path) -> ui.element:
    url = f'{endereco_da_pasta(indice.parent)}/{indice.name}?v={indice.stat().st_mtime_ns}'
    return (
        ui.element('iframe')
        .props(f'src="{url}" title="Relatório da análise"')
        .classes('w-full rounded border')
        .style('height: 75vh')
        .mark('relatorio')
    )
