"""O `edital_a_confirmar.yaml`: os campos que nenhuma camada do edital preencheu, para o usuário completar.

O arquivo nunca é reescrito: depois de criado, só ganha no fim os campos que passarem a faltar. O que o
usuário preenche é lido por `concurso_config.carregar_concurso` como se estivesse no `concurso.yaml`."""

import logging
from pathlib import Path

import yaml

from concursos.analytics.correcao import ConfiguracaoCorrecao, FonteCorrecao
from concursos.analytics.regras_edital import FONTES_DO_TEXTO, Campo, EscopoCorte, FonteRegra, RegrasEdital
from concursos.concurso_config import ARQUIVO_CONFIRMACAO, CAMPOS_CONFIRMAVEIS, ConcursoConfig
from concursos.modelo import Formato

logger = logging.getLogger(__name__)

_EXPLICACOES = {
    'data_prova': 'data da prova objetiva (AAAA-MM-DD)',
    'alternativas': 'número de alternativas por questão (2 a 10)',
    'fator_penalidade': (
        'quantos acertos cada erro anula: 0 se o erro não desconta, 1 na Cebraspe, 0.25 se 4 erros anulam 1 acerto'
    ),
    'nota_corte': 'nota mínima no conjunto das provas objetivas, em pontos (vazio se o edital não tem)',
}
_CABECALHO = """\
# Campos do edital que a análise não encontrou. Preencha os que souber e rode `concurso-analise` de novo: os
# valores preenchidos valem como se estivessem no concurso.yaml (fonte `config`), para todos os candidatos.
# Este arquivo nunca é sobrescrito; campos que passarem a faltar são acrescentados no fim.
#
"""


def campos_faltantes(regras: RegrasEdital, correcoes: list[ConfiguracaoCorrecao]) -> list[str]:
    correcao = correcoes[0]
    faltantes = {
        'data_prova': correcao.data_prova is None,
        'alternativas': regras.prova.formato.valor == Formato.MULTIPLA_ESCOLHA
        and regras.prova.alternativas.fonte is FonteRegra.DEFAULT,
        'fator_penalidade': correcao.fonte is FonteCorrecao.DEFAULT,
        'nota_corte': not any(
            c.unidade.calculavel and c.escopo is not EscopoCorte.DISCURSIVA for c in regras.cortes
        ),
    }
    return [campo for campo in CAMPOS_CONFIRMAVEIS if faltantes[campo]]


def gravar_confirmacao(
    config: ConcursoConfig, regras: RegrasEdital, correcoes: list[ConfiguracaoCorrecao]
) -> Path | None:
    """Cria o arquivo com os campos que faltam ou acrescenta os que ainda não estão nele."""
    faltantes = campos_faltantes(regras, correcoes)
    caminho = config.caminho(ARQUIVO_CONFIRMACAO)
    if not faltantes:
        return None
    if caminho.exists():
        texto = caminho.read_text(encoding='utf-8')
        novos = [campo for campo in faltantes if campo not in (yaml.safe_load(texto) or {})]
        if not novos:
            return caminho
        separador = '' if texto.endswith('\n') or not texto else '\n'
        caminho.write_text(texto + separador + ''.join(_bloco(c) for c in novos), encoding='utf-8')
    else:
        novos = faltantes
        caminho.write_text(
            _CABECALHO + _extraidos(regras) + ''.join(_bloco(c) for c in novos), encoding='utf-8'
        )
    logger.warning(
        '%s: o edital não traz %s; preencha %s e rode de novo',
        config.nome,
        ', '.join(novos),
        caminho,
    )
    return caminho


def _bloco(campo: str) -> str:
    return f'# {_EXPLICACOES[campo]}\n{campo}:\n'


def _extraidos(regras: RegrasEdital) -> str:
    campos: list[tuple[str, Campo]] = [
        ('formato', regras.prova.formato),
        ('alternativas', regras.prova.alternativas),
        ('fator de penalidade', regras.prova.penalidade),
        ('data da prova objetiva', regras.cronograma.objetiva),
        ('total de questões', regras.distribuicao.total),
        *((f'corte {c.escopo} ({c.unidade})', c) for c in regras.cortes),
    ]
    linhas = [
        f'#   {nome}: {campo.valor} ({campo.documento_origem}, p. {campo.pagina_origem})'
        for nome, campo in campos
        if campo.fonte in FONTES_DO_TEXTO
    ]
    if not linhas:
        return '# Nada foi extraído do edital (modo mínimo).\n#\n'
    return '# Extraído do edital, só para conferência:\n' + '\n'.join(linhas) + '\n#\n'
