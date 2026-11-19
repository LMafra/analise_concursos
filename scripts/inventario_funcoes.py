#!/usr/bin/env python3
"""Inventário AST de funções em src/concursos/ para docs/arquitetura-plataforma.md.

Uso:
  uv run python scripts/inventario_funcoes.py > /tmp/inventario_f.md
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src' / 'concursos'


def camada(rel: Path) -> str:
    parts = rel.parts
    if not parts:
        return 'raiz'
    top = parts[0]
    mapa = {
        'cli': 'CLI',
        'gui': 'GUI',
        'aplicacao': 'aplicacao',
        'analytics': 'pipeline/analytics',
        'integracoes': 'integracoes',
        'estudo': 'estudo',
        'livros': 'livros',
        'perfis': 'perfis',
        'config': 'config',
        'empacotado.py': 'empacotamento',
    }
    if rel.name in ('relatorio.py', 'relatorio_html.py', 'graficos.py', 'exportacao.py', 'consolidado.py'):
        return 'relatorios'
    if rel.name in ('pipeline.py', 'folha.py', 'correcao.py', 'topicos.py', 'gabarito.py', 'edital.py'):
        return 'pipeline'
    if top in mapa:
        return mapa[top]
    if rel.name == 'atualizador.py':
        return 'empacotamento'
    return 'raiz'


def coletar() -> list[tuple[str, str, str, int, str, bool]]:
    rows: list[tuple[str, str, str, int, str, bool]] = []
    for path in sorted(SRC.rglob('*.py')):
        rel = path.relative_to(SRC)
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError:
            continue
        for node in tree.body:
            _visitar(node, rel, '', rows)
    return rows


def _visitar(
    node: ast.AST,
    rel: Path,
    prefixo: str,
    rows: list[tuple[str, str, str, int, str, bool]],
) -> None:
    if isinstance(node, ast.ClassDef):
        nome = f'{prefixo}{node.name}.' if not prefixo else f'{prefixo}{node.name}.'
        for filho in node.body:
            _visitar(filho, rel, nome, rows)
        return
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        qual = f'{prefixo}{node.name}'
        privado = node.name.startswith('_') and not node.name.startswith('__')
        rows.append(
            (
                qual,
                str(rel).replace('\\', '/'),
                camada(rel),
                node.lineno,
                'async' if isinstance(node, ast.AsyncFunctionDef) else 'def',
                privado,
            )
        )


def main() -> int:
    rows = coletar()
    print(f'<!-- gerado por scripts/inventario_funcoes.py; {len(rows)} funções -->')
    print('| ID | Função | Onde vive | Camada | Tipo | Privado |')
    print('|---|---|---|---|---|---|')
    for i, (qual, arquivo, cam, linha, tipo, privado) in enumerate(rows, start=1):
        fid = f'F-{i:04d}'
        onde = f'`{arquivo}:{linha}`'
        print(
            f'| {fid} | `{qual}` | {onde} | {cam} | {tipo} | '
            f'{"sim" if privado else "não"} |'
        )
    print(f'\nTotal: {len(rows)} funções. Fonte: AST de `src/concursos/`.', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
