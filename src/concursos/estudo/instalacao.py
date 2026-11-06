"""Instala e atualiza o pacote de estudo em `~/.concurso/open-notebook/`.

Só o transporte (o mesmo do atualizador) fala com a rede, e só depois do consentimento. A pasta do
banco ganha um backup verificado antes da primeira partida de cada versão nova; se essa partida falha,
`voltar_ao_anterior` restaura o pacote e o banco de antes.
"""

import json
import logging
import shutil
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from concursos import atualizador
from concursos.aplicacao.atualizador import Progresso, Transporte
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.estudo import manifesto
from concursos.estudo.manifesto import ArtefatoEstudo, ManifestoEstudo
from concursos.modelo import CanalAtualizacao

logger = logging.getLogger(__name__)

PASTA = 'open-notebook'
ARQUIVO_ESTADO = 'instalado.json'
BACKUPS_MANTIDOS = 2
URL_RELEASES = f'https://api.github.com/repos/{atualizador.REPOSITORIO}/releases?per_page=50'
MARGEM_DISCO = 200 * 1024 * 1024
DICA_DISCO = 'libere espaço no disco (apague arquivos grandes ou esvazie a lixeira) e tente de novo'

EspacoLivre = Callable[[Path], int]


@dataclass(frozen=True)
class Pastas:
    base: Path

    @classmethod
    def do_home(cls, home: Path) -> 'Pastas':
        return cls(home / PASTA)

    @property
    def pacotes(self) -> Path:
        return self.base / 'pacote'

    @property
    def dados(self) -> Path:
        return self.base / 'dados'

    @property
    def banco(self) -> Path:
        return self.dados / 'banco'

    @property
    def backups(self) -> Path:
        return self.base / 'backups'

    @property
    def estado(self) -> Path:
        return self.base / ARQUIVO_ESTADO

    @property
    def trava(self) -> Path:
        return self.base / '.trava'


@dataclass(frozen=True)
class Estado:
    atual: str | None = None
    anterior: str | None = None
    ultima_partida: str | None = None


@dataclass(frozen=True)
class PacoteDisponivel:
    manifesto: ManifestoEstudo
    plataforma: str
    artefato: ArtefatoEstudo
    url: str


def plataforma(sistema: str = sys.platform) -> str:
    try:
        return atualizador.plataforma(sistema)
    except ErroDoUsuario as erro:
        raise ErroDoUsuario(
            'estudar com seus livros ainda não está disponível neste sistema',
            'por enquanto, a biblioteca funciona no Windows e no Linux',
        ) from erro


