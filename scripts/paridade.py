"""Retrato de paridade das saídas da análise: o hash de cada arquivo, para provar que um refactor não mudou nada.

Uso (rode a análise com --forcar antes de cada retrato):
    python scripts/paridade.py retrato analises .paridade/retrato.json
    python scripts/paridade.py comparar analises .paridade/retrato.json

A chave é o caminho relativo à pasta de análises. Depois da migração para o layout multi-candidato, compare
contra a pasta do candidato (analises/<slug>). O manifesto fica de fora: ele guarda os hashes de entrada e a
versão da análise, que mudam legitimamente.
"""

import hashlib
import json
import sys
from pathlib import Path

IGNORADOS = {'.manifesto.json'}


def retratar(raiz: Path) -> dict[str, str]:
    return {
        caminho.relative_to(raiz).as_posix(): hashlib.sha256(caminho.read_bytes()).hexdigest()
        for caminho in sorted(raiz.rglob('*'))
        if caminho.is_file() and caminho.name not in IGNORADOS
    }


def comparar(antes: dict[str, str], depois: dict[str, str]) -> list[str]:
    diferencas = [f'sumiu: {chave}' for chave in sorted(antes.keys() - depois.keys())]
    diferencas += [f'novo: {chave}' for chave in sorted(depois.keys() - antes.keys())]
    diferencas += [
        f'mudou: {chave}' for chave in sorted(antes.keys() & depois.keys()) if antes[chave] != depois[chave]
    ]
    return diferencas


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] not in {'retrato', 'comparar'}:
        sys.stderr.write(__doc__)
        return 2
    comando, raiz, arquivo = argv[0], Path(argv[1]), Path(argv[2])
    atual = retratar(raiz)
    if comando == 'retrato':
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(json.dumps(atual, indent=2, sort_keys=True), encoding='utf-8')
        sys.stdout.write(f'{len(atual)} arquivos retratados em {arquivo}\n')
        return 0
    diferencas = comparar(json.loads(arquivo.read_text(encoding='utf-8')), atual)
    sys.stdout.write(
        '\n'.join(diferencas) + '\n' if diferencas else f'paridade: {len(atual)} arquivos iguais\n'
    )
    return 1 if diferencas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
