import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated

import typer

from concursos.analytics.taxonomia import carregar_taxonomia
from concursos.assistente import InteracaoAutomatica, InteracaoConsole
from concursos.cadastro import cadastrar
from concursos.candidatos import (
    adicionar_arquivo,
    candidatos_existentes,
    completar_perfis,
    gravar_perfil_global,
    slug,
)
from concursos.cli.erros import ErroDoUsuario, ajustar_nivel_console
from concursos.config.contexto import Contexto, gravar_no_config_projeto, ler_toml, resolver_contexto
from concursos.configuracao import configuracao_do_projeto
from concursos.consolidado import comparar_candidatos
from concursos.pipeline import analisar_todos, planejar
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


Forcar = Annotated[bool, typer.Option('--force', help='reprocessa mesmo sem mudanças')]
DryRun = Annotated[bool, typer.Option('--dry-run', help='mostra o que seria feito, sem gravar nada')]
Candidato = Annotated[
    str | None, typer.Option('--candidate', help='candidato (padrão: o último usado neste projeto)')
]
Todos = Annotated[
    bool, typer.Option('--all-candidates', help='analisa todos os candidatos e gera o comparativo entre eles')
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
    ctx.obj = Opcoes(contexto, sim=sim, dry_run=dry_run, forcar=forcar, todos=todos)
    if ctx.invoked_subcommand is None:
        return _analisar(ctx.obj)
    return None


@app.command('analyze', help='analisa os concursos que mudaram (ou só o indicado)')
def analyze(
    ctx: typer.Context,
    concurso: Annotated[str | None, typer.Argument(help='nome da pasta do concurso')] = None,
    forcar: Forcar = False,
    dry_run: DryRun = False,
    candidato: Candidato = None,
    todos: Todos = False,
) -> int:
    opcoes = replace(
        ctx.obj,
        forcar=ctx.obj.forcar or forcar,
        dry_run=ctx.obj.dry_run or dry_run,
        todos=ctx.obj.todos or todos,
    )
    if candidato:
        opcoes = replace(opcoes, contexto=replace(opcoes.contexto, candidato=slug(candidato)))
    return _analisar(opcoes, concurso)


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
        interacao = InteracaoAutomatica() if opcoes.sim else InteracaoConsole()
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


def _analisar(opcoes: Opcoes, concurso: str | None = None) -> int:
    contexto = opcoes.contexto
    _exigir_provas(contexto.provas)
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
    configuracao = configuracao_do_projeto(contexto)
    taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else None
    return analisar_todos(provas, destino, opcoes.forcar, concurso, configuracao, taxonomia, candidato)


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
