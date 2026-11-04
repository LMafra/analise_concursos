import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated

import typer

from concursos import doctor as diagnostico
from concursos import onboarding, relatorio_html
from concursos.analytics.consolidado import concursos_analisados
from concursos.analytics.taxonomia import carregar_taxonomia
from concursos.assistente import InteracaoAutomatica, InteracaoConsole
from concursos.biblioteca import (
    BuscaBiblioteca,
    FontesDeEstudo,
    gravar_recomendacoes,
    indexar_biblioteca,
    ler_fontes_de_estudo,
    recomendar,
    topicos_fracos,
)
from concursos.cadastro import cadastrar
from concursos.calibracao import CalibracaoError
from concursos.candidatos import (
    adicionar_arquivo,
    candidatos_existentes,
    completar_perfis,
    gravar_perfil_global,
    gravar_revisao,
    pasta_do_candidato,
    slug,
)
from concursos.cli.erros import CODIGO_AMBIENTE, ErroDoAmbiente, ErroDoUsuario, ajustar_nivel_console
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import (
    VARIAVEL_ANALISES,
    VARIAVEL_CANDIDATO,
    VARIAVEL_PROVAS,
    Contexto,
    gravar_no_config_projeto,
    ler_toml,
    resolver_contexto,
)
from concursos.configuracao import ConfiguracaoGlobal, configuracao_do_projeto
from concursos.consolidado import comparar_candidatos
from concursos.exportacao import FormatoExportacao, exportar_consolidado
from concursos.integracoes.open_notebook import (
    DICA_INSTANCIA,
    ClienteOpenNotebook,
    ConfiguracaoOpenNotebook,
    OpenNotebookIndisponivelError,
    gravar_configuracao,
    ler_configuracao,
)
from concursos.integracoes.sincronizacao_notebook import (
    ARQUIVO_ESTADO,
    ARTEFATOS_DO_CONCURSO,
    ARTEFATOS_DO_CONSOLIDADO,
    EstadoSincronizacao,
    RelatorioSincronizacao,
    Sincronizador,
    sincronizar_candidato,
)
from concursos.llm import ClienteComMemoria, ClienteLlm, cliente_configurado
from concursos.manifesto import ARQUIVO_MANIFESTO
from concursos.migracao import MigracaoError, executar_migracao, planejar_migracao
from concursos.pipeline import ARQUIVO_RESPOSTAS, analisar_todos, planejar
from concursos.pratica_tec import (
    ARQUIVO_ESCOLHAS,
    ConfiguracaoPratica,
    ExportacaoInvalidaError,
    ResultadoPratica,
    importar_pratica,
    ler_exportacao,
    ler_pratica,
    textos_do_caderno,
    textos_para_normas,
)
from concursos.pratica_tec import ARQUIVO_ESTADO as ARQUIVO_ESTADO_CADERNO
from concursos.pratica_tec import ler_configuracao as ler_configuracao_pratica
from concursos.respostas import RespostasInvalidasError
from concursos.status import avaliar, formatar_tabela, listar_concursos

logger = logging.getLogger(__name__)

app = typer.Typer(
    name='concurso-analise',
    help='Correção e análise de provas de concurso. Sem subcomando, analisa o que mudou.',
    add_completion=False,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
)
notebook_app = typer.Typer(
    help='sincronização opcional com uma instância local do open-notebook',
    no_args_is_help=True,
    rich_markup_mode=None,
)
app.add_typer(notebook_app, name='notebook')
pratica_app = typer.Typer(
    help='prática no TEC: as exportações do tec-erros', no_args_is_help=True, rich_markup_mode=None
)
app.add_typer(pratica_app, name='pratica')


@dataclass(frozen=True)
class Opcoes:
    contexto: Contexto
    sim: bool = False
    dry_run: bool = False
    forcar: bool = False
    todos: bool = False
    abrir: bool = True
    llm: bool = True
    rede: bool = True
    fornecidos: frozenset[str] = frozenset()


Forcar = Annotated[bool, typer.Option('--force', help='reprocessa mesmo sem mudanças')]
DryRun = Annotated[bool, typer.Option('--dry-run', help='mostra o que seria feito, sem gravar nada')]
Candidato = Annotated[
    str | None, typer.Option('--candidate', help='candidato (padrão: o último usado neste projeto)')
]
Todos = Annotated[
    bool, typer.Option('--all-candidates', help='analisa todos os candidatos e gera o comparativo entre eles')
]
NaoAbrir = Annotated[bool, typer.Option('--no-open', help='não abre o relatório no navegador')]
SemLlm = Annotated[bool, typer.Option('--no-llm', help='não usa o LLM configurado nesta execução')]
Offline = Annotated[
    bool, typer.Option('--offline', help='nenhuma chamada de rede (desliga o LLM e o open-notebook)')
]


