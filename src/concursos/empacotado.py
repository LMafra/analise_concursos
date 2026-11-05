"""O executável do PyInstaller: o Python, o Tesseract e a captura do TEC vão dentro dele.

Sem argumentos, abre a GUI; com argumentos, é a CLI; `--smoke` confere o pacote e sai.
"""

import codecs
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from importlib.metadata import version
from pathlib import Path

ARGUMENTO_SMOKE = '--smoke'
VARIAVEL_SEM_OCR = 'CONCURSO_SMOKE_SEM_OCR'
VARIAVEL_LIMITE_PARTIDA = 'CONCURSO_SMOKE_LIMITE_PARTIDA'
TIMEOUT_SERVIDOR = 120
TEXTO_OCR = 'CONCURSO 2026'
_IMPORTADO_EM = time.monotonic()


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
    """Na janela sem console do Windows, `sys.stdout` e `sys.stderr` são None, e quem escreve neles quebra.

    Com a saída redirecionada, o Windows dá a codificação do sistema (cp1252), que não tem o ✓ do doctor;
    o executável não tem o `PYTHONUTF8` do ambiente de desenvolvimento."""
    for nome in ('stdout', 'stderr'):
        fluxo = getattr(sys, nome)
        if fluxo is None:
            setattr(sys, nome, open(os.devnull, 'w', encoding='utf-8'))  # noqa: SIM115
        elif codecs.lookup(fluxo.encoding or 'ascii').name != 'utf-8' and hasattr(fluxo, 'reconfigure'):
            fluxo.reconfigure(encoding='utf-8', errors='replace')


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
    origem = 'embutido' if embutido(caminho) else 'do sistema'
    return f'Tesseract {origem} em {caminho}, com português; {conferir_ocr(caminho)}'


def conferir_ocr(tesseract: str) -> str:
    """Lê uma imagem gerada na hora: `--list-langs` passa mesmo com uma biblioteca de imagem faltando."""
    from PIL import Image, ImageDraw, ImageFont

    with tempfile.TemporaryDirectory() as pasta:
        imagem = Path(pasta) / 'ocr.png'
        tela = Image.new('L', (900, 160), 255)
        ImageDraw.Draw(tela).text((30, 40), TEXTO_OCR, fill=0, font=ImageFont.load_default(size=64))
        tela.save(imagem)
        resultado = subprocess.run(
            [tesseract, str(imagem), 'stdout', '-l', 'por'],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    if resultado.returncode != 0:
        raise SmokeError(
            f'o Tesseract saiu com código {resultado.returncode}: {resultado.stderr.strip()[-200:]}'
        )
    if 'CONCURSO' not in resultado.stdout.upper():
        raise SmokeError(
            f'o Tesseract não leu "{TEXTO_OCR}" na imagem de teste (leu {resultado.stdout.strip()!r})'
        )
    return f'OCR leu "{TEXTO_OCR}"'


def segundos_desde_o_inicio() -> float:
    """Desde a criação do processo, quando o sistema informa; senão, desde a importação deste módulo."""
    try:
        if sys.platform.startswith('linux'):
            return _segundos_linux()
        if sys.platform == 'win32':
            return _segundos_windows()
    except (OSError, ValueError, AttributeError):
        pass
    return max(time.monotonic() - _IMPORTADO_EM, 1e-6)


def _segundos_linux() -> float:
    campos = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    inicio = int(campos[19]) / os.sysconf('SC_CLK_TCK')
    ligado = float(Path('/proc/uptime').read_text().split()[0])
    return max(ligado - inicio, 1e-6)


def _segundos_windows() -> float:
    import ctypes
    from ctypes import wintypes

    criacao, saida, kernel, usuario, agora = (wintypes.FILETIME() for _ in range(5))
    k32 = ctypes.windll.kernel32
    if not k32.GetProcessTimes(
        k32.GetCurrentProcess(),
        ctypes.byref(criacao),
        ctypes.byref(saida),
        ctypes.byref(kernel),
        ctypes.byref(usuario),
    ):
        raise OSError('GetProcessTimes falhou')
    k32.GetSystemTimeAsFileTime(ctypes.byref(agora))

    def valor(tempo: wintypes.FILETIME) -> int:
        return (tempo.dwHighDateTime << 32) | tempo.dwLowDateTime

    return max((valor(agora) - valor(criacao)) / 10_000_000, 1e-6)


def _decimal(segundos: float) -> str:
    return f'{segundos:.1f}'.replace('.', ',')


def conferir_partida(segundos: float) -> str:
    bruto = os.environ.get(VARIAVEL_LIMITE_PARTIDA)
    if not bruto:
        return f'partida: {_decimal(segundos)} s'
    try:
        limite = float(bruto.replace(',', '.'))
    except ValueError as erro:
        raise SmokeError(f'{VARIAVEL_LIMITE_PARTIDA}={bruto!r} não é um número de segundos') from erro
    texto_limite = f'{limite:g}'.replace('.', ',')
    if segundos > limite:
        raise SmokeError(f'partida de {_decimal(segundos)} s passou do limite de {texto_limite} s')
    return f'partida: {_decimal(segundos)} s (limite {texto_limite} s)'


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
    resultado: dict[str, float] = {}

    def conferir() -> None:
        if responde(url, TIMEOUT_SERVIDOR):
            resultado['partida'] = segundos_desde_o_inicio()
        app.shutdown()

    app.on_startup(lambda: threading.Thread(target=conferir, daemon=True).start())
    executar(navegador=True, abrir=False, porta=porta)
    if 'partida' not in resultado:
        raise SmokeError(f'a GUI não respondeu em {url}')
    return f'GUI respondeu em {url}; {conferir_partida(resultado["partida"])}'


def conferir_pacote() -> int:
    etapas = [
        lambda: f'versão {conferir_versao()}',
        conferir_servidor,
        lambda: f'perfis de banca: {", ".join(conferir_perfis())}',
        conferir_tesseract,
    ]
    for etapa in etapas:
        try:
            sys.stdout.write(f'smoke: {etapa()}\n')
        except Exception as erro:  # noqa: BLE001 - o smoke relata qualquer falha e sai com 1
            sys.stdout.write(f'smoke: FALHOU: {erro}\n')
            return 1
    sys.stdout.write('smoke: ok\n')
    return 0
