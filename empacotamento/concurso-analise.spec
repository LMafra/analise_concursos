# Build onedir do concurso-analise: `pyinstaller empacotamento/concurso-analise.spec` a partir de
# `uv sync --locked --no-dev --extra gui --extra llm --extra pci --group empacotamento`.
#
# Dois executáveis no mesmo diretório: `concurso-analise` (janela, sem console no Windows) e
# `concurso-analise-cli` (console, para a CLI e o smoke). O Tesseract (em `_internal/tesseract`) e a captura do
# TEC entram quando os scripts de `empacotamento/tesseract/` e o `node tec-erros/scripts/build.mjs` já rodaram.
import shutil
import sys
from importlib.metadata import version
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

PASTA = Path(SPECPATH)
RAIZ = PASTA.parent
CONSTRUCAO = PASTA / 'construcao'
NOME = 'concurso-analise'
VERSAO = version(NOME)


def opcional(origem: Path, destino: str) -> list[tuple[str, str]]:
    return [(str(origem), destino)] if origem.exists() else []


datas = [
    *opcional(CONSTRUCAO / 'LICENSES', 'LICENSES'),
    (str(PASTA / 'LICENSES' / 'LEIA-ME.md'), 'LICENSES'),
    *collect_data_files('nicegui'),
]
if (RAIZ / 'tec-erros' / 'dist' / 'caderno.html').is_file():
    datas.append((str(RAIZ / 'tec-erros' / 'dist'), 'tec-erros'))

a = Analysis(
    [str(PASTA / 'launcher.py')],
    pathex=[str(RAIZ / 'src')],
    hookspath=[str(PASTA / 'hooks')],
    datas=datas,
    excludes=['IPython', 'jupyter', 'jupyter_client', 'nbformat', 'nbconvert', 'jedi', 'tkinter', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
icone = PASTA / 'icones' / ('concurso-analise.ico' if sys.platform == 'win32' else 'concurso-analise.icns')

janela = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NOME,
    console=False,
    icon=str(icone) if icone.exists() else None,
)
cli = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=f'{NOME}-cli',
    console=True,
    icon=str(icone) if icone.exists() else None,
)
coll = COLLECT(janela, cli, a.binaries, a.datas, name=NOME)


def copiar_tesseract(destino: Path) -> None:
    """Fora do Analysis: o PyInstaller analisaria as bibliotecas do Tesseract e poria na raiz do pacote as
    dependências delas (no Linux, a libstdc++ do AppImage, feita para uma glibc mais nova que a do build)."""
    if (CONSTRUCAO / 'tesseract').is_dir():
        shutil.copytree(CONSTRUCAO / 'tesseract', destino / 'tesseract', symlinks=True, dirs_exist_ok=True)


copiar_tesseract(Path(DISTPATH) / NOME / '_internal')

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name=f'{NOME}.app',
        icon=str(icone) if icone.exists() else None,
        bundle_identifier='br.lmafra.concurso-analise',
        version=VERSAO,
        info_plist={'NSHighResolutionCapable': True, 'CFBundleShortVersionString': VERSAO},
    )
    copiar_tesseract(Path(DISTPATH) / f'{NOME}.app' / 'Contents' / 'Frameworks')
