"""Retrato de paridade das saídas da análise: o hash de cada arquivo, para provar que um refactor não mudou nada.

Uso (rode a análise com --forcar antes de cada retrato):
    python scripts/paridade.py retrato analises .paridade/retrato.json
    python scripts/paridade.py comparar analises .paridade/retrato.json
    python scripts/paridade.py comparar analises .paridade/retrato.json --esperadas scripts/paridade_esperadas.toml

A chave é o caminho relativo à pasta de análises. Depois da migração para o layout multi-candidato, compare
contra a pasta do candidato (analises/<slug>). O manifesto fica de fora: ele guarda os hashes de entrada e a
versão da análise, que mudam legitimamente. O index.html também, porque traz a data da geração.

Sem `--esperadas`, toda diferença reprova. Com ela, uma diferença cujo caminho casa com um padrão do arquivo
aparece com o motivo e não reprova; as outras continuam reprovando.
"""

import fnmatch
import hashlib
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

IGNORADOS = {'.manifesto.json', 'index.html'}


@dataclass(frozen=True)
class Esperada:
    padrao: str
    motivo: str
    versao: str


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


def ler_esperadas(arquivo: Path) -> list[Esperada]:
    dados = tomllib.loads(arquivo.read_text(encoding='utf-8'))
    return [Esperada(item['padrao'], item['motivo'], item['versao']) for item in dados.get('esperada', [])]


def motivo_esperado(chave: str, esperadas: list[Esperada]) -> str | None:
    return next((e.motivo for e in esperadas if fnmatch.fnmatchcase(chave, e.padrao)), None)


def main(argv: list[str]) -> int:
    esperadas: list[Esperada] | None = None
    if len(argv) == 5 and argv[0] == 'comparar' and argv[3] == '--esperadas':
        esperadas, argv = ler_esperadas(Path(argv[4])), argv[:3]
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
    if not diferencas:
        sys.stdout.write(f'paridade: {len(atual)} arquivos iguais\n')
        return 0
    linhas, inesperadas = [], 0
    for diferenca in diferencas:
        motivo = motivo_esperado(diferenca.split(': ', 1)[1], esperadas or [])
        linhas.append(f'{diferenca} (esperado: {motivo})' if motivo else diferenca)
        inesperadas += motivo is None
    sys.stdout.write('\n'.join(linhas) + '\n')
    return 1 if inesperadas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
