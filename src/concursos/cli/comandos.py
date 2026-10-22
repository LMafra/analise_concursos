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
from concursos.cadastro import cadastrar
from concursos.calibracao import CalibracaoError
from concursos.candidatos import (
    adicionar_arquivo,
    candidatos_existentes,
    completar_perfis,
    gravar_perfil_global,
    gravar_revisao,
    slug,
)
from concursos.cli.erros import CODIGO_AMBIENTE, ErroDoAmbiente, ErroDoUsuario, ajustar_nivel_console
from concursos.config.contexto import (
    VARIAVEL_ANALISES,
    VARIAVEL_CANDIDATO,
    VARIAVEL_PROVAS,
    Contexto,
    gravar_no_config_projeto,
    ler_toml,
    resolver_contexto,
)
from concursos.configuracao import configuracao_do_projeto
from concursos.consolidado import comparar_candidatos
from concursos.exportacao import FormatoExportacao, exportar_consolidado
from concursos.llm import cliente_configurado
from concursos.manifesto import ARQUIVO_MANIFESTO
from concursos.migracao import MigracaoError, executar_migracao, planejar_migracao
from concursos.pipeline import ARQUIVO_RESPOSTAS, analisar_todos, planejar
from concursos.respostas import RespostasInvalidasError
from concursos.status import avaliar, formatar_tabela, listar_concursos

app = typer.Typer(
    name='concurso-analise',
    help='Correção e análise de provas de concurso. Sem subcomando, analisa o que mudou.',
    add_completion=False,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
)


@dataclass(frozen=True)
class Opcoes:
    contexto: Contexto
    sim: bool = False
    dry_run: bool = False
    forcar: bool = False
    todos: bool = False
    abrir: bool = True
    llm: bool = True
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
Offline = Annotated[bool, typer.Option('--offline', help='nenhuma chamada de rede (desliga o LLM)')]


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
    if candidato:
        opcoes = replace(opcoes, contexto=replace(opcoes.contexto, candidato=slug(candidato)))
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
        typer.echo(f'copiaria {caminho} para {pasta / "candidatos" / slug(nome)}')
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
    contexto: Contexto = ctx.obj.contexto
    itens = diagnostico.diagnosticar(
        [contexto.provas, contexto.analises, contexto.projeto, contexto.home], contexto.home
    )
    typer.echo(diagnostico.formatar(itens))
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
        itens = diagnostico.diagnosticar(
            [contexto.provas, contexto.analises, contexto.projeto, contexto.home], contexto.home
        )
        typer.echo(diagnostico.formatar(itens))
    if contexto.provas.is_dir() and not listar_concursos(contexto.provas):
        typer.echo(
            f'nenhum concurso em {contexto.provas} ainda; siga o {onboarding.ARQUIVO_LEIA_ME} '
            'e rode `concurso-analise` de novo'
        )
        return 0
    return _analisar(opcoes)


def _analisar(opcoes: Opcoes, concurso: str | None = None, reaproveitar: bool = False) -> int:
    _exigir_provas(opcoes.contexto.provas)
    opcoes = _migrar(opcoes)
    contexto = opcoes.contexto
    if reaproveitar:
        _reaproveitar_csv(opcoes, concurso)
    if not opcoes.todos:
        return 0 if _analisar_candidato(opcoes, _escolher_candidato(contexto), concurso) else 1
    candidatos = candidatos_existentes(contexto.provas)
    if not candidatos:
        raise ErroDoUsuario(
            'nenhum candidato encontrado em provas/<concurso>/candidatos/',
            'acrescente um com `concurso-analise add <arquivo> --candidate <nome> --concurso <pasta>`',
        )
    sucessos = [_analisar_candidato(opcoes, candidato, concurso) for candidato in candidatos]
    if not opcoes.dry_run:
        comparar_candidatos(contexto.analises, candidatos)
    return 0 if all(sucessos) else 1


def _analisar_candidato(opcoes: Opcoes, candidato: str | None, concurso: str | None) -> bool:
    contexto = opcoes.contexto
    provas, analises = _curto(contexto.provas, contexto.raiz), _curto(contexto.analises, contexto.raiz)
    destino = analises / candidato if candidato else analises
    if opcoes.dry_run:
        prefixo = f'{candidato}/' if candidato else ''
        for nome, acao in planejar(provas, destino, opcoes.forcar, concurso, candidato):
            typer.echo(f'{prefixo}{nome}: {acao}')
        return True
    if candidato:
        completar_perfis(contexto.provas, candidato)
        if not opcoes.todos:
            _lembrar_candidato(contexto, candidato)
    configuracao = replace(
        configuracao_do_projeto(contexto),
        cliente_llm=cliente_configurado(contexto.home, contexto.config_global, opcoes.llm),
    )
    taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else None
    antes = _manifestos(destino)
    sucesso = analisar_todos(provas, destino, opcoes.forcar, concurso, configuracao, taxonomia, candidato)
    indice = destino / relatorio_html.ARQUIVO_INDICE
    if _manifestos(destino) != antes or not indice.exists():
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
        typer.echo(f'copiaria {csv} para {contexto.provas / concurso / "candidatos" / candidato}')
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
