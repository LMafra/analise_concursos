import logging
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated

import typer

from concursos.analytics.taxonomia import carregar_taxonomia
from concursos.cli.erros import ErroDoUsuario, ajustar_nivel_console
from concursos.config.contexto import Contexto, resolver_contexto
from concursos.configuracao import configuracao_do_projeto
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


Forcar = Annotated[bool, typer.Option('--force', help='reprocessa mesmo sem mudanças')]
DryRun = Annotated[bool, typer.Option('--dry-run', help='mostra o que seria feito, sem gravar nada')]


@app.callback(invoke_without_command=True)
def principal(
    ctx: typer.Context,
    sim: Annotated[bool, typer.Option('--yes', '-y', help='aceita os padrões sem perguntar')] = False,
    quieto: Annotated[bool, typer.Option('--quiet', '-q', help='só avisos e erros')] = False,
    detalhado: Annotated[bool, typer.Option('--verbose', '-v', help='log detalhado')] = False,
    dry_run: DryRun = False,
    forcar: Forcar = False,
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
    contexto = resolver_contexto(data_dir=data_dir, provas=provas, analises=analises)
    ctx.obj = Opcoes(contexto, sim=sim, dry_run=dry_run, forcar=forcar)
    if ctx.invoked_subcommand is None:
        return _analisar(ctx.obj)
    return None


@app.command('analyze', help='analisa os concursos que mudaram (ou só o indicado)')
def analyze(
    ctx: typer.Context,
    concurso: Annotated[str | None, typer.Argument(help='nome da pasta do concurso')] = None,
    forcar: Forcar = False,
    dry_run: DryRun = False,
) -> int:
    opcoes = replace(ctx.obj, forcar=ctx.obj.forcar or forcar, dry_run=ctx.obj.dry_run or dry_run)
    return _analisar(opcoes, concurso)


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
    provas, analises = _curto(contexto.provas, contexto.raiz), _curto(contexto.analises, contexto.raiz)
    if opcoes.dry_run:
        for nome, acao in planejar(provas, analises, opcoes.forcar, concurso):
            typer.echo(f'{nome}: {acao}')
        return 0
    configuracao = configuracao_do_projeto(contexto)
    taxonomia = carregar_taxonomia(contexto.taxonomia) if contexto.taxonomia.exists() else None
    sucesso = analisar_todos(provas, analises, opcoes.forcar, concurso, configuracao, taxonomia)
    return 0 if sucesso else 1


def _curto(caminho: Path, raiz: Path) -> Path:
    """Relativo à pasta atual quando está dentro dela, para os relatórios não citarem a pasta do usuário."""
    return caminho.relative_to(raiz) if caminho.is_relative_to(raiz) else caminho


def _exigir_provas(raiz_provas: Path) -> None:
    if not raiz_provas.is_dir():
        raise ErroDoUsuario(
            f'pasta de provas não encontrada: {raiz_provas}',
            'crie uma subpasta por concurso (ex.: provas/meu_concurso/) ou indique outra pasta com --provas',
        )
