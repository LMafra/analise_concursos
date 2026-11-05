"""Download assistido: o usuário baixa os PDFs no navegador dele, e o app os importa da pasta de downloads."""

import logging
import re
import shutil
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from concursos import relatorio_html

logger = logging.getLogger(__name__)

EXTENSOES_PARCIAIS = ('.crdownload', '.part', '.partial', '.download', '.tmp')
FOLGA_SEGUNDOS = 5
_SUFIXO_COPIA = re.compile(r'\s*\(\d+\)$')
_USUARIOS_DO_SISTEMA = {'public', 'default', 'default user', 'all users'}


def pasta_de_downloads(configurada: str, raiz_windows: Path = Path('/mnt/c/Users')) -> Path:
    """A configurada; no WSL, a `Downloads` do usuário do Windows (a mais recente, se houver mais de um)."""
    if configurada:
        return Path(configurada).expanduser()
    if relatorio_html._no_wsl() and raiz_windows.is_dir():
        candidatas = [
            pasta / 'Downloads'
            for pasta in raiz_windows.iterdir()
            if pasta.name.lower() not in _USUARIOS_DO_SISTEMA and (pasta / 'Downloads').is_dir()
        ]
        if candidatas:
            return max(candidatas, key=lambda p: p.stat().st_mtime)
    return Path.home() / 'Downloads'


def _comparavel(nome: str) -> str:
    caminho = Path(nome.lower())
    return _SUFIXO_COPIA.sub('', caminho.stem).replace('-', '_').replace(' ', '_') + caminho.suffix


def casa(nome_baixado: str, esperado: str) -> bool:
    """`gabaritos.pdf` casa com `gabaritos (1).pdf` (cópia do navegador); hífen e sublinhado se equivalem."""
    return _comparavel(nome_baixado) == _comparavel(esperado)


def _baixados(pasta: Path, desde: float) -> list[Path]:
    if not pasta.is_dir():
        return []
    arquivos = []
    for caminho in pasta.iterdir():
        if not caminho.is_file() or caminho.suffix.lower() in EXTENSOES_PARCIAIS:
            continue
        try:
            estado = caminho.stat()
        except OSError:
            continue
        if estado.st_mtime >= desde and estado.st_size > 0:
            arquivos.append(caminho)
    return sorted(arquivos, key=lambda p: p.stat().st_mtime)


def esperar_downloads(
    pasta: Path,
    esperados: Iterable[str],
    desde: float,
    timeout: float,
    *,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
    intervalo: float = 2.0,
    silencio: float = 60.0,
) -> dict[str, Path]:
    """Os esperados que apareceram na pasta depois de `desde` (hora do arquivo), até todos, até o timeout ou
    até `silencio` segundos sem arquivo novo depois do primeiro (o usuário pode não querer todos).

    Um arquivo ainda em download (`.crdownload`, `.part`) só conta quando o navegador o renomeia."""
    esperados = list(esperados)
    fim = relogio() + timeout
    encontrados: dict[str, Path] = {}
    ultimo: float | None = None
    while True:
        for baixado in _baixados(pasta, desde):
            for esperado in esperados:
                if esperado not in encontrados and casa(baixado.name, esperado):
                    encontrados[esperado] = baixado
                    ultimo = relogio()
                    logger.info('download: %s encontrado em %s', esperado, pasta)
        agora = relogio()
        quieto = ultimo is not None and agora - ultimo >= silencio
        if len(encontrados) == len(esperados) or agora >= fim or quieto:
            return encontrados
        dormir(intervalo)


def importar(encontrados: dict[str, Path], destino: Path) -> list[Path]:
    """Copia com o nome da página (sem o `(1)` do navegador); o original fica nos downloads."""
    destino.mkdir(parents=True, exist_ok=True)
    copiados = []
    for nome, origem in encontrados.items():
        alvo = destino / nome
        shutil.copy2(origem, alvo)
        copiados.append(alvo)
    return copiados


def instante_atual() -> float:
    """Com folga: a hora dos arquivos do Windows vista do WSL pode diferir em alguns segundos."""
    return time.time() - FOLGA_SEGUNDOS
