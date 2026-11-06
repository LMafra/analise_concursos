"""Gera e assina o manifesto de atualização da release (`atualizacao.json` e `atualizacao.json.sig`).

Roda no job `publicar` do release.yml, só com as dependências do uv.lock e sem instalar o projeto:

    uv sync --frozen --no-dev --no-install-project
    uv run --no-sync python scripts/assinar_manifesto.py assinar 0.6.0 dist

A chave privada (PEM, Ed25519) vem da variável `CHAVE_ATUALIZACAO`, o secret do environment `release`.

    ... assinar_manifesto.py gerar-chave <destino.pem>   # chave nova; imprime a pública para CHAVES_PUBLICAS
    ... assinar_manifesto.py conferir dist                # confere com as chaves do pacote
"""

import argparse
import base64
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from concursos import atualizador  # noqa: E402

VARIAVEL_CHAVE = 'CHAVE_ATUALIZACAO'


def ler_chave_privada(texto: str) -> Ed25519PrivateKey:
    chave = serialization.load_pem_private_key(texto.encode(), password=None)
    if not isinstance(chave, Ed25519PrivateKey):
        raise SystemExit(f'{VARIAVEL_CHAVE} não é uma chave Ed25519')
    return chave


def publica_em_base64(chave: Ed25519PrivateKey) -> str:
    bruta = chave.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(bruta).decode()


def assinar(versao: str, pasta: Path, texto_chave: str, hoje: str) -> tuple[Path, Path]:
    chave = ler_chave_privada(texto_chave)
    if publica_em_base64(chave) not in atualizador.CHAVES_PUBLICAS:
        raise SystemExit('a chave privada não corresponde a nenhuma de atualizador.CHAVES_PUBLICAS')
    conteudo = atualizador.montar_manifesto(versao, hoje, sorted(pasta.iterdir()))
    manifesto = atualizador.ler_manifesto(conteudo)
    faltam = set(atualizador.SUFIXOS) - set(manifesto.artefatos)
    if faltam:
        raise SystemExit(f'faltam os artefatos de {", ".join(sorted(faltam))} em {pasta}')
    destino = pasta / atualizador.ARQUIVO_MANIFESTO
    assinatura = pasta / atualizador.ARQUIVO_ASSINATURA
    destino.write_bytes(conteudo)
    assinatura.write_bytes(atualizador.assinar(conteudo, chave) + b'\n')
    atualizador.conferir_assinatura(destino.read_bytes(), assinatura.read_bytes())
    return destino, assinatura


def conferir(pasta: Path) -> str:
    conteudo = (pasta / atualizador.ARQUIVO_MANIFESTO).read_bytes()
    atualizador.conferir_assinatura(conteudo, (pasta / atualizador.ARQUIVO_ASSINATURA).read_bytes())
    manifesto = atualizador.ler_manifesto(conteudo)
    for artefato in manifesto.artefatos.values():
        atualizador.conferir_sha256(pasta / artefato.arquivo, artefato.sha256)
    return f'{manifesto.versao} ({manifesto.canal.value}): assinatura e SHA-256 conferem'


def gerar_chave(destino: Path) -> str:
    if destino.exists():
        raise SystemExit(f'{destino} já existe; não sobrescrevo uma chave')
    chave = Ed25519PrivateKey.generate()
    pem = chave.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    descritor = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descritor, 'wb') as arquivo:
        arquivo.write(pem)
    return publica_em_base64(chave)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    comandos = parser.add_subparsers(dest='comando', required=True)
    p_assinar = comandos.add_parser('assinar')
    p_assinar.add_argument('versao')
    p_assinar.add_argument('pasta', type=Path)
    comandos.add_parser('conferir').add_argument('pasta', type=Path)
    comandos.add_parser('gerar-chave').add_argument('destino', type=Path)
    args = parser.parse_args(argv)
    if args.comando == 'assinar':
        texto = os.environ.get(VARIAVEL_CHAVE)
        if not texto:
            raise SystemExit(f'defina {VARIAVEL_CHAVE} com a chave privada (PEM)')
        for caminho in assinar(args.versao, args.pasta, texto, datetime.now(UTC).date().isoformat()):
            print(f'gravado: {caminho}')  # noqa: T201
    elif args.comando == 'conferir':
        print(conferir(args.pasta))  # noqa: T201
    else:
        print(f'chave pública (para atualizador.CHAVES_PUBLICAS): {gerar_chave(args.destino)}')  # noqa: T201
    return 0


if __name__ == '__main__':
    sys.exit(main())
