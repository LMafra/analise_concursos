#!/usr/bin/env bash
#
# Converte cada notebooks/NN_*.py (jupytext, formato percent) em .ipynb e o executa do zero, em ordem.
# Para no primeiro notebook que falhar. Uso: scripts/rodar_notebooks.sh [notebooks/00_carregamento.py ...]

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $# -gt 0 ]]; then
  notebooks=("$@")
else
  notebooks=(notebooks/[0-9][0-9]_*.py)
fi

for script in "${notebooks[@]}"; do
  echo "==> ${script}"
  uv run --group analise jupytext --quiet --to ipynb "${script}"
  uv run --group analise jupyter nbconvert --to notebook --execute --inplace "${script%.py}.ipynb"
done
