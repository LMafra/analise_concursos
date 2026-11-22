#!/usr/bin/env python3
"""Roda pip-audit no requirements exportado, respeitando docs/arquitetura/cve-ignorados.toml."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
IGNORADOS = RAIZ / 'docs' / 'arquitetura' / 'cve-ignorados.toml'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('requirements', type=Path)
    args = parser.parse_args(argv)
    dados = tomllib.loads(IGNORADOS.read_text(encoding='utf-8'))
    cmd = ['uvx', 'pip-audit', '-r', str(args.requirements)]
    for item in dados.get('ignorar', []):
        cmd.extend(['--ignore-vuln', item['id']])
    return subprocess.call(cmd)


if __name__ == '__main__':
    sys.exit(main())
