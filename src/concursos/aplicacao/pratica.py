import json
import logging
import shutil
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from concursos import planilha_tec
from concursos.analytics.taxonomia import carregar_taxonomia
from concursos.aplicacao import estudo
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.projeto import curto, pasta_do_candidato
from concursos.biblioteca import (
    BuscaBiblioteca,
    BuscaLocal,
    FontesDeEstudo,
    MapaBiblioteca,
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
from concursos.modelo import EstadoLivro
from concursos.pratica_tec import (
    ARQUIVO_ESCOLHAS,
    ARQUIVO_RESUMO,
    ARQUIVO_SIMULADO,
    PASTA_PRATICA,
    ConfiguracaoPratica,
    ExportacaoInvalidaError,
    ResultadoPratica,
    gravar_escolhas,
    importar_pratica,
    ler_escolhas,
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


def entrada_da_pratica(opcoes: Opcoes) -> Path:
    """A pasta das exportações; sem `[pratica]`, cria a seção com a pasta padrão."""
    contexto = opcoes.contexto
    configuracao = configuracao_pratica(contexto)
    if configuracao is not None:
        return configuracao.entrada
    if not opcoes.dry_run:
        gravar_no_config_projeto(contexto, SECAO_PRATICA, {'entrada_tec': ENTRADA_PADRAO})
    return contexto.raiz / ENTRADA_PADRAO


def importar_exportacoes(opcoes: Opcoes, arquivos: list[Path]) -> list[Path]:
    """Valida todos antes de copiar o primeiro."""
    for arquivo in arquivos:
        validar_exportacao(arquivo)
    entrada = entrada_da_pratica(opcoes)
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


@dataclass(frozen=True)
class PrevisaoPlanilha:
    arquivo: Path
    cabecalho: list[str]
    mapeamento: dict[str, str | None]
    lembrado: bool
    amostra: list[dict[str, str]]

    @property
    def faltando(self) -> list[str]:
        return planilha_tec.faltando(self.mapeamento)


def _ler_planilha(arquivo: Path) -> planilha_tec.Planilha:
    try:
        return planilha_tec.ler_planilha(arquivo)
    except planilha_tec.PlanilhaInvalidaError as erro:
        raise ErroDoUsuario(
            str(erro), 'exporte a planilha de novo, em .csv ou .xlsx, com o cabeçalho na primeira linha'
        ) from erro


def prever_planilha(contexto: Contexto, arquivo: Path) -> PrevisaoPlanilha:
    """As colunas que o app reconheceu (ou as conferidas da última vez, para os mesmos cabeçalhos)."""
    planilha = _ler_planilha(arquivo)
    lembrado = ler_escolhas(contexto.projeto / ARQUIVO_ESCOLHAS).planilhas.get(
        planilha_tec.assinatura(planilha.cabecalho)
    )
    detectado = planilha_tec.detectar_colunas(planilha.cabecalho)
    if lembrado:
        detectado = {campo: lembrado.get(campo) for campo in planilha_tec.CAMPOS}
    return PrevisaoPlanilha(arquivo, planilha.cabecalho, detectado, bool(lembrado), planilha.linhas[:3])


def importar_planilha(
    opcoes: Opcoes,
    arquivo: Path,
    mapeamento: dict[str, str | None] | None = None,
    agora: datetime | None = None,
) -> Path:
    """Converte a planilha para uma exportação do tec-erros na pasta da prática e lembra o mapeamento."""
    contexto = opcoes.contexto
    planilha = _ler_planilha(arquivo)
    mapeamento = mapeamento or prever_planilha(contexto, arquivo).mapeamento
    if faltando := planilha_tec.faltando(mapeamento):
        nomes = ', '.join(planilha_tec.ROTULOS[c] for c in faltando)
        raise ErroDoUsuario(
            f'{arquivo.name}: falta a coluna de {nomes}',
            'escolha as colunas na tela Importar do TEC, ou dê esse nome ao cabeçalho da planilha',
        )
    agora = agora or datetime.now().astimezone()
    try:
        conversao = planilha_tec.converter(planilha, mapeamento, arquivo.name, agora)
    except planilha_tec.PlanilhaInvalidaError as erro:
        raise ErroDoUsuario(str(erro), 'escolha as colunas na tela Importar do TEC') from erro
    if conversao.linhas == conversao.ignoradas:
        raise ErroDoUsuario(
            f'{arquivo.name}: nenhuma linha com disciplina e resultado reconhecido',
            'confira a coluna Resultado: use certo/errado, C/E, sim/não ou 1/0',
        )
    entrada = entrada_da_pratica(opcoes)
    destino = entrada / planilha_tec.nome_da_exportacao(arquivo, agora)
    resumo = (
        f'{arquivo.name}: {conversao.erradas} erro(s) em {conversao.linhas - conversao.ignoradas} questão(ões)'
        + (
            f'; {conversao.ignoradas} linha(s) sem disciplina ou resultado ignorada(s)'
            if conversao.ignoradas
            else ''
        )
    )
    if opcoes.dry_run:
        opcoes.saida(f'{resumo}; gravaria {destino}')
        return destino
    entrada.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(conversao.exportacao, ensure_ascii=False, indent=2), encoding='utf-8')
    escolhas = ler_escolhas(contexto.projeto / ARQUIVO_ESCOLHAS)
    escolhas.planilhas[planilha_tec.assinatura(planilha.cabecalho)] = {
        campo: coluna for campo, coluna in mapeamento.items() if coluna
    }
    gravar_escolhas(contexto.projeto / ARQUIVO_ESCOLHAS, escolhas)
    opcoes.saida(f'{resumo}; gravado em {destino}')
    return destino


@dataclass(frozen=True)
class SaidasDaPratica:
    resumo: str | None
    simulado: Path | None


def saidas_da_pratica(contexto: Contexto) -> SaidasDaPratica:
    """O resumo com as prioridades e o simulado com os erros, da última análise do candidato escolhido."""
    try:
        pasta = pasta_do_candidato(contexto) / PASTA_PRATICA
    except ErroDoUsuario:
        return SaidasDaPratica(None, None)
    resumo, simulado = pasta / ARQUIVO_RESUMO, pasta / ARQUIVO_SIMULADO
    return SaidasDaPratica(
        resumo.read_text(encoding='utf-8') if resumo.is_file() else None,
        simulado if simulado.is_file() else None,
    )


def eh_planilha(arquivo: Path) -> bool:
    return arquivo.suffix.lower() in planilha_tec.EXTENSOES


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
            configuracao_analise.dicionario,
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


LIVRO_LIDO = {EstadoLivro.LIDO, EstadoLivro.ENVIANDO, EstadoLivro.PRONTO}


def fontes_de_estudo(contexto: Contexto) -> FontesDeEstudo:
    try:
        fontes = ler_fontes_de_estudo(
            contexto.projeto, contexto.raiz, contexto.taxonomia, contexto.config_global
        )
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(
            str(erro), 'corrija o .concurso/biblioteca.yaml ou a seção [legislacao] e rode de novo'
        ) from erro
    if not livros_do_app(contexto):
        return fontes
    mapa = fontes.mapa or MapaBiblioteca({})
    return replace(fontes, mapa=replace(mapa, por_disciplina=True))


def livros_do_app(contexto: Contexto) -> dict[str, dict[str, str]]:
    """Os livros lidos da biblioteca do app, por disciplina (sha → nome)."""
    por_disciplina: dict[str, dict[str, str]] = {}
    for livro in estudo.listar_livros(contexto):
        if livro.estado in LIVRO_LIDO and livro.disciplina:
            por_disciplina.setdefault(livro.disciplina, {})[livro.sha] = livro.nome
    return por_disciplina


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


def busca_na_biblioteca(opcoes: Opcoes, fontes: FontesDeEstudo) -> BuscaBiblioteca | BuscaLocal | None:
    """Os livros do app, pelo índice local, vêm primeiro. O open-notebook externo só entra ligado, com
    consentimento e rede; senão, fica o catálogo."""
    if fontes.mapa is None:
        return None
    if livros := livros_do_app(opcoes.contexto):
        return BuscaLocal(estudo.biblioteca(opcoes.contexto).banco, livros)
    if not opcoes.rede:
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