@app.callback(invoke_without_command=True)
def principal(
    ctx: typer.Context,
    sim: Annotated[bool, typer.Option('--yes', '-y', help='aceita os padrões sem perguntar')] = False,
    quieto: Annotated[bool, typer.Option('--quiet', '-q', help='só avisos e erros')] = False,
    detalhado: Annotated[bool, typer.Option('--verbose', '-v', help='log detalhado')] = False,
    dry_run: DryRun = False,
    forcar: Forcar = False,
    candidato: Candidato = None,
    todos: Todos = False,
    nao_abrir: NaoAbrir = False,
    sem_llm: SemLlm = False,
    offline: Offline = False,
    data_dir: Annotated[
        Path | None, typer.Option('--data-dir', help='configuração do projeto (padrão: ./.concurso)')
    ] = None,
    provas: Annotated[
        Path | None, typer.Option('--provas', help='pasta com uma subpasta por concurso (padrão: ./provas)')
    ] = None,
    analises: Annotated[
        Path | None, typer.Option('--analises', help='pasta de saída (padrão: ./analises)')
    ] = None,
) -> int | None:
    if quieto and detalhado:
        raise ErroDoUsuario('--quiet e --verbose não combinam', 'use só uma das duas opções')
    ajustar_nivel_console(logging.WARNING if quieto else logging.DEBUG if detalhado else logging.INFO)
    contexto = resolver_contexto(
        data_dir=data_dir, provas=provas, analises=analises, candidato=candidato and slug(candidato)
    )
    fornecidos = frozenset(
        nome
        for nome, flag, variavel in (
            ('nome', candidato, VARIAVEL_CANDIDATO),
            ('provas', provas, VARIAVEL_PROVAS),
            ('analises', analises, VARIAVEL_ANALISES),
        )
        if flag or os.environ.get(variavel)
    )
    ctx.obj = Opcoes(
        contexto,
        sim=sim,
        dry_run=dry_run,
        forcar=forcar,
        todos=todos,
        abrir=not nao_abrir,
        llm=not (sem_llm or offline),
        rede=not offline,
        fornecidos=fornecidos,
    )
    if ctx.invoked_subcommand is None:
        if onboarding.precisa_de_onboarding(contexto) and not dry_run:
            return _onboarding(ctx.obj)
        return _analisar(ctx.obj)
    return None


@app.command('init', help='refaz as perguntas do onboarding, com as respostas atuais como padrão')
def init(
    ctx: typer.Context,
    doctor: Annotated[
        bool | None, typer.Option('--doctor/--no-doctor', help='confere o ambiente no fim')
    ] = None,
    folha: Annotated[
        Path | None, typer.Option('--calibrate-sheet', help='folha preenchida para calibrar a leitura')
    ] = None,
    digitadas: Annotated[
        str | None,
        typer.Option('--calibrate-answers', help='respostas das 5 primeiras questões da folha (ex.: ABCD-)'),
    ] = None,
) -> int:
    opcoes: Opcoes = ctx.obj
    if opcoes.dry_run:
        typer.echo('o init não grava nada com --dry-run')
        return 0
    ambiente = {}
    if folha is not None:
        ambiente[onboarding.VARIAVEL_CALIBRAR_FOLHA] = str(folha)
    if digitadas is not None:
        ambiente[onboarding.VARIAVEL_CALIBRAR_RESPOSTAS] = digitadas
    return _onboarding(opcoes, doctor, ambiente)


@app.command('analyze', help='analisa os concursos que mudaram (ou só o indicado)')
def analyze(
    ctx: typer.Context,
    concurso: Annotated[str | None, typer.Argument(help='nome da pasta do concurso')] = None,
    forcar: Forcar = False,
    dry_run: DryRun = False,
    candidato: Candidato = None,
    todos: Todos = False,
    nao_abrir: NaoAbrir = False,
    reaproveitar: Annotated[
        bool,
        typer.Option(
            '--reuse-csv',
            help='usa o respostas_extraidas.csv corrigido à mão no lugar da leitura da folha',
        ),
    ] = False,
) -> int:
    opcoes = replace(
        ctx.obj,
        forcar=ctx.obj.forcar or forcar,
        dry_run=ctx.obj.dry_run or dry_run,
        todos=ctx.obj.todos or todos,
        abrir=ctx.obj.abrir and not nao_abrir,
    )
    opcoes = replace(opcoes, contexto=_com_candidato(opcoes.contexto, candidato))
    return _analisar(opcoes, concurso, reaproveitar)


