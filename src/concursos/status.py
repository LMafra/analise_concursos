from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from concursos.concurso_config import ConcursoConfig, ConfiguracaoInvalidaError, carregar_concurso
from concursos.folha import TEMPLATES


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


def avaliar(pasta: Path) -> StatusConcurso:
    try:
        config = carregar_concurso(pasta)
    except ConfiguracaoInvalidaError as erro:
        return StatusConcurso(pasta.name, Situacao.DESATUALIZADO, (str(erro),), '-', None)

    motivos = [
        f'{config.caminho(prova.gabarito.arquivo)}: arquivo ausente (gabarito da prova {prova.chave})'
        for prova in config.provas
        if not config.caminho(prova.gabarito.arquivo).exists()
    ]
    if config.respostas_arquivo is not None:
        if not config.caminho(config.respostas_arquivo).exists():
            motivos.append(f'{config.caminho(config.respostas_arquivo)}: arquivo ausente (respostas)')
    elif config.folha is not None:
        if not config.caminho(config.folha.arquivo).exists():
            motivos.append(f'{config.caminho(config.folha.arquivo)}: arquivo ausente (folha de resposta)')
        elif config.folha.template not in TEMPLATES:
            motivos.append(
                f'{config.folha.arquivo}: leitura do template {config.folha.template!r} ainda não disponível'
            )
    else:
        motivos.append('respostas não configuradas (folha de resposta ou respostas.txt)')
    if config.edital is not None:
        documentos = [*config.edital.documentos, *([config.edital.manual] if config.edital.manual else [])]
        motivos += [
            f'{config.caminho(arquivo)}: arquivo ausente (edital)'
            for arquivo in documentos
            if not config.caminho(arquivo).exists()
        ]

    situacao = Situacao.INCOMPLETO if motivos else Situacao.COMPLETO
    return StatusConcurso(config.nome, situacao, tuple(motivos), _status_gabarito(config), config)


def _status_gabarito(config: ConcursoConfig) -> str:
    estados = {prova.gabarito.status for prova in config.provas}
    return estados.pop() if len(estados) == 1 else 'misto'


def formatar_tabela(status: list[StatusConcurso]) -> str:
    largura = max([len('concurso'), *(len(s.nome) for s in status)])
    linhas = [f'{"concurso":<{largura}}  {"situacao":<13}  {"gabarito":<10}  motivo', '-' * (largura + 40)]
    for item in status:
        motivo = '; '.join(item.motivos) or '-'
        linhas.append(f'{item.nome:<{largura}}  {item.situacao:<13}  {item.gabarito:<10}  {motivo}')
    return '\n'.join(linhas)
