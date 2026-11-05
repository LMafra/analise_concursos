"""Atualização do executável por manifesto assinado (Ed25519), sem rede: o transporte vem de quem chama.

O contrato do `atualizacao.json` está em `docs/modelo.md`.
"""

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from packaging.version import InvalidVersion, Version

from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.modelo import CanalAtualizacao

FORMATO = 1
REPOSITORIO = 'LMafra/analise_concursos'
URL_STABLE = f'https://github.com/{REPOSITORIO}/releases/latest/download/atualizacao.json'
URL_RELEASES = f'https://api.github.com/repos/{REPOSITORIO}/releases?per_page=10'
URL_DOWNLOAD = f'https://github.com/{REPOSITORIO}/releases/download'
URL_RELEASES_PAGINA = f'https://github.com/{REPOSITORIO}/releases'
ARQUIVO_MANIFESTO = 'atualizacao.json'
ARQUIVO_ASSINATURA = 'atualizacao.json.sig'
HOSTS_PERMITIDOS = frozenset(
    {'github.com', 'api.github.com', 'objects.githubusercontent.com', 'release-assets.githubusercontent.com'}
)
LIMITE_MANIFESTO = 64 * 1024
LIMITE_ASSINATURA = 1024
LIMITE_LISTA_RELEASES = 2 * 1024 * 1024
INTERVALO_CONSULTA = timedelta(hours=24)

# Qualquer uma vale, para rotacionar: a nova entra numa versão antes de a antiga sair do CI.
CHAVES_PUBLICAS: tuple[str, ...] = ('aHV1PoJmOdb1vVzPuVzT5Ue8LXw7p3FCWH6z4JB9z0M=',)

PLATAFORMAS = {'win32': 'windows-x64', 'linux': 'linux-x86_64'}
SUFIXOS = {'windows-x64': 'windows-x64-setup.exe', 'linux-x86_64': 'linux-x86_64.AppImage'}
PADRAO_ARQUIVO = re.compile(
    r'^concurso-analise-[0-9A-Za-z.+-]+-(windows-x64-setup\.exe|linux-x86_64\.AppImage)$'
)
PADRAO_SHA256 = re.compile(r'^[0-9a-f]{64}$')
DICA_MANUAL = f'baixe a versão nova à mão em {URL_RELEASES_PAGINA}'


@dataclass(frozen=True)
class Artefato:
    arquivo: str
    sha256: str
    tamanho: int


@dataclass(frozen=True)
class Manifesto:
    versao: str
    canal: CanalAtualizacao
    publicado_em: str
    notas: str
    artefatos: dict[str, Artefato]


def assinar(conteudo: bytes, chave: Ed25519PrivateKey) -> bytes:
    return base64.b64encode(chave.sign(conteudo))


def conferir_assinatura(conteudo: bytes, assinatura: bytes, chaves: tuple[str, ...] | None = None) -> None:
    try:
        bruta = base64.b64decode(assinatura.strip(), validate=True)
    except (binascii.Error, ValueError):
        bruta = b''
    for chave in CHAVES_PUBLICAS if chaves is None else chaves:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(chave)).verify(bruta, conteudo)
        except (InvalidSignature, ValueError):
            continue
        return
    raise ErroDoAmbiente(
        'o manifesto de atualização não tem assinatura válida; nada foi baixado', DICA_MANUAL
    )


def _invalido(motivo: str) -> ErroDoAmbiente:
    return ErroDoAmbiente(f'manifesto de atualização inválido: {motivo}', DICA_MANUAL)


def ler_manifesto(conteudo: bytes) -> Manifesto:
    """Chame só depois de `conferir_assinatura`."""
    try:
        dados = json.loads(conteudo)
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        raise _invalido('não é JSON') from erro
    if not isinstance(dados, dict):
        raise _invalido('não é um objeto')
    try:
        formato, versao, canal = dados['formato'], dados['versao'], dados['canal']
        publicado_em, notas, brutos = dados['publicado_em'], dados['notas'], dados['artefatos']
    except KeyError as erro:
        raise _invalido(f'falta o campo {erro.args[0]}') from erro
    if formato != FORMATO:
        raise _invalido(f'formato {formato}, este app lê o {FORMATO}')
    try:
        Version(versao)
        canal = CanalAtualizacao(canal)
    except (InvalidVersion, TypeError, ValueError) as erro:
        raise _invalido(f'versão {versao!r} ou canal {canal!r}') from erro
    if not isinstance(brutos, dict) or not brutos:
        raise _invalido('sem artefatos')
    return Manifesto(
        versao=versao,
        canal=canal,
        publicado_em=str(publicado_em),
        notas=str(notas),
        artefatos={plataforma: _artefato(plataforma, bruto) for plataforma, bruto in brutos.items()},
    )