@app.command('report', help='reabre o último relatório HTML')
def report(ctx: typer.Context, candidato: Candidato = None) -> int:
    contexto = _com_candidato(ctx.obj.contexto, candidato)
    indice = _pasta_do_candidato(contexto) / relatorio_html.ARQUIVO_INDICE
    if not indice.exists():
        raise ErroDoUsuario(
            f'{indice}: relatório ainda não gerado',
            'rode `concurso-analise` para analisar e gerar o relatório',
        )
    if ctx.obj.abrir:
        relatorio_html.abrir_no_navegador(indice)
    typer.echo(f'relatório: {indice}')
    return 0


@app.command('export', help='grava o consolidado do candidato, uma linha por questão')
def export(
    ctx: typer.Context,
    formato: Annotated[
        FormatoExportacao, typer.Option('--format', help='formato do arquivo')
    ] = FormatoExportacao.CSV,
    candidato: Candidato = None,
) -> int:
    contexto = _com_candidato(ctx.obj.contexto, candidato)
    _exigir_provas(contexto.provas)
    pasta = _pasta_do_candidato(contexto)
    if not concursos_analisados(contexto.provas, pasta):
        raise ErroDoUsuario(
            f'{pasta}: nenhum concurso analisado para exportar', 'rode `concurso-analise` antes do export'
        )
    destino = exportar_consolidado(contexto.provas, pasta, contexto.taxonomia, formato)
    typer.echo(f'consolidado exportado para {destino}')
    return 0


@app.command('add', help='cadastra a pasta de um concurso ou acrescenta as respostas de um candidato')
def add(
    ctx: typer.Context,
    caminho: Annotated[Path, typer.Argument(help='pasta do concurso, ou arquivo de respostas ou folha')],
    candidato: Candidato = None,
    concurso: Annotated[str | None, typer.Option('--concurso', help='pasta do concurso em provas/')] = None,
) -> int:
    opcoes: Opcoes = ctx.obj
    contexto = opcoes.contexto
    if caminho.is_dir():
        if opcoes.dry_run:
            typer.echo(f'cadastraria {caminho} (concurso.yaml)')
            return 0
        interacao = InteracaoConsole() if onboarding.interativo(opcoes.sim) else InteracaoAutomatica()
        return 0 if cadastrar(caminho, interacao) else 1
    if not caminho.is_file():
        raise ErroDoUsuario(f'arquivo não encontrado: {caminho}', 'confira o caminho do arquivo de respostas')
    nome = candidato or contexto.candidato
    if not nome:
        raise ErroDoUsuario(
            'falta dizer de qual candidato é o arquivo', 'rode de novo com --candidate <nome>'
        )
    _exigir_provas(contexto.provas)
    pasta = _concurso_do_arquivo(contexto.provas, caminho, concurso)
    if opcoes.dry_run:
        typer.echo(f'copiaria {caminho} para {pasta_do_candidato(pasta, slug(nome))}')
        return 0
    destino = adicionar_arquivo(pasta, caminho, nome)
    gravar_perfil_global(contexto.home, nome)
    typer.echo(f'{caminho.name} copiado para {destino}')
    return 0


@app.command('status', help='mostra a situação de cada concurso')
def status(
    ctx: typer.Context,
    provas: Annotated[
        Path | None, typer.Option('--provas', help='pasta com uma subpasta por concurso')
    ] = None,
) -> int:
    contexto = ctx.obj.contexto
    raiz_provas = provas or contexto.provas
    _exigir_provas(raiz_provas)
    situacoes = [avaliar(pasta) for pasta in listar_concursos(raiz_provas)]
    typer.echo(formatar_tabela(situacoes))
    return 0


@app.command('doctor', help='verifica o ambiente e diz como corrigir o que falta')
def doctor(ctx: typer.Context) -> int:
    itens = _diagnosticar(ctx.obj.contexto)
    return CODIGO_AMBIENTE if diagnostico.tem_erro(itens) else 0


@app.command('upgrade', help='mostra (ou, com --run, executa) o comando que atualiza a ferramenta')
def upgrade(
    ctx: typer.Context,
    executar: Annotated[bool, typer.Option('--run', help='executa a atualização agora')] = False,
) -> int:
    comando = ['tool', 'upgrade', 'concurso-analise']
    if not executar or ctx.obj.dry_run:
        typer.echo(f'para atualizar: uv {" ".join(comando)}')
        return 0
    uv = shutil.which('uv')
    if uv is None:
        raise ErroDoAmbiente(
            'uv não encontrado no PATH', 'instale o uv (https://docs.astral.sh/uv/) e rode de novo'
        )
    return subprocess.run([uv, *comando], check=False).returncode


