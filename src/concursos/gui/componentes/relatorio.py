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


def url_do_relatorio(caminho: Path, *, raiz: Path | None = None) -> str:
    """`raiz` é a pasta do candidato (serve links relativos entre index e concursos)."""
    base = (raiz or caminho.parent).resolve()
    relativo = caminho.resolve().relative_to(base).as_posix()
    return f'{endereco_da_pasta(base)}/{relativo}?v={caminho.stat().st_mtime_ns}'


def relatorio(indice: Path, *, raiz: Path | None = None) -> ui.element:
    return (
        ui.element('iframe')
        .props(f'src="{url_do_relatorio(indice, raiz=raiz)}" title="Relatório da análise"')
        .classes('w-full rounded border')
        .style('height: 75vh')
        .mark('relatorio')
    )


def mostrar_relatorio(quadro: ui.element, caminho: Path, *, raiz: Path) -> None:
    quadro.props(f'src="{url_do_relatorio(caminho, raiz=raiz)}" title="Relatório da análise"')
