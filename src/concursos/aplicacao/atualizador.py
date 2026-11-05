"""Verificar e instalar a versão nova do executável, para o Sobre da GUI e o `upgrade` da CLI.

Só o transporte (`TransporteHttps`) fala com a rede; os testes passam um transporte falso.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Protocol

from concursos import atualizador
from concursos.aplicacao.opcoes import Opcoes
from concursos.atualizador import Artefato
from concursos.config.contexto import gravar_secao, ler_toml
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.modelo import CanalAtualizacao

logger = logging.getLogger(__name__)

SECAO = 'atualizacao'
ARQUIVO_ESTADO = 'atualizacao.json'
BLOCO = 1024 * 1024
TIMEOUT = 30

Progresso = Callable[[int, int], None]
LerAssinatura = Callable[[Path], tuple[str, str | None]]
Abrir = Callable[[list[str]], object]


class Transporte(Protocol):
    def baixar(self, url: str, limite: int) -> bytes: ...

    def baixar_para(
        self, url: str, destino: Path, limite: int, progresso: Progresso | None = None
    ) -> None: ...


class _SoGithub(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        atualizador.conferir_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class TransporteHttps:
    def __init__(self, instalada: str, timeout: float = TIMEOUT) -> None:
        self._abridor = urllib.request.build_opener(_SoGithub())
        self._cabecalhos = {'User-Agent': f'concurso-analise/{instalada}', 'Accept': '*/*'}
        self._timeout = timeout

    def _abrir(self, url: str):  # noqa: ANN202
        atualizador.conferir_url(url)
        pedido = urllib.request.Request(url, headers=self._cabecalhos)
        try:
            return self._abridor.open(pedido, timeout=self._timeout)
        except urllib.error.HTTPError as erro:
            raise ErroDoAmbiente(
                f'o GitHub respondeu {erro.code} ao procurar a atualização', 'tente de novo mais tarde'
            ) from erro
        except (urllib.error.URLError, OSError) as erro:
            raise ErroDoAmbiente(
                'sem conexão com o GitHub para procurar a atualização', 'confira a internet e tente de novo'
            ) from erro

    def baixar(self, url: str, limite: int) -> bytes:
        with self._abrir(url) as resposta:
            dados = resposta.read(limite + 1)
        if len(dados) > limite:
            raise ErroDoAmbiente(f'resposta maior que {limite} bytes em {url}; nada foi usado')
        return dados

    def baixar_para(self, url: str, destino: Path, limite: int, progresso: Progresso | None = None) -> None:
        total = 0
        with self._abrir(url) as resposta, destino.open('wb') as arquivo:
            while bloco := resposta.read(BLOCO):
                total += len(bloco)
                if total > limite:
                    raise ErroDoAmbiente(f'o download passou de {limite} bytes; o arquivo foi descartado')
                arquivo.write(bloco)
                if progresso is not None:
                    progresso(total, limite)


@dataclass(frozen=True)
class Preferencias:
    canal: CanalAtualizacao = CanalAtualizacao.STABLE
    verificar_ao_abrir: bool = False


@dataclass(frozen=True)
class Novidade:
    versao: str
    canal: CanalAtualizacao
    notas: str
    plataforma: str
    artefato: Artefato
    url: str


@dataclass(frozen=True)
class Instalacao:
    """`caminho` é o AppImage substituído (Linux) ou o setup em execução (Windows)."""

    versao: str
    caminho: Path
    setup_em_andamento: bool


def no_executavel() -> bool:
    return bool(getattr(sys, 'frozen', False))


def versao_instalada() -> str:
    return version('concurso-analise')


def ler_preferencias(config_global: Path) -> Preferencias:
    dados = ler_toml(config_global).get(SECAO, {})
    try:
        canal = CanalAtualizacao(dados.get('canal', CanalAtualizacao.STABLE.value))
    except ValueError:
        canal = CanalAtualizacao.STABLE
    return Preferencias(canal=canal, verificar_ao_abrir=dados.get('verificar_ao_abrir') is True)


def gravar_preferencias(config_global: Path, preferencias: Preferencias) -> None:
    gravar_secao(
        config_global,
        SECAO,
        {'canal': preferencias.canal.value, 'verificar_ao_abrir': preferencias.verificar_ao_abrir},
    )


def gravar_aviso(config_global: Path, ligado: bool) -> None:
    preferencias = ler_preferencias(config_global)
    gravar_preferencias(config_global, Preferencias(preferencias.canal, ligado))


def _manifesto_e_assinatura(canal: CanalAtualizacao, transporte: Transporte) -> tuple[bytes, bytes] | None:
    if canal is CanalAtualizacao.STABLE:
        return (
            transporte.baixar(atualizador.URL_STABLE, atualizador.LIMITE_MANIFESTO),
            transporte.baixar(f'{atualizador.URL_STABLE}.sig', atualizador.LIMITE_ASSINATURA),
        )
    try:
        releases = json.loads(transporte.baixar(atualizador.URL_RELEASES, atualizador.LIMITE_LISTA_RELEASES))
    except json.JSONDecodeError as erro:
        raise ErroDoAmbiente(
            'o GitHub respondeu algo que não é a lista de versões', 'tente mais tarde'
        ) from erro
    for release in releases if isinstance(releases, list) else []:
        if not isinstance(release, dict) or release.get('draft'):
            continue
        urls = {
            asset.get('name'): asset.get('browser_download_url')
            for asset in release.get('assets', [])
            if isinstance(asset, dict)
        }
        manifesto, assinatura = (
            urls.get(atualizador.ARQUIVO_MANIFESTO),
            urls.get(atualizador.ARQUIVO_ASSINATURA),
        )
        if isinstance(manifesto, str) and isinstance(assinatura, str):
            return (
                transporte.baixar(manifesto, atualizador.LIMITE_MANIFESTO),
                transporte.baixar(assinatura, atualizador.LIMITE_ASSINATURA),
            )
    return None


def verificar(
    canal: CanalAtualizacao,
    *,
    transporte: Transporte | None = None,
    instalada: str | None = None,
    sistema: str = sys.platform,
) -> Novidade | None:
    """A versão nova para este sistema, ou None. Manifesto sem assinatura válida é erro, nunca 'sem novidade'."""
    plataforma = atualizador.plataforma(sistema)
    instalada = instalada or versao_instalada()
    baixado = _manifesto_e_assinatura(canal, transporte or TransporteHttps(instalada))
    if baixado is None:
        return None
    conteudo, assinatura = baixado
    atualizador.conferir_assinatura(conteudo, assinatura)
    manifesto = atualizador.ler_manifesto(conteudo)
    artefato = atualizador.escolher(manifesto, instalada, canal, plataforma)
    if artefato is None:
        return None
    return Novidade(
        versao=manifesto.versao,
        canal=manifesto.canal,
        notas=manifesto.notas,
        plataforma=plataforma,
        artefato=artefato,
        url=atualizador.url_do_artefato(manifesto, artefato),
    )


def verificar_ao_abrir(
    config_global: Path,
    estado: Path,
    *,
    agora: datetime,
    transporte: Transporte | None = None,
    instalada: str | None = None,
    sistema: str = sys.platform,
) -> Novidade | None:
    """A consulta do aviso no cabeçalho: opt-in, no máximo uma por dia, e falha só no log."""
    preferencias = ler_preferencias(config_global)
    if not preferencias.verificar_ao_abrir or not atualizador.consulta_vencida(estado, agora):
        return None
    atualizador.registrar_consulta(estado, agora)
    try:
        return verificar(preferencias.canal, transporte=transporte, instalada=instalada, sistema=sistema)
    except ErroDoUsuario as erro:
        logger.info('consulta de atualização ao abrir falhou: %s', erro.causa)
    except Exception:
        logger.info('consulta de atualização ao abrir falhou', exc_info=True)
    return None


def ler_assinatura_windows(caminho: Path) -> tuple[str, str | None]:
    """Status e titular do Authenticode, pelo PowerShell; o caminho vai por variável de ambiente."""
    script = (
        '$a = Get-AuthenticodeSignature -LiteralPath $env:CONCURSO_ALVO; '
        '@{status = "$($a.Status)"; titular = $a.SignerCertificate.Subject} | ConvertTo-Json -Compress'
    )
    saida = subprocess.run(
        ['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
        capture_output=True,
        text=True,
        env={**os.environ, 'CONCURSO_ALVO': str(caminho)},
        check=False,
        timeout=60,
    )
    try:
        dados = json.loads(saida.stdout)
    except json.JSONDecodeError:
        return 'Desconhecido', None
    return str(dados.get('status')), dados.get('titular')


def _conferir_signatario(setup: Path, executavel: Path, ler_assinatura: LerAssinatura) -> None:
    status, titular = ler_assinatura(executavel)
    if status != 'Valid':
        return
    status_setup, titular_setup = ler_assinatura(setup)
    if status_setup != 'Valid' or titular_setup != titular:
        raise ErroDoAmbiente(
            f'o instalador baixado não tem a assinatura de {titular} ({status_setup}, {titular_setup}); '
            'ele foi descartado',
            atualizador.DICA_MANUAL,
        )


def _baixar_conferido(
    novidade: Novidade, destino: Path, transporte: Transporte, progresso: Progresso | None
) -> None:
    try:
        transporte.baixar_para(novidade.url, destino, novidade.artefato.tamanho, progresso)
        atualizador.conferir_sha256(destino, novidade.artefato.sha256)
    except BaseException:
        destino.unlink(missing_ok=True)
        raise


def instalar(
    novidade: Novidade,
    *,
    transporte: Transporte | None = None,
    sistema: str = sys.platform,
    ambiente: Mapping[str, str] | None = None,
    executavel: Path | None = None,
    ler_assinatura: LerAssinatura = ler_assinatura_windows,
    abrir: Abrir = subprocess.Popen,
    pasta_temporaria: Path | None = None,
    progresso: Progresso | None = None,
) -> Instalacao:
    """No Windows, deixa o setup rodando e o app precisa fechar; no Linux, troca o AppImage no lugar."""
    transporte = transporte or TransporteHttps(versao_instalada())
    if atualizador.plataforma(sistema) == 'windows-x64':
        pasta = pasta_temporaria or Path(tempfile.mkdtemp(prefix='concurso-analise-atualizacao-'))
        setup = pasta / novidade.artefato.arquivo
        _baixar_conferido(novidade, setup, transporte, progresso)
        try:
            _conferir_signatario(setup, executavel or Path(sys.executable), ler_assinatura)
        except ErroDoAmbiente:
            setup.unlink(missing_ok=True)
            raise
        abrir(atualizador.comando_do_setup(setup))
        return Instalacao(novidade.versao, setup, setup_em_andamento=True)
    return _trocar_appimage(novidade, transporte, os.environ if ambiente is None else ambiente, progresso)


def _trocar_appimage(
    novidade: Novidade, transporte: Transporte, ambiente: Mapping[str, str], progresso: Progresso | None
) -> Instalacao:
    valor = ambiente.get('APPIMAGE')
    if not valor:
        raise ErroDoUsuario(
            'o app não está rodando de um AppImage, então não há o que trocar', atualizador.DICA_MANUAL
        )
    appimage = Path(valor)
    if not os.access(appimage.parent, os.W_OK):
        raise ErroDoUsuario(
            f'sem permissão de escrita em {appimage.parent} para trocar o AppImage',
            f'mova o AppImage para uma pasta sua (por exemplo, ~/Aplicativos), ou {atualizador.DICA_MANUAL}',
        )
    descritor, nome = tempfile.mkstemp(
        prefix=f'.{appimage.name}.', suffix='.atualizacao', dir=appimage.parent
    )
    os.close(descritor)
    temporario = Path(nome)
    _baixar_conferido(novidade, temporario, transporte, progresso)
    temporario.chmod(0o755)
    os.replace(temporario, appimage)
    return Instalacao(novidade.versao, appimage, setup_em_andamento=False)


def reabrir(instalacao: Instalacao, abrir: Abrir = subprocess.Popen) -> None:
    """Abre o AppImage novo; o processo atual fecha em seguida."""
    ambiente = {
        chave: valor for chave, valor in os.environ.items() if chave not in {'APPIMAGE', 'APPDIR', 'ARGV0'}
    }
    abrir([str(instalacao.caminho)], env=ambiente, start_new_session=True)


def atualizar_executavel(
    opcoes: Opcoes,
    *,
    canal: CanalAtualizacao | None = None,
    executar: bool = False,
    transporte: Transporte | None = None,
    sistema: str = sys.platform,
    instalar_com: Callable[..., Instalacao] | None = None,
) -> int:
    """O `upgrade` do executável: consulta, mostra e, com `executar` e confirmação, instala."""
    canal = canal or ler_preferencias(opcoes.contexto.config_global).canal
    if opcoes.dry_run:
        opcoes.saida(f'dry-run: consultaria o canal {canal.value} em {atualizador.URL_RELEASES_PAGINA}')
        return 0
    if not opcoes.rede:
        raise ErroDoUsuario(
            '--offline não consulta atualizações', 'rode `concurso-analise upgrade` sem --offline'
        )
    novidade = verificar(canal, transporte=transporte, sistema=sistema)
    if novidade is None:
        opcoes.saida(f'concurso-analise {versao_instalada()} é a versão mais nova do canal {canal.value}')
        return 0
    opcoes.saida(f'versão nova: {novidade.versao} ({novidade.canal.value}); notas em {novidade.notas}')
    if not executar:
        opcoes.saida('para instalar: concurso-analise upgrade --run')
        return 0
    pergunta = f'Baixar e instalar a {novidade.versao} ({novidade.artefato.tamanho // 1_000_000} MB)?'
    if not opcoes.interacao_ou_automatica().confirmar(pergunta, padrao=True):
        opcoes.saida('atualização cancelada')
        return 0
    instalacao = (instalar_com or instalar)(novidade, transporte=transporte, sistema=sistema)
    if instalacao.setup_em_andamento:
        opcoes.saida(f'o instalador da {instalacao.versao} continua sozinho e reabre o app no fim')
    else:
        opcoes.saida(f'atualizado para {instalacao.versao} em {instalacao.caminho}; abra o app de novo')
    return 0
