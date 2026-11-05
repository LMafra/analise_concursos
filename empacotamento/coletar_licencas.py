"""Copia os arquivos de licença de cada distribuição instalada no ambiente de build para
`empacotamento/construcao/LICENSES/<distribuição>/`, que o spec põe no executável."""

import re
import shutil
import sys
from importlib.metadata import distributions
from pathlib import Path

DESTINO = Path(__file__).parent / 'construcao' / 'LICENSES'
LICENCA = re.compile(r'(^|/)(LICEN[CS]E|COPYING|NOTICE|AUTHORS)[^/]*$', re.IGNORECASE)


def coletar(destino: Path = DESTINO) -> list[str]:
    shutil.rmtree(destino, ignore_errors=True)
    nomes = []
    for distribuicao in distributions():
        nome = distribuicao.metadata['Name']
        arquivos = [f for f in distribuicao.files or [] if LICENCA.search(str(f))]
        if not arquivos:
            continue
        pasta = destino / f'{nome}-{distribuicao.version}'
        pasta.mkdir(parents=True, exist_ok=True)
        for arquivo in arquivos:
            origem = Path(distribuicao.locate_file(arquivo))
            if origem.is_file():
                shutil.copy2(origem, pasta / origem.name)
        nomes.append(nome)
    if licenca_python := licenca_do_python():
        (destino / 'python').mkdir(parents=True, exist_ok=True)
        shutil.copy2(licenca_python, destino / 'python' / 'LICENSE.txt')
        nomes.append('python')
    return sorted(nomes, key=str.lower)


def licenca_do_python() -> Path | None:
    base = Path(sys.base_prefix)
    versao = f'python{sys.version_info.major}.{sys.version_info.minor}'
    for candidato in (base / 'LICENSE.txt', base / 'lib' / versao / 'LICENSE.txt'):
        if candidato.is_file():
            return candidato
    return None


if __name__ == '__main__':
    coletadas = coletar()
    sys.stdout.write(f'licenças de {len(coletadas)} distribuições em {DESTINO}\n')
