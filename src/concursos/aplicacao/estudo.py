"""Estudar com os livros: preparar o open-notebook no computador, enviar, listar, remover e perguntar.

As mensagens daqui aparecem para o usuário leigo; o teste de vocabulário as confere.
"""

import atexit
import logging
import re
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from concursos.aplicacao import atualizador as atualizacao
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import Contexto
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.estudo import embeddings, instalacao
from concursos.estudo.instalacao import PacoteDisponivel, Pastas
from concursos.estudo.supervisor import VARIAVEL_CIFRA, Sessao, Supervisor
from concursos.integracoes.open_notebook import ClienteOpenNotebook
from concursos.llm import guardar_chave, obter_chave_da_variavel

logger = logging.getLogger(__name__)

TAMANHO_ESTIMADO_MB = 360
TEXTO_PREPARAR = (
    'Para estudar com seus livros, o app precisa preparar o open-notebook no seu computador. '
    'É um download único de cerca de {mb} MB; seus livros não saem do computador.'
)
TEXTO_PREPARANDO = 'Sua biblioteca está sendo preparada; os envios continuam sozinhos.'
TEXTO_FORA = 'O open-notebook não abriu agora. A busca continua nos seus livros, só que mais simples.'

ProgressoEstudo = Callable[[str, float], None]

_supervisores: dict[Path, Supervisor] = {}
_trava = threading.Lock()


@dataclass(frozen=True)
class SituacaoEstudo:
    disponivel_no_sistema: bool
    versao: str | None
    aberto: bool
    fora_do_ar: bool
    mensagem: str

    @property
    def preparado(self) -> bool:
        return self.versao is not None


def pastas(contexto: Contexto) -> Pastas:
    return Pastas.do_home(contexto.home)


def chave_de_cifra(home: Path) -> str:
    """A chave que cifra as credenciais no banco do open-notebook; gerada uma vez e guardada no keyring."""
    encontrada = obter_chave_da_variavel(VARIAVEL_CIFRA, home)
    if encontrada:
        return encontrada[0]
    chave = secrets.token_urlsafe(32)
    guardar_chave(VARIAVEL_CIFRA, chave, home)
    return chave


def _registrar_embeddings(sessao: Sessao) -> None:
    embeddings.registrar(ClienteOpenNotebook(sessao.url, sessao.senha, timeout=60))


def supervisor(contexto: Contexto) -> Supervisor:
    """Um supervisor por pasta global, parado quando o app fecha."""
    with _trava:
        existente = _supervisores.get(contexto.home)
        if existente is not None:
            return existente
        novo = Supervisor(
            pastas(contexto),
            contexto.logs,
            chave_cifra=lambda: chave_de_cifra(contexto.home),
            ao_subir=[_registrar_embeddings],
        )
        novo.vigiar()
        atexit.register(novo.parar)
        _supervisores[contexto.home] = novo
        return novo


def situacao_do_estudo(contexto: Contexto, sistema: str | None = None) -> SituacaoEstudo:
    try:
        instalacao.plataforma(*([sistema] if sistema else []))
    except ErroDoUsuario as erro:
        return SituacaoEstudo(False, None, False, False, erro.causa)
    raiz = instalacao.instalado(pastas(contexto))
    if raiz is None:
        return SituacaoEstudo(True, None, False, False, TEXTO_PREPARAR.format(mb=TAMANHO_ESTIMADO_MB))
    versao = instalacao.ler_estado(pastas(contexto)).atual
    existente = _supervisores.get(contexto.home)
    aberto = existente is not None and existente.sessao is not None
    fora = existente is not None and existente.indisponivel
    mensagem = TEXTO_FORA if fora else 'Sua biblioteca está pronta.'
    return SituacaoEstudo(True, versao, aberto, fora, mensagem)


def procurar_pacote(opcoes: Opcoes, transporte=None) -> PacoteDisponivel | None:  # noqa: ANN001
    if not opcoes.rede:
        raise ErroDoUsuario(
            'sem internet não dá para preparar a biblioteca', 'tente de novo com a internet ligada'
        )
    canal = atualizacao.ler_preferencias(opcoes.contexto.config_global).canal
    versao = atualizacao.versao_instalada()
    return instalacao.procurar(canal, transporte or atualizacao.TransporteHttps(versao), versao)


def preparar_estudo(
    opcoes: Opcoes,
    *,
    consentiu: bool,
    arquivo: Path | None = None,
    progresso: ProgressoEstudo | None = None,
    transporte=None,  # noqa: ANN001
) -> str:
    """Baixa (ou instala de `arquivo`) o pacote de estudo; devolve a versão instalada."""
    if opcoes.dry_run:
        opcoes.saida('prepararia o open-notebook no computador')
        return ''
    alvo = pastas(opcoes.contexto)
    if arquivo is not None:
        encontrada = re.match(r'estudo-(\d+\.\d+\.\d+-\d+)-', arquivo.name)
        if encontrada is None:
            raise ErroDoUsuario(
                f'{arquivo.name} não é um pacote de estudo', 'use o arquivo estudo-<versão>-<sistema>'
            )
        versao = encontrada.group(1)
        instalacao.instalar_arquivo(alvo, arquivo, versao)
        opcoes.saida(f'biblioteca preparada (open-notebook {versao.split("-")[0]})')
        return versao
    if not consentiu:
        raise ErroDoUsuario(
            'a biblioteca só é preparada depois que você concordar', 'clique em "Preparar agora"'
        )
    if progresso:
        progresso('Procurando a versão mais nova…', 0.0)
    disponivel = procurar_pacote(opcoes, transporte)
    if disponivel is None:
        raise ErroDoAmbiente(
            'ainda não há uma biblioteca para esta versão do app', 'atualize o app e tente de novo'
        )
    if not instalacao.tem_atualizacao(alvo, disponivel):
        return disponivel.manifesto.versao

    def ao_baixar(feito: int, total: int) -> None:
        if progresso:
            progresso(f'Baixando: {feito * 100 // max(total, 1)}%', feito / max(total, 1))

    raiz = instalacao.instalar(
        alvo,
        disponivel,
        transporte or atualizacao.TransporteHttps(atualizacao.versao_instalada()),
        consentiu=True,
        offline=not opcoes.rede,
        progresso=ao_baixar,
    )
    if progresso:
        progresso('Pronto', 1.0)
    opcoes.saida(f'biblioteca preparada (open-notebook {disponivel.manifesto.open_notebook})')
    logger.info('pacote de estudo instalado em %s', raiz)
    return disponivel.manifesto.versao


def cliente_gerenciado(contexto: Contexto) -> ClienteOpenNotebook:
    """O cliente da instância gerenciada, subindo os processos se preciso."""
    sessao = supervisor(contexto).garantir()
    return ClienteOpenNotebook(sessao.url, sessao.senha, timeout=300)


def parar_estudo(contexto: Contexto) -> None:
    existente = _supervisores.get(contexto.home)
    if existente is not None:
        existente.parar()