@notebook_app.command(
    'enable', help='liga a sincronização com o open-notebook, depois de confirmar o que vai'
)
def notebook_enable(
    ctx: typer.Context,
    url: Annotated[
        str | None, typer.Option('--url', help='endereço da API (padrão: http://localhost:5055)')
    ] = None,
) -> int:
    opcoes: Opcoes = ctx.obj
    configuracao = _configuracao_open_notebook(opcoes.contexto)
    url = url or configuracao.url
    typer.echo(_aviso_open_notebook(url, configuracao))
    if opcoes.dry_run:
        typer.echo(f'ligaria a sincronização com {url}')
        return 0
    if not opcoes.sim:
        if not onboarding.interativo(False):
            raise ErroDoUsuario(
                'ligar o open-notebook exige confirmação, e não há terminal para perguntar',
                'confirme com `concurso-analise --yes notebook enable`',
            )
        if not typer.confirm('ligar a sincronização?', default=False):
            typer.echo('nada foi gravado')
            return 0
    gravar_configuracao(opcoes.contexto.config_global, enabled=True, consentimento=True, url=url)
    typer.echo(f'open-notebook ligado: {url}; rode `concurso-analise notebook sync` para enviar agora')
    return 0


@notebook_app.command('disable', help='desliga a sincronização (a configuração continua gravada)')
def notebook_disable(ctx: typer.Context) -> int:
    opcoes: Opcoes = ctx.obj
    _configuracao_open_notebook(opcoes.contexto)
    if opcoes.dry_run:
        typer.echo('desligaria a sincronização com o open-notebook')
        return 0
    gravar_configuracao(opcoes.contexto.config_global, enabled=False)
    typer.echo('open-notebook desligado')
    return 0


@pratica_app.command(
    'import', help='copia uma exportação do tec-erros para a pasta [pratica] entrada_tec e analisa'
)
def pratica_import(
    ctx: typer.Context,
    arquivo: Annotated[
        Path | None, typer.Argument(help='tec-erros-*.json ou caderno-estado.json (sem ele, só analisa)')
    ] = None,
    candidato: Candidato = None,
    nao_abrir: NaoAbrir = False,
) -> int:
    opcoes = replace(ctx.obj, abrir=ctx.obj.abrir and not nao_abrir)
    opcoes = replace(opcoes, contexto=_com_candidato(opcoes.contexto, candidato))
    configuracao = _configuracao_pratica(opcoes.contexto)
    if configuracao is None:
        raise ErroDoUsuario(
            'o projeto não tem a seção [pratica]',
            'acrescente `[pratica]` com `entrada_tec = "<pasta das exportações>"` ao .concurso/config.toml',
        )
    if arquivo is not None:
        _copiar_exportacao(opcoes, arquivo, configuracao.entrada)
    return _analisar(opcoes)


def _copiar_exportacao(opcoes: Opcoes, arquivo: Path, entrada: Path) -> None:
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
    destino = entrada / arquivo.name
    if opcoes.dry_run:
        typer.echo(f'copiaria {arquivo} para {destino}')
        return
    entrada.mkdir(parents=True, exist_ok=True)
    if arquivo.resolve() != destino.resolve():
        shutil.copy2(arquivo, destino)
    typer.echo(f'exportação copiada para {destino}')


def _configuracao_pratica(contexto: Contexto) -> ConfiguracaoPratica | None:
    try:
        return ler_configuracao_pratica(contexto.config_projeto, contexto.raiz)
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(str(erro), 'corrija a seção [pratica] do .concurso/config.toml') from erro


def _praticar(
    opcoes: Opcoes, candidato: str | None, destino: Path, configuracao_analise: ConfiguracaoGlobal | None
) -> ResultadoPratica | None:
    """Importa a prática do TEC para o candidato dono dela: `[pratica] candidato` ou o desta execução."""
    contexto = opcoes.contexto
    configuracao = _configuracao_pratica(contexto)
    if configuracao is None:
        return None
    if configuracao.candidato is None and opcoes.todos and candidato is not None:
        logger.warning('prática: com --all-candidates, diga de quem é a prática em [pratica] candidato')
        return None
    if (configuracao.candidato or candidato) != candidato:
        return None
    if opcoes.dry_run or configuracao_analise is None:
        typer.echo(f'prática: importaria {_curto(configuracao.entrada, contexto.raiz)}')
        return None
    if not configuracao.entrada.is_dir():
        logger.warning('prática: a pasta %s não existe; nada a importar', configuracao.entrada)
    taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else {}
    limiar = configuracao_analise.limiar_topico_baixo
    fracos, _ = topicos_fracos(_curto(contexto.provas, contexto.raiz), destino, contexto.taxonomia, limiar)
    try:
        return importar_pratica(
            configuracao.entrada,
            destino,
            contexto.projeto / ARQUIVO_ESCOLHAS,
            taxonomia,
            configuracao_analise.concurso_alvo,
            InteracaoConsole() if onboarding.interativo(opcoes.sim) else None,
            fracos,
        )
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(str(erro), f'corrija ou apague {contexto.projeto / ARQUIVO_ESCOLHAS}') from erro


