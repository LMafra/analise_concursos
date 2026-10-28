from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from concursos.atualizacao import Troca, verificar
from concursos.candidatos import aplicar_candidato
from concursos.concurso_config import (
    ARQUIVO_CONFIG,
    ConcursoConfig,
    ConfiguracaoInvalidaError,
    carregar_concurso,
)
from concursos.perfis import ids_de_ocr

_PAPEIS_OPCIONAIS = ('caderno', 'resultado oficial')


class Situacao(StrEnum):
    COMPLETO = 'completo'
    INCOMPLETO = 'incompleto'
    DESATUALIZADO = 'desatualizado'


@dataclass(frozen=True)
class StatusConcurso:
    nome: str
    situacao: Situacao
    motivos: tuple[str, ...]
    gabarito: str
    config: ConcursoConfig | None
    trocas: tuple[Troca, ...] = ()


def listar_concursos(raiz_provas: Path) -> list[Path]:
    """Subpastas de provas/, cadastradas ou não (as não cadastradas aparecem como incompletas)."""
    return sorted(p for p in raiz_provas.iterdir() if p.is_dir() and not p.name.startswith('.'))


def avaliar(pasta: Path, candidato: str | None = None) -> StatusConcurso:
    """Sem candidato, as respostas vêm do `concurso.yaml` (layout das fases 1 a 3)."""
    if not (pasta / ARQUIVO_CONFIG).exists():
        motivo = f'{ARQUIVO_CONFIG} ausente; rode `concurso-analise add {pasta}`'
        return StatusConcurso(pasta.name, Situacao.INCOMPLETO, (motivo,), '-', None)
    try:
        config = carregar_concurso(pasta)
        if candidato is not None:
            config = aplicar_candidato(config, candidato)
    except ConfiguracaoInvalidaError as erro:
        return StatusConcurso(pasta.name, Situacao.DESATUALIZADO, (str(erro),), '-', None)

    ausentes = {
        arquivo: papel
        for arquivo, papel in config.arquivos_referenciados.items()
        if not config.caminho(arquivo).exists()
    }
    motivos = [
        f'{config.caminho(arquivo)}: arquivo ausente ({papel})'
        for arquivo, papel in ausentes.items()
        if not papel.startswith(_PAPEIS_OPCIONAIS)
    ]
    if config.respostas_arquivo is None and config.folha is None:
        motivos.append('respostas não configuradas (folha de resposta ou respostas.txt)')
    elif (
        config.folha is not None
        and config.folha.arquivo not in ausentes
        and config.folha.template is not None
        and config.folha.template not in ids_de_ocr()
    ):
        motivos.append(
            f'{config.folha.arquivo}: leitura do template {config.folha.template!r} ainda não disponível'
        )

    if motivos:
        return StatusConcurso(
            config.nome, Situacao.INCOMPLETO, tuple(motivos), config.status_gabarito, config
        )
    pendencias = verificar(config)
    if pendencias.motivos:
        return StatusConcurso(
            config.nome, Situacao.DESATUALIZADO, pendencias.motivos, config.status_gabarito, config
        )
    avisos = tuple(
        f'{t.novo}: gabarito definitivo será aplicado na próxima análise' for t in pendencias.trocas
    )
    return StatusConcurso(
        config.nome, Situacao.COMPLETO, avisos, config.status_gabarito, config, pendencias.trocas
    )


def formatar_tabela(status: list[StatusConcurso]) -> str:
    largura = max([len('concurso'), *(len(s.nome) for s in status)])
    linhas = [f'{"concurso":<{largura}}  {"situacao":<13}  {"gabarito":<10}  motivo', '-' * (largura + 40)]
    for item in status:
        motivo = '; '.join(item.motivos) or '-'
        linhas.append(f'{item.nome:<{largura}}  {item.situacao:<13}  {item.gabarito:<10}  {motivo}')
    return '\n'.join(linhas)