def ler_estado(pastas: Pastas) -> Estado:
    try:
        dados = json.loads(pastas.estado.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return Estado()
    if not isinstance(dados, dict):
        return Estado()
    return Estado(dados.get('atual'), dados.get('anterior'), dados.get('ultima_partida'))


def gravar_estado(pastas: Pastas, estado: Estado) -> None:
    pastas.base.mkdir(parents=True, exist_ok=True)
    dados = {'atual': estado.atual, 'anterior': estado.anterior, 'ultima_partida': estado.ultima_partida}
    pastas.estado.write_text(json.dumps(dados, indent=2) + '\n', encoding='utf-8')


def raiz_do_pacote(pastas: Pastas, versao: str) -> Path:
    return pastas.pacotes / versao / f'estudo-{versao}'


def instalado(pastas: Pastas) -> Path | None:
    """A raiz do pacote em uso, ou None se não há pacote válido."""
    atual = ler_estado(pastas).atual
    if not atual:
        return None
    raiz = raiz_do_pacote(pastas, atual)
    return raiz if (raiz / 'estudo.toml').is_file() else None


def _releases_de_estudo(transporte: Transporte, canal: CanalAtualizacao) -> list[str]:
    try:
        releases = json.loads(transporte.baixar(URL_RELEASES, atualizador.LIMITE_LISTA_RELEASES))
    except json.JSONDecodeError as erro:
        raise ErroDoAmbiente(
            'o GitHub respondeu algo que não é a lista de versões', 'tente mais tarde'
        ) from erro
    versoes = []
    for release in releases if isinstance(releases, list) else []:
        if not isinstance(release, dict) or release.get('draft'):
            continue
        if canal is CanalAtualizacao.STABLE and release.get('prerelease'):
            continue
        tag = str(release.get('tag_name', ''))
        versao = tag.removeprefix(manifesto.PREFIXO_TAG)
        if tag.startswith(manifesto.PREFIXO_TAG) and manifesto.PADRAO_VERSAO.match(versao):
            versoes.append(versao)
    return sorted(versoes, key=manifesto.chave_de_ordem, reverse=True)


def procurar(
    canal: CanalAtualizacao, transporte: Transporte, versao_do_app: str, sistema: str = sys.platform
) -> PacoteDisponivel | None:
    """O pacote mais novo do canal que este app aceita (`app_minimo`), já com a assinatura conferida."""
    alvo = plataforma(sistema)
    for versao in _releases_de_estudo(transporte, canal):
        conteudo = transporte.baixar(manifesto.url_do_manifesto(versao), atualizador.LIMITE_MANIFESTO)
        assinatura = transporte.baixar(
            manifesto.url_do_manifesto(versao, True), atualizador.LIMITE_ASSINATURA
        )
        manifesto.conferir_assinatura(conteudo, assinatura)
        lido = manifesto.ler_manifesto(conteudo)
        if lido.versao != versao or alvo not in lido.artefatos:
            continue
        if canal is CanalAtualizacao.STABLE and lido.canal is not CanalAtualizacao.STABLE:
            continue
        if not manifesto.compativel(lido, versao_do_app):
            continue
        artefato = lido.artefatos[alvo]
        return PacoteDisponivel(lido, alvo, artefato, manifesto.url_do_artefato(versao, artefato))
    return None


def tem_atualizacao(pastas: Pastas, disponivel: PacoteDisponivel | None) -> bool:
    atual = ler_estado(pastas).atual
    if disponivel is None:
        return False
    if atual is None:
        return True
    return manifesto.chave_de_ordem(disponivel.manifesto.versao) > manifesto.chave_de_ordem(atual)


def _tamanho(pasta: Path) -> int:
    if not pasta.exists():
        return 0
    return sum(p.stat().st_size for p in pasta.rglob('*') if p.is_file())


def espaco_necessario(pastas: Pastas, artefato: ArtefatoEstudo) -> int:
    """O download, a extração e um backup do banco, com uma margem."""
    return artefato.tamanho + artefato.tamanho_extraido + _tamanho(pastas.banco) + MARGEM_DISCO


def _livre(pasta: Path) -> int:
    while not pasta.exists():
        pasta = pasta.parent
    return shutil.disk_usage(pasta).free


def conferir_espaco(pastas: Pastas, artefato: ArtefatoEstudo, livre: EspacoLivre = _livre) -> None:
    precisa = espaco_necessario(pastas, artefato)
    if livre(pastas.base) < precisa:
        raise ErroDoUsuario(
            f'falta espaço no disco para preparar a biblioteca: são necessários {precisa / 1e9:.1f} GB livres',
            DICA_DISCO,
        )


def _dentro(destino: Path, nome: str) -> Path:
    relativo = PurePosixPath(nome.replace('\\', '/'))
    if relativo.is_absolute() or '..' in relativo.parts:
        raise ErroDoAmbiente(f'o pacote da biblioteca tem um caminho inválido ({nome}); nada foi instalado')
    return destino / Path(*relativo.parts)


def extrair(arquivo: Path, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    if arquivo.name.endswith('.zip'):
        with zipfile.ZipFile(arquivo) as pacote:
            for nome in pacote.namelist():
                _dentro(destino, nome)
            pacote.extractall(destino)
    else:
        with tarfile.open(arquivo) as tar:
            tar.extractall(destino, filter='data')


def _manter_dois_pacotes(pastas: Pastas, estado: Estado) -> None:
    manter = {estado.atual, estado.anterior}
    for pasta in pastas.pacotes.iterdir() if pastas.pacotes.exists() else []:
        if pasta.name not in manter:
            shutil.rmtree(pasta, ignore_errors=True)


def instalar_arquivo(pastas: Pastas, arquivo: Path, versao: str) -> Path:
    """Extrai um pacote já conferido e o torna o atual; o anterior fica para voltar."""
    destino = pastas.pacotes / versao
    pastas.pacotes.mkdir(parents=True, exist_ok=True)
    temporaria = Path(tempfile.mkdtemp(prefix='extraindo-', dir=pastas.base))
    try:
        extrair(arquivo, temporaria)
        if not (temporaria / f'estudo-{versao}' / 'estudo.toml').is_file():
            raise ErroDoAmbiente('o pacote da biblioteca está incompleto; nada foi instalado', manifesto.DICA)
        shutil.rmtree(destino, ignore_errors=True)
        temporaria.rename(destino)
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)
    estado = ler_estado(pastas)
    anterior = estado.atual if estado.atual != versao else estado.anterior
    novo = Estado(atual=versao, anterior=anterior, ultima_partida=estado.ultima_partida)
    gravar_estado(pastas, novo)
    _manter_dois_pacotes(pastas, novo)
    return raiz_do_pacote(pastas, versao)


def instalar(
    pastas: Pastas,
    disponivel: PacoteDisponivel,
    transporte: Transporte,
    *,
    consentiu: bool,
    offline: bool = False,
    progresso: Progresso | None = None,
    livre: EspacoLivre = _livre,
) -> Path:
    if offline:
        raise ErroDoUsuario(
            'sem internet não dá para preparar a biblioteca', 'tente de novo com a internet ligada'
        )
    if not consentiu:
        raise ErroDoUsuario(
            'a biblioteca só é preparada depois que você concordar', 'clique em "Preparar agora"'
        )
    pastas.base.mkdir(parents=True, exist_ok=True)
    conferir_espaco(pastas, disponivel.artefato, livre)
    atualizador.conferir_url(disponivel.url)
    baixado = pastas.base / f'.baixando-{disponivel.artefato.arquivo}'
    try:
        transporte.baixar_para(disponivel.url, baixado, disponivel.artefato.tamanho, progresso)
        try:
            atualizador.conferir_sha256(baixado, disponivel.artefato.sha256)
        except ErroDoAmbiente as erro:
            raise ErroDoAmbiente(
                'o pacote da biblioteca chegou diferente do publicado e foi descartado', manifesto.DICA
            ) from erro
        return instalar_arquivo(pastas, baixado, disponivel.manifesto.versao)
    finally:
        baixado.unlink(missing_ok=True)


def precisa_de_backup(pastas: Pastas) -> bool:
    estado = ler_estado(pastas)
    return pastas.banco.exists() and estado.atual is not None and estado.ultima_partida != estado.atual


def _arquivos(pasta: Path) -> dict[str, tuple[int, str]]:
    return {
        p.relative_to(pasta).as_posix(): (p.stat().st_size, manifesto.sha256_do_arquivo(p))
        for p in sorted(pasta.rglob('*'))
        if p.is_file()
    }


def fazer_backup(pastas: Pastas, versao: str, agora: datetime | None = None) -> Path:
    """Cópia da pasta do banco (com os processos parados), conferida arquivo a arquivo."""
    momento = (agora or datetime.now()).strftime('%Y%m%d-%H%M%S')
    destino = pastas.backups / f'{momento}-{versao}'
    shutil.copytree(pastas.banco, destino / 'banco')
    if _arquivos(pastas.banco) != _arquivos(destino / 'banco'):
        shutil.rmtree(destino, ignore_errors=True)
        raise ErroDoAmbiente(
            'a cópia de segurança da biblioteca não conferiu; a versão nova não foi aberta', DICA_DISCO
        )
    copias = sorted(p for p in pastas.backups.iterdir() if p.is_dir())
    for antiga in copias[:-BACKUPS_MANTIDOS]:
        shutil.rmtree(antiga, ignore_errors=True)
    return destino


def registrar_partida(pastas: Pastas) -> None:
    estado = ler_estado(pastas)
    gravar_estado(pastas, Estado(estado.atual, estado.anterior, estado.atual))


def voltar_ao_anterior(pastas: Pastas) -> str | None:
    """Volta ao pacote anterior e ao último backup do banco; devolve a versão restaurada."""
    estado = ler_estado(pastas)
    if not estado.anterior or not raiz_do_pacote(pastas, estado.anterior).exists():
        return None
    copias = sorted(p for p in pastas.backups.iterdir() if p.is_dir()) if pastas.backups.exists() else []
    if copias:
        shutil.rmtree(pastas.banco, ignore_errors=True)
        shutil.copytree(copias[-1] / 'banco', pastas.banco)
    gravar_estado(
        pastas, Estado(atual=estado.anterior, anterior=estado.atual, ultima_partida=estado.anterior)
    )
    logger.warning('open-notebook: a versão %s não abriu; voltei para a %s', estado.atual, estado.anterior)
    return estado.anterior
