"""Regenera `src/concursos/dados/municipios_ibge.json` (`{uf: [nomes]}`) a partir da lista oficial do IBGE.

Rodado à mão antes de uma release, nunca pelo app: a lista é de domínio público e entra no pacote.
Uso: uv run python scripts/atualizar_municipios.py
"""

import gzip
import json
import sys
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

URL = 'https://servicodados.ibge.gov.br/api/v1/localidades/municipios'
DESTINO = Path(__file__).resolve().parent.parent / 'src' / 'concursos' / 'dados' / 'municipios_ibge.json'
TOTAL_MINIMO = 5500


def _uf(municipio: dict) -> str:
    microrregiao = municipio.get('microrregiao') or {}
    if microrregiao:
        return microrregiao['mesorregiao']['UF']['sigla']
    return municipio['regiao-imediata']['regiao-intermediaria']['UF']['sigla']


def _ordem(nome: str) -> tuple[str, str]:
    sem_acento = ''.join(c for c in unicodedata.normalize('NFKD', nome) if not unicodedata.combining(c))
    return sem_acento.casefold(), nome


def main() -> int:
    with urllib.request.urlopen(URL, timeout=60) as resposta:  # noqa: S310
        corpo = resposta.read()
    if corpo[:2] == b'\x1f\x8b':
        corpo = gzip.decompress(corpo)
    municipios = json.loads(corpo)
    if len(municipios) < TOTAL_MINIMO:
        print(f'resposta com só {len(municipios)} municípios; nada gravado', file=sys.stderr)  # noqa: T201
        return 1
    por_uf: dict[str, list[str]] = defaultdict(list)
    for municipio in municipios:
        por_uf[_uf(municipio)].append(municipio['nome'])
    dados = {uf: sorted(nomes, key=_ordem) for uf, nomes in sorted(por_uf.items())}
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, indent=0) + '\n', encoding='utf-8')
    print(f'{sum(map(len, dados.values()))} municípios em {len(dados)} UFs gravados em {DESTINO}')  # noqa: T201
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
