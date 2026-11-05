import logging
import shutil
from pathlib import Path

from concursos.analytics.taxonomia import carregar_taxonomia
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import curto
from concursos.biblioteca import (
    BuscaBiblioteca,
    FontesDeEstudo,
    gravar_recomendacoes,
    indexar_biblioteca,
    ler_fontes_de_estudo,
    recomendar,
    topicos_fracos,
)
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import Contexto, gravar_no_config_projeto
from concursos.configuracao import ConfiguracaoGlobal
from concursos.erros import ErroDoUsuario
from concursos.integracoes.open_notebook import (
    ClienteOpenNotebook,
    OpenNotebookIndisponivelError,
    ler_configuracao,
)
from concursos.pratica_tec import (
    ARQUIVO_ESCOLHAS,
    ConfiguracaoPratica,
    ExportacaoInvalidaError,
    ResultadoPratica,
    importar_pratica,
    ler_exportacao,
    ler_pratica,
    textos_do_caderno,
)
from concursos.pratica_tec import ARQUIVO_ESTADO as ARQUIVO_ESTADO_CADERNO
from concursos.pratica_tec import SECAO as SECAO_PRATICA
from concursos.pratica_tec import ler_configuracao as ler_configuracao_pratica

logger = logging.getLogger(__name__)

ENTRADA_PADRAO = 'tec'


def configuracao_pratica(contexto: Contexto) -> ConfiguracaoPratica | None:
    try:
        return ler_configuracao_pratica(contexto.config_projeto, contexto.raiz)
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(str(erro), 'corrija a seção [pratica] do .concurso/config.toml') from erro


def exigir_configuracao_pratica(contexto: Contexto) -> ConfiguracaoPratica:
    configuracao = configuracao_pratica(contexto)
    if configuracao is None:
        raise ErroDoUsuario(
            'o projeto não tem a seção [pratica]',
            'acrescente `[pratica]` com `entrada_tec = "<pasta das exportações>"` ao .concurso/config.toml',
        )
    return configuracao


def validar_exportacao(arquivo: Path) -> None:
    if not arquivo.is_file():
        raise ErroDoUsuario(
            f'{arquivo}: arquivo não encontrado', 'confira o caminho da exportação do tec-erros'
        )
    if arquivo.name != ARQUIVO_ESTADO_CADERNO:
        try:
            ler_exportacao(arquivo)
        except ExportacaoInvalidaError as erro:
            raise ErroDoUsuario(
                str(erro), 'exporte de novo pela extensão, pelo userscript ou pelo caderno.html'
            ) from erro


def importar_exportacoes(opcoes: Opcoes, arquivos: list[Path]) -> list[Path]:
    """Valida todos antes de copiar o primeiro; sem `[pratica]`, a GUI cria a seção com a pasta padrão."""
    for arquivo in arquivos:
        validar_exportacao(arquivo)
    contexto = opcoes.contexto
    configuracao = configuracao_pratica(contexto)
    if configuracao is None:
        if not opcoes.dry_run:
            gravar_no_config_projeto(contexto, SECAO_PRATICA, {'entrada_tec': ENTRADA_PADRAO})
        entrada = contexto.raiz / ENTRADA_PADRAO
    else:
        entrada = configuracao.entrada
    for arquivo in arquivos:
        copiar_exportacao(opcoes, arquivo, entrada)
    return [entrada / arquivo.name for arquivo in arquivos]


def copiar_exportacao(opcoes: Opcoes, arquivo: Path, entrada: Path) -> None:
    validar_exportacao(arquivo)
    destino = entrada / arquivo.name
    if opcoes.dry_run:
        opcoes.saida(f'copiaria {arquivo} para {destino}')
        return
    entrada.mkdir(parents=True, exist_ok=True)
    if arquivo.resolve() != destino.resolve():
        shutil.copy2(arquivo, destino)
    opcoes.saida(f'exportação copiada para {destino}')