@notebook_app.command('sync', help='envia as análises para o open-notebook e mostra o resumo')
def notebook_sync(
    ctx: typer.Context,
    concurso: Annotated[str | None, typer.Option('--concurso', help='só este concurso')] = None,
    candidato: Candidato = None,
    todos: Todos = False,
) -> int:
    opcoes: Opcoes = ctx.obj
    contexto = _com_candidato(opcoes.contexto, candidato)
    _exigir_provas(contexto.provas)
    configuracao = _configuracao_open_notebook(contexto)
    if not configuracao.ativa:
        raise ErroDoUsuario(
            'a sincronização com o open-notebook está desligada',
            'ligue com `concurso-analise notebook enable`',
        )
    if not opcoes.rede:
        raise ErroDoUsuario('notebook sync usa a rede e foi pedido --offline', 'rode de novo sem --offline')
    candidatos = _candidatos_da_execucao(contexto, todos or opcoes.todos)
    if opcoes.dry_run:
        for nome_candidato in candidatos:
            pasta = contexto.analises / nome_candidato if nome_candidato else contexto.analises
            prefixo = f'{nome_candidato}/' if nome_candidato else ''
            for nome in concursos_analisados(contexto.provas, pasta):
                if concurso in (None, nome):
                    typer.echo(f'{prefixo}{nome}: sincronizaria com {configuracao.url}')
        return 0
    try:
        relatorio = _sincronizar_notebooks(contexto, configuracao, candidatos, concurso)
    except OpenNotebookIndisponivelError as erro:
        if erro.status in (401, 403):
            raise ErroDoUsuario(erro.causa, erro.dica) from erro
        raise ErroDoAmbiente(erro.causa, erro.dica or DICA_INSTANCIA) from erro
    typer.echo(relatorio.formatar())
    return 0 if relatorio.sucesso else 1


def _configuracao_open_notebook(contexto: Contexto) -> ConfiguracaoOpenNotebook:
    try:
        return ler_configuracao(contexto.config_global)
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(
            str(erro), f'corrija a seção [open_notebook] de {contexto.config_global}'
        ) from erro


def _aviso_open_notebook(url: str, configuracao: ConfiguracaoOpenNotebook) -> str:
    rotulo = (
        'o nome (slug) do candidato'
        if configuracao.incluir_nome
        else 'um pseudônimo (candidato 1, candidato 2…)'
    )
    return '\n'.join(
        [
            f'O open-notebook em {url} vai receber, a cada análise:',
            f'- por concurso: {", ".join(ARTEFATOS_DO_CONCURSO)} e uma nota de resumo;',
            f'- no consolidado: {", ".join(Path(a).name for a in ARTEFATOS_DO_CONSOLIDADO)} e uma nota de resumo.',
            f'O candidato aparece como {rotulo}; CPF e inscrição não são enviados.',
            'Se a instância usa um provedor de IA externo, o chat dela manda esse conteúdo para ele.',
            f'A senha, se houver, vem da variável {configuracao.variavel_chave}, nunca do config.toml.',
        ]
    )


def _candidatos_da_execucao(contexto: Contexto, todos: bool) -> list[str | None]:
    if not todos:
        return [_escolher_candidato(contexto)]
    candidatos = candidatos_existentes(contexto.provas)
    if not candidatos:
        raise ErroDoUsuario(
            'nenhum candidato encontrado em provas/<concurso>/candidatos/',
            'acrescente um com `concurso-analise add <arquivo> --candidate <nome> --concurso <pasta>`',
        )
    return list(candidatos)


def _sincronizar_notebooks(
    contexto: Contexto,
    configuracao: ConfiguracaoOpenNotebook,
    candidatos: list[str | None],
    concurso: str | None,
) -> RelatorioSincronizacao:
    cliente = ClienteOpenNotebook.da_configuracao(configuracao, contexto.home)
    cliente.saude()
    cliente.listar_notebooks()
    sincronizador = Sincronizador(
        cliente, EstadoSincronizacao.ler(contexto.projeto / ARQUIVO_ESTADO), embed=configuracao.embed
    )
    limiar = configuracao_do_projeto(contexto).limiar_topico_baixo
    fontes = _fontes_de_estudo(contexto)
    caderno = _caderno_de_erros(contexto, candidatos)
    try:
        for candidato in candidatos:
            sincronizar_candidato(
                sincronizador,
                contexto.provas,
                contexto.analises / candidato if candidato else contexto.analises,
                candidato,
                limiar=limiar,
                arquivo_taxonomia=contexto.taxonomia,
                incluir_nome=configuracao.incluir_nome,
                concurso=concurso,
                fontes=fontes,
                caderno_de_erros=caderno.get(candidato),
            )
    finally:
        sincronizador.gravar_estado()
    return sincronizador.relatorio


