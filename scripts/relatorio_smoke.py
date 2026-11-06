"""Junta os relatórios dos gates de máquina limpa no `RELATORIO-SMOKE.md` da release.

Roda no job `publicar` do release.yml, depois de baixar os artefatos `relatorio-*`:

    python3 scripts/relatorio_smoke.py 0.6.0 "$GITHUB_SHA" relatorios dist/RELATORIO-SMOKE.md

Sem um dos relatórios obrigatórios, sai com erro: a release não nasce com um gate faltando.
"""

import argparse
import sys
from pathlib import Path

OBRIGATORIOS = ('smoke-windows.md', 'smoke-linux-debian-12.md', 'smoke-linux-ubuntu-22-04.md')


def montar(versao: str, commit: str, pasta: Path) -> str:
    faltando = [nome for nome in OBRIGATORIOS if not (pasta / nome).is_file()]
    if faltando:
        raise SystemExit(f'relatório de smoke faltando em {pasta}: {", ".join(faltando)}')
    partes = [
        f'# Relatório de smoke: concurso-analise {versao}\n',
        f'Gerado pelo release.yml no commit `{commit}`. Cada seção é o gate de máquina limpa de um sistema: '
        'instalação, `--smoke` (versão, partida, perfis, Tesseract com português e OCR numa imagem gerada, '
        'GUI em 127.0.0.1) e `scripts/smoke.py congelado` (onboarding, análise e idempotência).\n',
        'A release só é publicada depois do checklist manual de `docs/spec-fase6.md`.\n',
    ]
    # O Set-Content do PowerShell 5 grava BOM.
    partes += [(pasta / nome).read_text(encoding='utf-8-sig').strip() + '\n' for nome in OBRIGATORIOS]
    return '\n'.join(partes)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('versao')
    parser.add_argument('commit')
    parser.add_argument('relatorios', type=Path)
    parser.add_argument('destino', type=Path)
    args = parser.parse_args(argv)
    args.destino.write_text(montar(args.versao, args.commit, args.relatorios), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1:])