def praticar(
    opcoes: Opcoes, candidato: str | None, destino: Path, configuracao_analise: ConfiguracaoGlobal | None
) -> ResultadoPratica | None:
    """Importa a prática do TEC para o candidato dono dela: `[pratica] candidato` ou o desta execução."""
    contexto = opcoes.contexto
    configuracao = configuracao_pratica(contexto)
    if configuracao is None:
        return None
    if configuracao.candidato is None and opcoes.todos and candidato is not None:
        logger.warning('prática: com --all-candidates, diga de quem é a prática em [pratica] candidato')
        return None
    if (configuracao.candidato or candidato) != candidato:
        return None
    if opcoes.dry_run or configuracao_analise is None:
        opcoes.saida(f'prática: importaria {curto(configuracao.entrada, contexto.raiz)}')
        return None
    if not configuracao.entrada.is_dir():
        logger.warning('prática: a pasta %s não existe; nada a importar', configuracao.entrada)
    taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else {}
    limiar = configuracao_analise.limiar_topico_baixo
    fracos, _ = topicos_fracos(curto(contexto.provas, contexto.raiz), destino, contexto.taxonomia, limiar)
    try:
        return importar_pratica(
            configuracao.entrada,
            destino,
            contexto.projeto / ARQUIVO_ESCOLHAS,
            taxonomia,
            configuracao_analise.concurso_alvo,
            opcoes.interacao,
            fracos,
        )
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(str(erro), f'corrija ou apague {contexto.projeto / ARQUIVO_ESCOLHAS}') from erro


def caderno_de_erros(contexto: Contexto, candidatos: list[str | None]) -> dict[str | None, dict[str, str]]:
    """Os erros do TEC só vão ao open-notebook com `[pratica] open_notebook = true`, e para o dono da prática."""
    configuracao = configuracao_pratica(contexto)
    if configuracao is None or not configuracao.open_notebook:
        return {}
    dono = configuracao.candidato or (candidatos[0] if len(candidatos) == 1 else None)
    if dono not in candidatos:
        return {}
    taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else {}
    lido = ler_pratica(configuracao.entrada, contexto.projeto / ARQUIVO_ESCOLHAS, taxonomia)
    return {dono: textos_do_caderno(lido)} if lido.pratica.erros else {}


def fontes_de_estudo(contexto: Contexto) -> FontesDeEstudo:
    try:
        return ler_fontes_de_estudo(
            contexto.projeto, contexto.raiz, contexto.taxonomia, contexto.config_global
        )
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(
            str(erro), 'corrija o .concurso/biblioteca.yaml ou a seção [legislacao] e rode de novo'
        ) from erro


def recomendar_estudo(
    opcoes: Opcoes,
    fontes: FontesDeEstudo,
    provas: Path,
    destino: Path,
    limiar: float,
    textos_pratica: list[str] | None = None,
) -> bool:
    """Grava `recomendacoes_estudo.md`; devolve se o arquivo mudou."""
    if fontes.vazias:
        return False
    fracos, avisos = topicos_fracos(provas, destino, opcoes.contexto.taxonomia, limiar)
    busca = busca_na_biblioteca(opcoes, fontes) if fontes.mapa is not None else None
    resultado = recomendar(
        fracos, limiar, fontes.mapa, fontes.repositorio, busca, avisos, textos_pratica or []
    )
    return gravar_recomendacoes(destino, resultado)


def busca_na_biblioteca(opcoes: Opcoes, fontes: FontesDeEstudo) -> BuscaBiblioteca | None:
    """A camada do open-notebook só entra ligada, com consentimento e rede; senão, fica o catálogo."""
    if not opcoes.rede or fontes.mapa is None:
        return None
    try:
        configuracao = ler_configuracao(opcoes.contexto.config_global)
    except ConfiguracaoInvalidaError:
        return None
    if not configuracao.ativa:
        return None
    try:
        cliente = ClienteOpenNotebook.da_configuracao(configuracao, opcoes.contexto.home)
        cliente.saude()
        return BuscaBiblioteca(cliente, indexar_biblioteca(cliente, fontes.mapa))
    except OpenNotebookIndisponivelError as erro:
        logger.warning('open-notebook: %s; recomendações só pelo catálogo', erro.causa)
        return None
