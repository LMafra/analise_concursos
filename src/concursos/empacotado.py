"""O executável do PyInstaller: o Python, o Tesseract e a captura do TEC vão dentro dele.

Sem argumentos, abre a GUI; com argumentos, é a CLI; `--smoke` confere o pacote e sai.
"""

import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from importlib.metadata import version
from pathlib import Path

ARGUMENTO_SMOKE = '--smoke'
VARIAVEL_SEM_OCR = 'CONCURSO_SMOKE_SEM_OCR'
TIMEOUT_SERVIDOR = 120


class SmokeError(Exception):
    pass


def pasta_embutida() -> Path | None:
    if not getattr(sys, 'frozen', False):
        return None
    base = getattr(sys, '_MEIPASS', None)
    return Path(base) if base else Path(sys.executable).parent


def embutido(caminho: str | Path) -> bool:
    pasta = pasta_embutida()
    return pasta is not None and Path(caminho).resolve().is_relative_to(pasta.resolve())


def preparar_ambiente(base: Path) -> None:
    tesseract = base / 'tesseract'
    binarios = tesseract / 'bin' if (tesseract / 'bin').is_dir() else tesseract
    if binarios.is_dir():
        os.environ['PATH'] = str(binarios) + os.pathsep + os.environ.get('PATH', '')
    if (tesseract / 'tessdata').is_dir():
        os.environ['TESSDATA_PREFIX'] = str(tesseract / 'tessdata')
    if sys.platform.startswith('linux'):
        restaurar_bibliotecas_do_sistema()


def restaurar_bibliotecas_do_sistema() -> None:
    """O bootloader do PyInstaller põe as bibliotecas do pacote no `LD_LIBRARY_PATH`, e os programas do
    sistema abertos pelo app (navegador, `xdg-open`) quebrariam com elas. O processo atual não é afetado: o
    carregador lê a variável só na partida."""
    original = os.environ.pop('LD_LIBRARY_PATH_ORIG', None)
    if original is None:
        os.environ.pop('LD_LIBRARY_PATH', None)
    else:
        os.environ['LD_LIBRARY_PATH'] = original


def garantir_saidas() -> None:
    """Na janela sem console do Windows, `sys.stdout` e `sys.stderr` são None, e quem escreve neles quebra."""
    for nome in ('stdout', 'stderr'):
        if getattr(sys, nome) is None:
            setattr(sys, nome, open(os.devnull, 'w', encoding='utf-8'))  # noqa: SIM115


def principal(argv: list[str]) -> int:
    if (base := pasta_embutida()) is not None:
        preparar_ambiente(base)
    garantir_saidas()
    if argv == [ARGUMENTO_SMOKE]:
        return conferir_pacote()
    from concursos.cli import main

    return main(argv or ['gui'])


def conferir_versao() -> str:
    return version('concurso-analise')


def conferir_perfis() -> tuple[str, ...]:
    from concursos.perfis import ids_de_banca, ids_de_ocr

    if not ids_de_ocr():
        raise SmokeError('nenhum perfil de OCR carregado')
    return ids_de_banca()


def conferir_tesseract() -> str:
    caminho = shutil.which('tesseract')
    if caminho is None:
        if os.environ.get(VARIAVEL_SEM_OCR):
            return f'Tesseract dispensado ({VARIAVEL_SEM_OCR})'
        raise SmokeError('Tesseract não encontrado no executável nem no PATH')
    saida = subprocess.run(
        [caminho, '--list-langs'], capture_output=True, text=True, timeout=30, check=False
    ).stdout
    if 'por' not in saida.split():
        raise SmokeError(f'Tesseract em {caminho} sem o idioma português (por)')
    base = pasta_embutida()
    if base is not None and (base / 'tesseract').is_dir() and not embutido(caminho):
        raise SmokeError(f'o executável traz o Tesseract, mas o do PATH ({caminho}) veio na frente')
    return f'Tesseract {"embutido" if embutido(caminho) else "do sistema"} em {caminho}, com português'


def responde(url: str, timeout: float, intervalo: float = 0.5) -> bool:
    fim = time.monotonic() + timeout
    while time.monotonic() < fim:
        try:
            with urllib.request.urlopen(url, timeout=5) as resposta:
                if resposta.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(intervalo)
    return False


def conferir_servidor() -> str:
    """Sobe a GUI no modo navegador, sem abrir navegador, pede a página inicial e desliga o servidor."""
    from nicegui import app, native

    from concursos.gui.app import HOST, executar

    porta = native.find_open_port()
    url = f'http://{HOST}:{porta}/'
    resultado: dict[str, bool] = {}

    def conferir() -> None:
        resultado['ok'] = responde(url, TIMEOUT_SERVIDOR)
        app.shutdown()

    app.on_startup(lambda: threading.Thread(target=conferir, daemon=True).start())
    executar(navegador=True, abrir=False, porta=porta)
    if not resultado.get('ok'):
        raise SmokeError(f'a GUI não respondeu em {url}')
    return f'GUI respondeu em {url}'


def conferir_pacote() -> int:
    etapas = [
        lambda: f'versão {conferir_versao()}',
        lambda: f'perfis de banca: {", ".join(conferir_perfis())}',
        conferir_tesseract,
        conferir_servidor,
    ]
    for etapa in etapas:
        try:
            sys.stdout.write(f'smoke: {etapa()}\n')
        except Exception as erro:  # noqa: BLE001 - o smoke relata qualquer falha e sai com 1
            sys.stdout.write(f'smoke: FALHOU: {erro}\n')
            return 1
    sys.stdout.write('smoke: ok\n')
    return 0
