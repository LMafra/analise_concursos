"""Smoke test de ponta a ponta num concurso sintético. Só usa a biblioteca padrão, para rodar antes da instalação.

Uso:
    python scripts/smoke.py                                   # usa o concurso-analise do PATH
    python scripts/smoke.py uvx --from . concurso-analise     # o que o candidato roda
    python scripts/smoke.py congelado <concurso-analise-cli>  # o executável do PyInstaller

Confere, num projeto temporário com espaço e acento no caminho:
- `--dry-run --yes` num projeto novo não grava nada;
- `--yes` faz o onboarding e gera o index.html em até LIMITE_SEGUNDOS;
- duas execuções seguidas, e duas com `--dry-run`, não alteram nenhum mtime em analises/.

No modo `congelado`, antes: `--smoke` do executável (versão, perfis, Tesseract com português e a GUI em
127.0.0.1) e `doctor` sem erro.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LIMITE_SEGUNDOS = 300
CANDIDATO = 'ana'
CONCURSO_YAML = """\
banca: fgv
formato: multipla_escolha
pontuacao: simples
data_prova: {data}
edital:
  manual: edital_manual.yaml
provas:
  unica:
    gabarito: gabarito.txt
    itens: [1, 10]
"""
GABARITO = ''.join(f'{n} {letra}\n' for n, letra in enumerate('ABCDEABCDE', start=1))
RESPOSTAS = {
    'sintetico_2024': ('2024-03-10', 'ABCDEEDCBA'),
    'sintetico_2025': ('2025-03-09', 'ABCDEABCBA'),
}


def montar_projeto(raiz: Path) -> None:
    for nome, (data, respostas) in RESPOSTAS.items():
        pasta = raiz / 'provas' / nome
        (pasta / 'candidatos' / CANDIDATO).mkdir(parents=True)
        (pasta / 'concurso.yaml').write_text(CONCURSO_YAML.format(data=data), encoding='utf-8')
        (pasta / 'edital_manual.yaml').write_text('conhecimentos: []\n', encoding='utf-8')
        (pasta / 'gabarito.txt').write_text(GABARITO, encoding='utf-8')
        linhas = ''.join(f'{n} {letra}\n' for n, letra in enumerate(respostas, start=1))
        (pasta / 'candidatos' / CANDIDATO / 'respostas.txt').write_text(linhas, encoding='utf-8')


def rodar(comando: list[str], raiz: Path, *argumentos: str) -> float:
    ambiente = {**os.environ, 'CONCURSO_HOME': str(raiz / 'home'), 'CI': 'true', 'NO_COLOR': '1'}
    inicio = time.monotonic()
    resultado = subprocess.run(
        [*comando, *argumentos], cwd=raiz, env=ambiente, timeout=LIMITE_SEGUNDOS, check=False
    )
    duracao = time.monotonic() - inicio
    if resultado.returncode != 0:
        falhar(f'{" ".join(argumentos)} saiu com código {resultado.returncode}')
    return duracao


def mtimes(pasta: Path) -> dict[str, int]:
    return {str(p.relative_to(pasta)): p.stat().st_mtime_ns for p in sorted(pasta.rglob('*')) if p.is_file()}


def falhar(mensagem: str) -> None:
    sys.stderr.write(f'smoke: FALHOU: {mensagem}\n')
    sys.exit(1)


def main(comando: list[str]) -> None:
    base = Path(tempfile.mkdtemp())
    raiz = base / 'meus concursos ação'
    try:
        montar_projeto(raiz)

        rodar(comando, raiz, '--dry-run', '--yes')
        if (raiz / 'analises').exists() or (raiz / '.concurso').exists():
            falhar('--dry-run num projeto novo gravou arquivos')

        duracao = rodar(comando, raiz, '--yes', '--no-open', '--candidate', CANDIDATO)
        indice = raiz / 'analises' / CANDIDATO / 'index.html'
        if not indice.exists():
            falhar(f'{indice} não foi gerado')
        sys.stdout.write(f'smoke: onboarding e análise em {duracao:.1f}s\n')

        antes = mtimes(raiz / 'analises')
        rodar(comando, raiz, '--yes', '--no-open')
        rodar(comando, raiz, '--dry-run', '--yes')
        rodar(comando, raiz, '--dry-run', '--yes')
        mudados = sorted(k for k, v in mtimes(raiz / 'analises').items() if antes.get(k) != v)
        if mudados:
            falhar(f'reexecução alterou {", ".join(mudados)}')
        sys.stdout.write('smoke: ok\n')
    finally:
        shutil.rmtree(base, ignore_errors=True)


def congelado(executavel: str) -> None:
    if Path(executavel).exists():
        executavel = str(Path(executavel).resolve())
    base = Path(tempfile.mkdtemp())
    raiz = base / 'pré-checagem'
    raiz.mkdir()
    try:
        rodar([executavel], raiz, '--smoke')
        rodar([executavel], raiz, 'doctor')
    finally:
        shutil.rmtree(base, ignore_errors=True)
    main([executavel])


if __name__ == '__main__':
    argumentos = sys.argv[1:]
    if argumentos[:1] == ['congelado'] and len(argumentos) == 2:
        congelado(argumentos[1])
    else:
        main(argumentos or ['concurso-analise'])