def _caderno_de_erros(contexto: Contexto, candidatos: list[str | None]) -> dict[str | None, dict[str, str]]:
    """Os erros do TEC só vão ao open-notebook com `[pratica] open_notebook = true`, e para o dono da prática."""
    configuracao = _configuracao_pratica(contexto)
    if configuracao is None or not configuracao.open_notebook:
        return {}
    dono = configuracao.candidato or (candidatos[0] if len(candidatos) == 1 else None)
    if dono not in candidatos:
        return {}
    taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else {}
    lido = ler_pratica(configuracao.entrada, contexto.projeto / ARQUIVO_ESCOLHAS, taxonomia)
    return {dono: textos_do_caderno(lido)} if lido.pratica.erros else {}


def _fontes_de_estudo(contexto: Contexto) -> FontesDeEstudo:
    try:
        return ler_fontes_de_estudo(
            contexto.projeto, contexto.raiz, contexto.taxonomia, contexto.config_global
        )
    except ConfiguracaoInvalidaError as erro:
        raise ErroDoUsuario(
            str(erro), 'corrija o .concurso/biblioteca.yaml ou a seção [legislacao] e rode de novo'
        ) from erro


def _recomendar(
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
    busca = _busca_na_biblioteca(opcoes, fontes) if fontes.mapa is not None else None
    resultado = recomendar(
        fracos, limiar, fontes.mapa, fontes.repositorio, busca, avisos, textos_pratica or []
    )
    return gravar_recomendacoes(destino, resultado)


def _busca_na_biblioteca(opcoes: Opcoes, fontes: FontesDeEstudo) -> BuscaBiblioteca | None:
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


def _sincronizar_depois_da_analise(opcoes: Opcoes, candidatos: list[str | None]) -> None:
    """Uma falha aqui vira aviso: a análise já terminou e o código de saída é dela."""
    if opcoes.dry_run or not opcoes.rede:
        return
    contexto = opcoes.contexto
    try:
        configuracao = ler_configuracao(contexto.config_global)
    except ConfiguracaoInvalidaError as erro:
        logger.warning('open-notebook: %s; a sincronização foi pulada', erro)
        return
    if not configuracao.ativa:
        return
    try:
        relatorio = _sincronizar_notebooks(contexto, configuracao, candidatos, None)
    except OpenNotebookIndisponivelError as erro:
        logger.warning(
            'open-notebook: %s; a sincronização foi pulada (%s)', erro.causa, erro.dica or DICA_INSTANCIA
        )
        return
    except Exception as erro:  # noqa: BLE001 - nenhuma falha da integração derruba a análise
        logger.warning('open-notebook: falha inesperada na sincronização: %s', erro)
        logger.debug('open-notebook: detalhe da falha', exc_info=True)
        return
    logger.info('open-notebook: %s', relatorio.formatar().replace('\n', '; '))
    for falha in relatorio.falhas:
        logger.warning('open-notebook: %s', falha)


def _onboarding(opcoes: Opcoes, doctor: bool | None = None, extras: dict[str, str] | None = None) -> int:
    contexto = opcoes.contexto
    com_terminal = onboarding.interativo(opcoes.sim)
    if not com_terminal:
        _exigir_provas(contexto.provas)
    ambiente = {**os.environ, **(extras or {})}
    if doctor is not None:
        ambiente[onboarding.VARIAVEL_DOCTOR] = 's' if doctor else 'n'
    try:
        respostas = onboarding.perguntar(
            contexto, set(opcoes.fornecidos), InteracaoConsole() if com_terminal else None, ambiente
        )
    except onboarding.OnboardingCanceladoError:
        raise ErroDoUsuario(
            'onboarding cancelado; nada foi gravado', 'rode `concurso-analise init` quando quiser'
        ) from None
    except CalibracaoError as erro:
        raise ErroDoUsuario(f'calibração reprovada, nada foi gravado: {erro.causa}', erro.dica) from erro
    except onboarding.ProvedorInvalidoError as erro:
        raise ErroDoUsuario(
            f'{erro}; nada foi gravado', f'corrija {onboarding.VARIAVEL_LLM} ou apague a variável'
        ) from erro
    if respostas.calibracao is not None:
        opcoes = replace(opcoes, forcar=True)
    opcoes = replace(opcoes, contexto=onboarding.aplicar(contexto, respostas))
    if opcoes.contexto.provas.is_dir():
        opcoes = _migrar(opcoes)
    onboarding.gravar(contexto, respostas)
    contexto = opcoes.contexto
    if respostas.doctor:
        _diagnosticar(contexto)
    if contexto.provas.is_dir() and not listar_concursos(contexto.provas):
        typer.echo(
            f'nenhum concurso em {contexto.provas} ainda; siga o {onboarding.ARQUIVO_LEIA_ME} '
            'e rode `concurso-analise` de novo'
        )
        return 0
    return _analisar(opcoes)


def _diagnosticar(contexto: Contexto) -> list[diagnostico.Item]:
    itens = diagnostico.diagnosticar(
        [contexto.provas, contexto.analises, contexto.projeto, contexto.home], contexto.home
    )
    typer.echo(diagnostico.formatar(itens))
    return itens


def _analisar(opcoes: Opcoes, concurso: str | None = None, reaproveitar: bool = False) -> int:
    _exigir_provas(opcoes.contexto.provas)
    opcoes = _migrar(opcoes)
    contexto = opcoes.contexto
    if reaproveitar:
        _reaproveitar_csv(opcoes, concurso)
    if not opcoes.todos:
        candidato = _escolher_candidato(contexto)
        sucesso = _analisar_candidato(opcoes, _cliente_llm(opcoes), candidato, concurso)
        _sincronizar_depois_da_analise(opcoes, [candidato])
        return 0 if sucesso else 1
    candidatos = _candidatos_da_execucao(contexto, todos=True)
    cliente_llm = _cliente_llm(opcoes)
    sucessos = [_analisar_candidato(opcoes, cliente_llm, candidato, concurso) for candidato in candidatos]
    if not opcoes.dry_run:
        comparar_candidatos(contexto.analises, candidatos)
    _sincronizar_depois_da_analise(opcoes, candidatos)
    return 0 if all(sucessos) else 1


def _cliente_llm(opcoes: Opcoes) -> ClienteLlm | None:
    if opcoes.dry_run:
        return None
    cliente = cliente_configurado(opcoes.contexto.home, opcoes.contexto.config_global, opcoes.llm)
    return ClienteComMemoria(cliente) if cliente else None


def _analisar_candidato(
    opcoes: Opcoes, cliente_llm: ClienteLlm | None, candidato: str | None, concurso: str | None
) -> bool:
    contexto = opcoes.contexto
    provas, analises = _curto(contexto.provas, contexto.raiz), _curto(contexto.analises, contexto.raiz)
    destino = analises / candidato if candidato else analises
    if opcoes.dry_run:
        prefixo = f'{candidato}/' if candidato else ''
        for nome, acao in planejar(provas, destino, opcoes.forcar, concurso, candidato):
            typer.echo(f'{prefixo}{nome}: {acao}')
        _praticar(opcoes, candidato, destino, None)
        return True
    if candidato:
        completar_perfis(contexto.provas, candidato)
        if not opcoes.todos:
            _lembrar_candidato(contexto, candidato)
    configuracao = replace(configuracao_do_projeto(contexto), cliente_llm=cliente_llm)
    taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else None
    fontes = _fontes_de_estudo(contexto)
    antes = _manifestos(destino)
    sucesso = analisar_todos(provas, destino, opcoes.forcar, concurso, configuracao, taxonomia, candidato)
    pratica = _praticar(opcoes, candidato, destino, configuracao)
    textos = textos_para_normas(pratica) if pratica is not None else []
    recomendacoes = _recomendar(opcoes, fontes, provas, destino, configuracao.limiar_topico_baixo, textos)
    indice = destino / relatorio_html.ARQUIVO_INDICE
    mudou_pratica = pratica is not None and pratica.mudou
    if recomendacoes or mudou_pratica or _manifestos(destino) != antes or not indice.exists():
        relatorio_html.gerar_relatorio_html(
            provas, destino, contexto.taxonomia, configuracao.limiar_topico_baixo
        )
        if opcoes.abrir:
            relatorio_html.abrir_no_navegador(contexto.raiz / indice)
    typer.echo(f'relatório: {contexto.raiz / indice}')
    return sucesso


def _manifestos(destino: Path) -> dict[str, int]:
    """Quando cada concurso foi analisado pela última vez; o manifesto só é regravado numa análise."""
    return {p.parent.name: p.stat().st_mtime_ns for p in destino.glob(f'*/{ARQUIVO_MANIFESTO}')}


def _reaproveitar_csv(opcoes: Opcoes, concurso: str | None) -> None:
    contexto = opcoes.contexto
    if concurso is None or opcoes.todos:
        raise ErroDoUsuario(
            '--reuse-csv vale para um concurso e um candidato por vez',
            'rode `concurso-analise analyze <concurso> --reuse-csv --candidate <nome>`',
        )
    candidato = _escolher_candidato(contexto)
    if candidato is None:
        raise ErroDoUsuario(
            '--reuse-csv precisa de um candidato, e este projeto não tem nenhum',
            'acrescente as respostas com `concurso-analise add <folha> --candidate <nome> --concurso <pasta>`',
        )
    csv = contexto.analises / candidato / concurso / ARQUIVO_RESPOSTAS
    if not csv.exists():
        raise ErroDoUsuario(
            f'{csv}: CSV de leitura da folha não encontrado',
            f'rode `concurso-analise analyze {concurso}` para ler a folha, corrija o CSV e rode de novo '
            'com --reuse-csv',
        )
    status = avaliar(contexto.provas / concurso, candidato)
    if status.config is None:
        raise ErroDoUsuario(
            f'{concurso}: {"; ".join(status.motivos)}', 'corrija o concurso.yaml e rode de novo'
        )
    if opcoes.dry_run:
        typer.echo(f'copiaria {csv} para {pasta_do_candidato(contexto.provas / concurso, candidato)}')
        return
    try:
        destino = gravar_revisao(status.config, candidato, csv)
    except RespostasInvalidasError as erro:
        raise ErroDoUsuario(str(erro), f'corrija o {csv} e rode de novo com --reuse-csv') from erro
    typer.echo(f'revisão copiada para {destino}; ela vence a folha a partir de agora')


def _migrar(opcoes: Opcoes) -> Opcoes:
    """Passa para o layout multi-candidato o que estiver no formato das fases 1 a 3."""
    contexto = opcoes.contexto
    try:
        migracao = planejar_migracao(contexto)
        if migracao.vazia:
            return opcoes
        if opcoes.dry_run:
            for operacao in migracao.operacoes(contexto):
                typer.echo(operacao)
            return opcoes
        executar_migracao(migracao, contexto)
    except MigracaoError as erro:
        raise ErroDoAmbiente(
            str(erro), 'resolva o problema e rode de novo; a migração recomeça do zero'
        ) from erro
    return replace(opcoes, contexto=replace(contexto, candidato=migracao.candidato))


def _com_candidato(contexto: Contexto, candidato: str | None) -> Contexto:
    return replace(contexto, candidato=slug(candidato)) if candidato else contexto


def _pasta_do_candidato(contexto: Contexto) -> Path:
    candidato = _escolher_candidato(contexto)
    return contexto.analises / candidato if candidato else contexto.analises


def _escolher_candidato(contexto: Contexto) -> str | None:
    """O escolhido, o último usado ou o único; sem nenhum, o layout das fases 1 a 3."""
    if contexto.candidato:
        return contexto.candidato
    existentes = candidatos_existentes(contexto.provas)
    if len(existentes) <= 1:
        return existentes[0] if existentes else None
    raise ErroDoUsuario(
        f'há mais de um candidato ({", ".join(existentes)}) e nenhum foi escolhido',
        'rode com --candidate <nome> ou com --all-candidates',
    )


def _lembrar_candidato(contexto: Contexto, candidato: str) -> None:
    if ler_toml(contexto.config_projeto).get('candidato', {}).get('ultimo') != candidato:
        gravar_no_config_projeto(contexto, 'candidato', {'ultimo': candidato})


def _concurso_do_arquivo(raiz_provas: Path, arquivo: Path, concurso: str | None) -> Path:
    if concurso:
        pasta = raiz_provas / concurso
        if not pasta.is_dir():
            raise ErroDoUsuario(
                f'concurso não encontrado: {pasta}', 'use o nome de uma pasta em provas/ no --concurso'
            )
        return pasta
    absoluto, raiz = arquivo.resolve(), raiz_provas.resolve()
    if absoluto.is_relative_to(raiz) and len(absoluto.relative_to(raiz).parts) > 1:
        return raiz_provas / absoluto.relative_to(raiz).parts[0]
    pastas = listar_concursos(raiz_provas)
    if len(pastas) == 1:
        return pastas[0]
    raise ErroDoUsuario(
        'não dá para saber a qual concurso o arquivo pertence', 'rode de novo com --concurso <pasta>'
    )


def _curto(caminho: Path, raiz: Path) -> Path:
    """Relativo à pasta atual quando está dentro dela, para os relatórios não citarem a pasta do usuário."""
    return caminho.relative_to(raiz) if caminho.is_relative_to(raiz) else caminho


def _exigir_provas(raiz_provas: Path) -> None:
    if not raiz_provas.is_dir():
        raise ErroDoUsuario(
            f'pasta de provas não encontrada: {raiz_provas}',
            'crie uma subpasta por concurso (ex.: provas/meu_concurso/) ou indique outra pasta com --provas',
        )
