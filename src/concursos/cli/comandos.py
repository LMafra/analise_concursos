import json
import logging
import os
import shutil
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from typing import Annotated

import typer

from concursos import doctor as diagnostico
from concursos import onboarding, relatorio_html
from concursos.aplicacao import analise, cadastro, integracoes, projeto
from concursos.aplicacao.inicio import executar_onboarding
from concursos.aplicacao.opcoes import Opcoes
from concursos.assistente import InteracaoConsole
from concursos.candidatos import slug
from concursos.cli.erros import CODIGO_AMBIENTE, ErroDoAmbiente, ErroDoUsuario, ajustar_nivel_console
from concursos.config.contexto import (
    VARIAVEL_ANALISES,
    VARIAVEL_CANDIDATO,
    VARIAVEL_PROVAS,
    resolver_contexto,
)
from concursos.exportacao import FormatoExportacao
from concursos.integracoes import pci_mcp
from concursos.integracoes.pci_mcp import REGIOES
from concursos.integracoes.simulado_pci import formatar_provas
from concursos.integracoes.sincronizacao_pci import como_json
from concursos.integracoes.sincronizacao_pci import formatar_tabela as tabela_pci
from concursos.status import formatar_tabela

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
pci_app = typer.Typer(
    help='integração opcional com o PCI Concursos: provas anteriores e liga/desliga',
    no_args_is_help=True,
    rich_markup_mode=None,
)
app.add_typer(pci_app, name='pci')


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
    bool,
    typer.Option('--offline', help='nenhuma chamada de rede (desliga o LLM, o open-notebook e o PCI)'),
]
Refresh = Annotated[bool, typer.Option('--refresh', help='consulta o PCI de novo, ignorando o cache')]
ComoJson = Annotated[bool, typer.Option('--json', help='imprime o resultado em JSON')]


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
        saida=typer.echo,
        interacao=InteracaoConsole() if onboarding.interativo(sim) else None,
    )
    if ctx.invoked_subcommand is None:
        if onboarding.precisa_de_onboarding(contexto) and not dry_run:
            return executar_onboarding(ctx.obj)
        return analise.analisar(ctx.obj)
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
    return executar_onboarding(opcoes, doctor, ambiente)


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
    opcoes = replace(opcoes, contexto=projeto.com_candidato(opcoes.contexto, candidato))
    return analise.analisar(opcoes, concurso, reaproveitar)


@app.command('report', help='reabre o último relatório HTML')
def report(ctx: typer.Context, candidato: Candidato = None) -> int:
    indice = analise.relatorio(projeto.com_candidato(ctx.obj.contexto, candidato))
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
    destino = analise.exportar(projeto.com_candidato(ctx.obj.contexto, candidato), formato)
    typer.echo(f'consolidado exportado para {destino}')
    return 0


@app.command('add', help='cadastra a pasta de um concurso ou acrescenta as respostas de um candidato')
def add(
    ctx: typer.Context,
    caminho: Annotated[Path, typer.Argument(help='pasta do concurso, ou arquivo de respostas ou folha')],
    candidato: Candidato = None,
    concurso: Annotated[str | None, typer.Option('--concurso', help='pasta do concurso em provas/')] = None,
    pci: Annotated[
        int | None,
        typer.Option('--pci', help='id de um concurso registrado com `discover --register`, para vincular'),
    ] = None,
) -> int:
    opcoes: Opcoes = ctx.obj
    if pci is not None and not caminho.is_dir():
        raise ErroDoUsuario(
            '--pci vale para a pasta de um concurso', f'rode `concurso-analise add <pasta> --pci {pci}`'
        )
    if caminho.is_dir():
        return cadastro.cadastrar_pasta(opcoes, caminho, pci)
    cadastro.adicionar_respostas(opcoes, caminho, candidato, concurso)
    return 0


@app.command('discover', help='busca no PCI Concursos os concursos com inscrições abertas ou prestes a abrir')
def discover(
    ctx: typer.Context,
    cargos: Annotated[
        list[str] | None,
        typer.Option('--cargo', help='cargo (repita para mais de um); padrão: os do candidato'),
    ] = None,
    uf: Annotated[str | None, typer.Option('--uf', help='sigla do estado, ex.: sp')] = None,
    cidade: Annotated[str | None, typer.Option('--cidade', help='cidade (exige --uf)')] = None,
    regiao: Annotated[str | None, typer.Option('--regiao', help=f'região: {", ".join(REGIOES)}')] = None,
    termo: Annotated[str | None, typer.Option('--termo', help='título, órgão ou cargo')] = None,
    professores: Annotated[bool, typer.Option('--professores', help='só concursos para professores')] = False,
    refresh: Refresh = False,
    json_: ComoJson = False,
    registrar: Annotated[
        int | None, typer.Option('--register', help='acompanha o concurso (pelo id) no radar de prazos')
    ] = None,
    esquecer: Annotated[
        int | None, typer.Option('--forget', help='deixa de acompanhar o concurso (pelo id)')
    ] = None,
    candidato: Candidato = None,
) -> int:
    opcoes: Opcoes = ctx.obj
    opcoes = replace(opcoes, contexto=projeto.com_candidato(opcoes.contexto, candidato))
    integracoes.configuracao_pci(opcoes.contexto)
    if esquecer is not None:
        integracoes.esquecer_interesse(opcoes, esquecer)
        return 0
    concursos = integracoes.descobrir(opcoes, cargos, uf, cidade, regiao, termo, professores, refresh)
    typer.echo(como_json(concursos) if json_ else tabela_pci(concursos))
    if registrar is not None:
        integracoes.registrar_interesse(opcoes, concursos, registrar)
    return 0


