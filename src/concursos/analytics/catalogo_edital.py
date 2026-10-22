"""Catálogo de descobertas do edital: um markdown por concurso, gerado do registro de candidatos e das regras
extraídas."""

from pathlib import Path

from concursos.analytics.candidatos_edital import (
    CANDIDATOS,
    DESCARTADOS_SEM_CANDIDATO,
    Impacto,
    StatusCandidato,
)
from concursos.analytics.regras_edital import Metadado, RegrasEdital, StatusExtracao
from concursos.concurso_config import ConcursoConfig

ARQUIVO_CATALOGO = 'catalogo_edital.md'
_TAMANHO_DO_VALOR = 80
_TAMANHO_DO_TRECHO = 160
_NO_EDITAL = {
    StatusExtracao.ENCONTRADO: 'encontrado',
    StatusExtracao.NAO_ENCONTRADO: 'não encontrado',
    StatusExtracao.AMBIGUO: 'ambíguo',
}


def gerar_catalogo(config: ConcursoConfig, regras: RegrasEdital) -> str:
    identificacao = regras.identificacao
    titulo = identificacao.nome_oficial.valor or config.nome
    if cargo := identificacao.cargo.valor or config.cargo:
        titulo += f', {cargo}'
    if especialidade := identificacao.especialidade.valor:
        titulo += f' – {especialidade}'
    metadados = {m.chave: m for m in regras.metadados}
    linhas = [
        f'# Catálogo do edital: {titulo}',
        '',
        f'Concurso `{config.nome}`; registro de candidatos na versão {regras.versao_candidatos}. '
        '"(descoberta)" marca o que veio além da lista inicial de candidatos.',
        '',
        '## Descobertas',
        '',
        '| Informação | Valor | Trecho de origem | Uso no projeto | Impacto | Status | No edital |',
        '|---|---|---|---|---|---|---|',
    ]
    for candidato in CANDIDATOS:
        metadado = metadados.get(candidato.chave)
        informacao = candidato.informacao + ('' if candidato.conhecido else ' (descoberta)')
        celulas = [
            informacao,
            _valor(metadado),
            _trecho(metadado),
            candidato.uso,
            candidato.impacto,
            candidato.status,
            _no_edital(metadado, candidato.severidade_se_ausente),
        ]
        linhas.append('| ' + ' | '.join(_celula(c) for c in celulas) + ' |')
    linhas += ['', '## Propostas de evolução', '']
    propostas = [c for c in CANDIDATOS if c.proposta and c.impacto is Impacto.ALTO]
    linhas += [f'- **{c.informacao}** ({c.status}): {c.proposta}' for c in propostas] or ['Nenhuma.']
    linhas += ['', '## Descartados', '']
    descartados = [
        (c.informacao, c.motivo_do_descarte) for c in CANDIDATOS if c.status is StatusCandidato.DESCARTADO
    ]
    linhas += [
        f'- **{informacao}**: {motivo}' for informacao, motivo in [*descartados, *DESCARTADOS_SEM_CANDIDATO]
    ]
    return '\n'.join(linhas) + '\n'


def gravar_catalogo(config: ConcursoConfig, regras: RegrasEdital, destino: Path) -> None:
    (destino / ARQUIVO_CATALOGO).write_text(gerar_catalogo(config, regras), encoding='utf-8')


def _valor(metadado: Metadado | None) -> str:
    if metadado is None or metadado.valor is None:
        return '–'
    return _encurtar(texto_do_valor(metadado.valor), _TAMANHO_DO_VALOR)


def texto_do_valor(valor: object) -> str:
    """Valor de metadado para leitura: lista separada por "; " e float sem ".0"."""
    if isinstance(valor, list):
        return '; '.join(map(texto_do_valor, valor))
    return f'{valor:g}' if isinstance(valor, float) else str(valor)


def _trecho(metadado: Metadado | None) -> str:
    if metadado is None or not metadado.trecho_origem:
        return '–'
    trecho = _encurtar(metadado.trecho_origem, _TAMANHO_DO_TRECHO)
    return f'«{trecho}» (p. {metadado.pagina_origem}, {metadado.documento_origem})'


def _no_edital(metadado: Metadado | None, severidade_se_ausente: str) -> str:
    status = metadado.status if metadado else StatusExtracao.NAO_ENCONTRADO
    rotulo = _NO_EDITAL[status]
    return f'{rotulo} ({severidade_se_ausente})' if status is StatusExtracao.NAO_ENCONTRADO else rotulo


def _encurtar(texto: str, tamanho: int) -> str:
    texto = ' '.join(texto.split())
    return texto if len(texto) <= tamanho else texto[: tamanho - 1] + '…'


def _celula(texto: str) -> str:
    return str(texto).replace('|', '\\|')