def _artefato(plataforma: str, bruto: object) -> Artefato:
    if not isinstance(bruto, dict):
        raise _invalido(f'artefato {plataforma}')
    arquivo, sha256, tamanho = bruto.get('arquivo'), bruto.get('sha256'), bruto.get('tamanho')
    sufixo = SUFIXOS.get(plataforma)
    if sufixo is None or not isinstance(arquivo, str) or not PADRAO_ARQUIVO.match(arquivo):
        raise _invalido(f'arquivo {arquivo!r} de {plataforma}')
    if not arquivo.endswith(sufixo):
        raise _invalido(f'{arquivo} não é de {plataforma}')
    if not isinstance(sha256, str) or not PADRAO_SHA256.match(sha256):
        raise _invalido(f'SHA-256 de {arquivo}')
    if not isinstance(tamanho, int) or isinstance(tamanho, bool) or tamanho <= 0:
        raise _invalido(f'tamanho de {arquivo}')
    return Artefato(arquivo, sha256, tamanho)


def escolher(
    manifesto: Manifesto, instalada: str, canal: CanalAtualizacao, plataforma: str
) -> Artefato | None:
    """O artefato a instalar, ou None se não há versão maior para este sistema."""
    if canal is CanalAtualizacao.STABLE and manifesto.canal is not CanalAtualizacao.STABLE:
        raise ErroDoAmbiente(
            f'o manifesto do canal stable aponta uma versão beta ({manifesto.versao}); nada foi baixado',
            DICA_MANUAL,
        )
    if Version(manifesto.versao) <= Version(instalada):
        return None
    return manifesto.artefatos.get(plataforma)


def url_do_artefato(manifesto: Manifesto, artefato: Artefato) -> str:
    return f'{URL_DOWNLOAD}/v{manifesto.versao}/{artefato.arquivo}'


def conferir_url(url: str) -> None:
    partes = urlsplit(url)
    if partes.scheme != 'https' or partes.username or partes.hostname not in HOSTS_PERMITIDOS:
        raise ErroDoAmbiente(
            f'endereço fora do GitHub na atualização ({partes.scheme}://{partes.hostname}); nada foi baixado',
            DICA_MANUAL,
        )


def conferir_sha256(caminho: Path, esperado: str) -> None:
    resumo = hashlib.sha256()
    with caminho.open('rb') as arquivo:
        while bloco := arquivo.read(1024 * 1024):
            resumo.update(bloco)
    if resumo.hexdigest() != esperado:
        raise ErroDoAmbiente(
            f'o SHA-256 de {caminho.name} não confere com o manifesto; o arquivo foi descartado', DICA_MANUAL
        )


def plataforma(sistema: str) -> str:
    chave = 'linux' if sistema.startswith('linux') else sistema
    if chave not in PLATAFORMAS:
        raise ErroDoUsuario(
            'a atualização pelo app existe só no Windows e no Linux', f'no macOS, {DICA_MANUAL}'
        )
    return PLATAFORMAS[chave]


def comando_do_setup(setup: Path) -> list[str]:
    """`/REABRIR=1` faz o setup abrir o app no fim; o `/SILENT` mostra só a barra de progresso."""
    return [str(setup), '/SILENT', '/SUPPRESSMSGBOXES', '/CLOSEAPPLICATIONS', '/REABRIR=1']


def consulta_vencida(estado: Path, agora: datetime) -> bool:
    try:
        ultima = datetime.fromisoformat(json.loads(estado.read_text(encoding='utf-8'))['ultima_consulta'])
    except (OSError, ValueError, KeyError, TypeError):
        return True
    return agora - ultima >= INTERVALO_CONSULTA


def registrar_consulta(estado: Path, agora: datetime) -> None:
    estado.parent.mkdir(parents=True, exist_ok=True)
    estado.write_text(json.dumps({'ultima_consulta': agora.isoformat()}), encoding='utf-8')


def montar_manifesto(versao: str, publicado_em: str, arquivos: list[Path]) -> bytes:
    """O `atualizacao.json` da release, com os artefatos de Windows e Linux entre `arquivos`."""
    artefatos = {}
    for caminho in arquivos:
        for chave, sufixo in SUFIXOS.items():
            if caminho.name == f'concurso-analise-{versao}-{sufixo}':
                resumo = hashlib.sha256(caminho.read_bytes()).hexdigest()
                artefatos[chave] = {
                    'arquivo': caminho.name,
                    'sha256': resumo,
                    'tamanho': caminho.stat().st_size,
                }
    canal = CanalAtualizacao.BETA if Version(versao).is_prerelease else CanalAtualizacao.STABLE
    dados = {
        'formato': FORMATO,
        'versao': versao,
        'canal': canal.value,
        'publicado_em': publicado_em,
        'notas': f'{URL_RELEASES_PAGINA}/tag/v{versao}',
        'artefatos': artefatos,
    }
    conteudo = json.dumps(dados, ensure_ascii=False, indent=2).encode('utf-8') + b'\n'
    ler_manifesto(conteudo)
    return conteudo
