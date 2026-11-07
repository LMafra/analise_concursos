"""Manifesto do pacote de estudo (`estudo.json`), assinado com a mesma chave Ed25519 do atualizador.

O contrato está em `docs/modelo.md`. A release do pacote tem a tag `estudo-v<versao>`, com
`<versao> = <open-notebook>-<revisao>`.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from packaging.version import InvalidVersion, Version

from concursos import atualizador
from concursos.erros import ErroDoAmbiente
from concursos.modelo import CanalAtualizacao

FORMATO = 1
ARQUIVO_MANIFESTO = 'estudo.json'
ARQUIVO_ASSINATURA = 'estudo.json.sig'
PREFIXO_TAG = 'estudo-v'
SUFIXOS = {'windows-x64': 'windows-x64.zip', 'linux-x86_64': 'linux-x86_64.tar.xz'}
PADRAO_VERSAO = re.compile(r'^\d+\.\d+\.\d+-\d+$')
PADRAO_ARQUIVO = re.compile(r'^estudo-\d+\.\d+\.\d+-\d+-(windows-x64\.zip|linux-x86_64\.tar\.xz)$')
DICA = 'tente de novo mais tarde em Estudar; se continuar, veja a página de releases do app'


@dataclass(frozen=True)
class ArtefatoEstudo:
    arquivo: str
    sha256: str
    tamanho: int
    tamanho_extraido: int


@dataclass(frozen=True)
class ManifestoEstudo:
    versao: str
    open_notebook: str
    app_minimo: str
    canal: CanalAtualizacao
    publicado_em: str
    modelo: dict
    artefatos: dict[str, ArtefatoEstudo]


def tag(versao: str) -> str:
    return f'{PREFIXO_TAG}{versao}'


def url_do_artefato(versao: str, artefato: ArtefatoEstudo) -> str:
    return f'{atualizador.URL_DOWNLOAD}/{tag(versao)}/{artefato.arquivo}'


def url_do_manifesto(versao: str, assinatura: bool = False) -> str:
    nome = ARQUIVO_ASSINATURA if assinatura else ARQUIVO_MANIFESTO
    return f'{atualizador.URL_DOWNLOAD}/{tag(versao)}/{nome}'


def conferir_assinatura(conteudo: bytes, assinatura: bytes) -> None:
    try:
        atualizador.conferir_assinatura(conteudo, assinatura)
    except ErroDoAmbiente as erro:
        raise ErroDoAmbiente(
            'o pacote da biblioteca não tem assinatura válida; nada foi instalado', DICA
        ) from erro


def _invalido(motivo: str) -> ErroDoAmbiente:
    return ErroDoAmbiente(f'pacote da biblioteca inválido: {motivo}', DICA)


def _inteiro_positivo(valor: object) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


def _artefato(plataforma: str, bruto: object) -> ArtefatoEstudo:
    if not isinstance(bruto, dict):
        raise _invalido(f'artefato {plataforma}')
    arquivo = bruto.get('arquivo')
    sufixo = SUFIXOS.get(plataforma)
    if sufixo is None or not isinstance(arquivo, str) or not PADRAO_ARQUIVO.match(arquivo):
        raise _invalido(f'arquivo {arquivo!r} de {plataforma}')
    if not arquivo.endswith(sufixo):
        raise _invalido(f'{arquivo} não é de {plataforma}')
    sha256 = bruto.get('sha256')
    if not isinstance(sha256, str) or not atualizador.PADRAO_SHA256.match(sha256):
        raise _invalido(f'SHA-256 de {arquivo}')
    tamanho, extraido = bruto.get('tamanho'), bruto.get('tamanho_extraido')
    if not _inteiro_positivo(tamanho) or not _inteiro_positivo(extraido):
        raise _invalido(f'tamanho de {arquivo}')
    return ArtefatoEstudo(arquivo, sha256, tamanho, extraido)


def ler_manifesto(conteudo: bytes) -> ManifestoEstudo:
    """Chame só depois de `conferir_assinatura`."""
    try:
        dados = json.loads(conteudo)
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        raise _invalido('não é JSON') from erro
    if not isinstance(dados, dict):
        raise _invalido('não é um objeto')
    try:
        formato, versao, brutos = dados['formato'], dados['versao'], dados['artefatos']
        open_notebook, app_minimo = dados['open_notebook'], dados['app_minimo']
        canal, publicado_em, modelo = dados['canal'], dados['publicado_em'], dados['modelo']
    except KeyError as erro:
        raise _invalido(f'falta o campo {erro.args[0]}') from erro
    if formato != FORMATO:
        raise _invalido(f'formato {formato}, este app lê o {FORMATO}')
    if not isinstance(versao, str) or not PADRAO_VERSAO.match(versao):
        raise _invalido(f'versão {versao!r}')
    try:
        Version(app_minimo)
        Version(open_notebook)
        canal = CanalAtualizacao(canal)
    except (InvalidVersion, TypeError, ValueError) as erro:
        raise _invalido(f'app_minimo {app_minimo!r} ou canal {canal!r}') from erro
    if not isinstance(brutos, dict) or not brutos or not isinstance(modelo, dict):
        raise _invalido('sem artefatos ou sem modelo')
    return ManifestoEstudo(
        versao=versao,
        open_notebook=str(open_notebook),
        app_minimo=app_minimo,
        canal=canal,
        publicado_em=str(publicado_em),
        modelo=modelo,
        artefatos={plataforma: _artefato(plataforma, bruto) for plataforma, bruto in brutos.items()},
    )


def compativel(manifesto: ManifestoEstudo, versao_do_app: str) -> bool:
    try:
        return Version(versao_do_app) >= Version(manifesto.app_minimo)
    except InvalidVersion:
        return False


def chave_de_ordem(versao: str) -> tuple[Version, int]:
    base, revisao = versao.rsplit('-', 1)
    return Version(base), int(revisao)


def sha256_do_arquivo(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open('rb') as arquivo:
        while bloco := arquivo.read(1024 * 1024):
            resumo.update(bloco)
    return resumo.hexdigest()


def montar_manifesto(
    *,
    open_notebook: str,
    revisao: int,
    app_minimo: str,
    publicado_em: str,
    modelo: dict,
    arquivos: list[Path],
    extraidos: dict[str, int],
) -> bytes:
    """O `estudo.json` da release, com os pacotes de Windows e Linux entre `arquivos`."""
    versao = f'{open_notebook}-{revisao}'
    artefatos = {}
    for caminho in arquivos:
        for plataforma, sufixo in SUFIXOS.items():
            if caminho.name == f'estudo-{versao}-{sufixo}':
                artefatos[plataforma] = {
                    'arquivo': caminho.name,
                    'sha256': sha256_do_arquivo(caminho),
                    'tamanho': caminho.stat().st_size,
                    'tamanho_extraido': extraidos[plataforma],
                }
    canal = CanalAtualizacao.BETA if Version(app_minimo).is_prerelease else CanalAtualizacao.STABLE
    dados = {
        'formato': FORMATO,
        'versao': versao,
        'open_notebook': open_notebook,
        'app_minimo': app_minimo,
        'canal': canal.value,
        'publicado_em': publicado_em,
        'modelo': modelo,
        'artefatos': artefatos,
    }
    conteudo = json.dumps(dados, ensure_ascii=False, indent=2).encode('utf-8') + b'\n'
    ler_manifesto(conteudo)
    return conteudo