@pci_app.command('enable', help='liga a integração com o PCI Concursos, depois de mostrar o que é enviado')
def pci_enable(
    ctx: typer.Context,
    url: Annotated[
        str | None, typer.Option('--url', help=f'endereço do MCP (padrão: {pci_mcp.URL_PADRAO})')
    ] = None,
) -> int:
    opcoes: Opcoes = ctx.obj
    configuracao = integracoes.configuracao_pci(opcoes.contexto)
    url = url or configuracao.url
    typer.echo(integracoes.aviso_pci(url, configuracao))
    if opcoes.dry_run:
        typer.echo(f'ligaria a integração com {url}')
        return 0
    if not opcoes.sim:
        if not onboarding.interativo(False):
            raise ErroDoUsuario(
                'ligar o PCI exige confirmação, e não há terminal para perguntar',
                'confirme com `concurso-analise --yes pci enable`',
            )
        if not typer.confirm('ligar a integração com o PCI?', default=False):
            typer.echo('nada foi gravado')
            return 0
    integracoes.ligar_pci(opcoes.contexto, url)
    typer.echo(f'PCI ligado: {url}; experimente `concurso-analise discover --cargo <cargo> --uf <uf>`')
    return 0


@pci_app.command('disable', help='desliga a integração (a configuração continua gravada)')
def pci_disable(ctx: typer.Context) -> int:
    opcoes: Opcoes = ctx.obj
    integracoes.configuracao_pci(opcoes.contexto)
    if opcoes.dry_run:
        typer.echo('desligaria a integração com o PCI')
        return 0
    integracoes.desligar_pci(opcoes.contexto)
    typer.echo('PCI desligado')
    return 0


@pci_app.command('provas', help='provas anteriores no PCI; com --download, importa uma como simulado')
def pci_provas(
    ctx: typer.Context,
    concurso: Annotated[
        str | None, typer.Argument(help='concurso-alvo (pasta em provas/): dá o cargo, a banca e o edital')
    ] = None,
    termos: Annotated[
        list[str] | None, typer.Option('--termo', help='palavras da busca, ex.: "auditor receita" (repita)')
    ] = None,
    baixar: Annotated[
        int | None, typer.Option('--download', help='id da prova: abre a página e importa o que você baixar')
    ] = None,
    refresh: Refresh = False,
    json_: ComoJson = False,
    candidato: Candidato = None,
) -> int:
    opcoes: Opcoes = ctx.obj
    opcoes = replace(opcoes, contexto=projeto.com_candidato(opcoes.contexto, candidato))
    resultado = integracoes.provas_anteriores(opcoes, concurso, termos, refresh)
    if json_:
        typer.echo(json.dumps([asdict(p) for p in resultado.provas], ensure_ascii=False, indent=2))
    else:
        typer.echo(formatar_provas(resultado.provas))
    if baixar is not None:
        return integracoes.importar_simulado(opcoes, resultado.provas, baixar, resultado.alvo)
    return 0


@app.command('status', help='mostra a situação de cada concurso')
def status(
    ctx: typer.Context,
    provas: Annotated[
        Path | None, typer.Option('--provas', help='pasta com uma subpasta por concurso')
    ] = None,
) -> int:
    contexto = ctx.obj.contexto
    typer.echo(formatar_tabela(analise.situacoes(provas or contexto.provas)))
    for linha in integracoes.linhas_do_radar(contexto):
        typer.echo(linha)
    return 0


@app.command('doctor', help='verifica o ambiente e diz como corrigir o que falta')
def doctor(ctx: typer.Context) -> int:
    itens = projeto.diagnosticar(ctx.obj.contexto)
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
    configuracao = integracoes.configuracao_open_notebook(opcoes.contexto)
    url = url or configuracao.url
    typer.echo(integracoes.aviso_open_notebook(url, configuracao))
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
    integracoes.ligar_open_notebook(opcoes.contexto, url)
    typer.echo(f'open-notebook ligado: {url}; rode `concurso-analise notebook sync` para enviar agora')
    return 0


@notebook_app.command('disable', help='desliga a sincronização (a configuração continua gravada)')
def notebook_disable(ctx: typer.Context) -> int:
    opcoes: Opcoes = ctx.obj
    integracoes.configuracao_open_notebook(opcoes.contexto)
    if opcoes.dry_run:
        typer.echo('desligaria a sincronização com o open-notebook')
        return 0
    integracoes.desligar_open_notebook(opcoes.contexto)
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
    opcoes = replace(opcoes, contexto=projeto.com_candidato(opcoes.contexto, candidato))
    return analise.importar_pratica_e_analisar(opcoes, arquivo)


@notebook_app.command('sync', help='envia as análises para o open-notebook e mostra o resumo')
def notebook_sync(
    ctx: typer.Context,
    concurso: Annotated[str | None, typer.Option('--concurso', help='só este concurso')] = None,
    candidato: Candidato = None,
    todos: Todos = False,
) -> int:
    opcoes: Opcoes = ctx.obj
    opcoes = replace(opcoes, contexto=projeto.com_candidato(opcoes.contexto, candidato))
    relatorio = integracoes.sincronizar(opcoes, concurso, todos)
    if relatorio is None:
        return 0
    typer.echo(relatorio.formatar())
    return 0 if relatorio.sucesso else 1
