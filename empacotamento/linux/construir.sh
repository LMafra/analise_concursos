#!/usr/bin/env bash
# Build do AppImage dentro de quay.io/pypa/manylinux_2_28_x86_64: com a glibc 2.28, o executável roda nas
# distribuições de 2019 em diante. O Python é o gerenciado pelo uv, porque o do manylinux não tem a
# libpython compartilhada que o PyInstaller exige.
#
# Antes, gere a captura do TEC (`node tec-erros/scripts/build.mjs`) para ela ir junto.
#
# Uso: bash empacotamento/linux/construir.sh
set -euo pipefail

UV_VERSAO=${UV_VERSAO:-0.13.0}
RAIZ=$(cd "$(dirname "$0")/../.." && pwd)
cd "$RAIZ"

if ! command -v uv >/dev/null; then
    curl -LsSf "https://astral.sh/uv/$UV_VERSAO/install.sh" | env UV_INSTALL_DIR=/usr/local/bin sh
fi
export UV_PYTHON_PREFERENCE=only-managed

uv sync --locked --no-dev --extra gui --extra llm --extra pci --group empacotamento --python 3.12
bash empacotamento/tesseract/obter_linux.sh
uv run --no-sync python empacotamento/coletar_licencas.py
uv run --no-sync pyinstaller --noconfirm --distpath dist --workpath build empacotamento/concurso-analise.spec
VERSAO=$(uv run --no-sync python -c "from importlib.metadata import version; print(version('concurso-analise'))")
bash empacotamento/linux/montar_appimage.sh "$VERSAO"
