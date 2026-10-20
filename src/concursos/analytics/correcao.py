"""Modelo de correção do edital: extração por regex, resolução por precedência e aplicação às questões."""

import bisect
import json
import logging
import re
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path

import pandas as pd

from concursos.concurso_config import ConcursoConfig, CorrecaoConfig
from concursos.modelo import Formato, ModeloCorrecao, Resultado

logger = logging.getLogger(__name__)

ARQUIVO_CORRECAO = 'correcao.json'
CONFIANCA_PENALIDADE_COM_ACERTO = 0.95
CONFIANCA_PENALIDADE_SEM_ACERTO = 0.7
CONFIANCA_BRUTA = 0.9
CONFIANCA_CONFIG = 1.0


class FonteCorrecao(StrEnum):
    EDITAL = 'edital'
    CONFIG = 'config'
    DEFAULT = 'default'


@dataclass(frozen=True)
class ConfiguracaoCorrecao:
    modelo: ModeloCorrecao = ModeloCorrecao.BRUTA
    fator_penalidade: float = 0.0
    nota_maxima: float | None = None
    nota_corte: float | None = None
    fonte: FonteCorrecao = FonteCorrecao.DEFAULT
    confianca: float = 0.0
    trecho_origem: str | None = None
    documento_origem: str | None = None
    pagina_origem: int | None = None
    variante: str | None = None


@dataclass(frozen=True)
class NotaCorrigida:
    """`itens` são as questões com a pontuação nas três versões (NaN nas anuladas, que não medem
    conhecimento); `nota` é a nota do concurso pela regra do edital, com anulada valendo ponto."""

    itens: pd.DataFrame
    nota: float


def aplicar_correcao(questoes: pd.DataFrame, cfg: ConfiguracaoCorrecao, formato: Formato) -> NotaCorrigida:
    """Pontuação de cada item: bruta (acerto vale 1), corrigida pela regra do edital e ajustada ao acaso
    (erro vale -1/(k-1), com k alternativas)."""
    acerto = (questoes['resultado'] == Resultado.ACERTO).astype(float)
    erro = (questoes['resultado'] == Resultado.ERRO).astype(float)
    anulada = questoes['anulada'].astype(bool)
    k = len(formato.alternativas)
    corrigida = acerto - cfg.fator_penalidade * erro
    itens = questoes.assign(
        pontos_bruta=acerto.mask(anulada),
        pontos_corrigida=corrigida.mask(anulada),
        pontos_ajustada=(acerto - erro / (k - 1)).mask(anulada),
    )
    return NotaCorrigida(itens, float(corrigida.where(~anulada, 1.0).sum()))


def nota_normalizada(nota: float, cfg: ConfiguracaoCorrecao) -> float:
    """Nota na escala 0–100 da nota máxima, truncada em 0."""
    return max(0.0, nota / cfg.nota_maxima * 100)


_NUMERO = r'\d+(?:,\d+)?'
_PENALIDADE = re.compile(
    rf'(?:(?P<acerto>{_NUMERO})\s*pontos?,?\s+caso\s+a\s+resposta[^;]{{0,200}}?concordância[^;]{{0,200}};\s*)?'
    rf'(?P<erro>{_NUMERO})\s*pontos?\s+negativos?',
    re.IGNORECASE,
)
_BRUTA = re.compile(
    r'igual\s+ao\s+total\s+de\s+acertos|valendo\s+1\s*(?:\(um\)\s*)?ponto\s+cada\s+questão', re.IGNORECASE
)
_MENCAO_PENALIDADE = re.compile(
    r'pontos?\s+negativos?|desconto\s+de|descontad[oa]\b'
    r'|anula(?:rá|m|-se)?\s+(?:um|uma|1)\s+(?:\(uma?\)\s+)?(?:acerto|certa|questão\s+certa|resposta\s+certa)',
    re.IGNORECASE,
)
_NOTA_MAXIMA = (
    re.compile(rf'prova\s+objetiva\s+totalizará\s+(?P<valor>{_NUMERO})\s*(?:\([^)]*\)\s*)?pontos', re.I),
)
_NOTA_CORTE = (
    re.compile(
        rf'nota\s+inferior\s+a\s+(?P<valor>{_NUMERO})\s*pontos\s+no\s+conjunto\s+das\s+provas\s+objetivas',
        re.I,
    ),
    re.compile(rf'nota\s+inferior\s+a\s+(?P<valor>{_NUMERO})\s*pontos\s+na\s+prova\s+objetiva\s+P\b', re.I),
)
_FIM_DE_FRASE = re.compile(r'\.(?:\s|$)')
_TAMANHO_MAXIMO_TRECHO = 600
_RECUO_MAXIMO_TRECHO = 300


@dataclass(frozen=True)
class _TextoCorrido:
    """Páginas com espaços normalizados e unidas, para casar regras que atravessam quebras de linha e de página."""

    texto: str
    inicios: tuple[int, ...]

    @classmethod
    def de(cls, paginas: list[str]) -> '_TextoCorrido':
        normalizadas = [' '.join(pagina.split()) for pagina in paginas]
        inicios, posicao = [], 0
        for pagina in normalizadas:
            inicios.append(posicao)
            posicao += len(pagina) + 1
        return cls(' '.join(normalizadas), tuple(inicios))

    def pagina(self, posicao: int) -> int:
        return bisect.bisect_right(self.inicios, posicao)

    def trecho(self, match: re.Match) -> str:
        """A frase inteira que contém a regra, incluindo o número do subitem que a precede."""
        inicio = match.start()
        inicio_pagina = self.inicios[self.pagina(inicio) - 1]
        recuo = max(inicio_pagina, inicio - _RECUO_MAXIMO_TRECHO)
        if (anterior := self.texto.rfind('. ', recuo, inicio)) >= 0:
            inicio = anterior + 2
        elif recuo == inicio_pagina:
            inicio = inicio_pagina
        fim = _FIM_DE_FRASE.search(self.texto, match.end())
        limite = inicio + _TAMANHO_MAXIMO_TRECHO
        return self.texto[inicio : min(fim.end() if fim else limite, limite)].strip()


def extrair_fator_correcao(paginas: list[str]) -> ConfiguracaoCorrecao | None:
    """Regra de correção da prova objetiva lida do texto do edital; None quando nenhum padrão casa."""
    texto = _TextoCorrido.de(paginas)
    if match := _PENALIDADE.search(texto.texto):
        acerto = _numero(match['acerto']) if match['acerto'] else 1.0
        confianca = CONFIANCA_PENALIDADE_COM_ACERTO if match['acerto'] else CONFIANCA_PENALIDADE_SEM_ACERTO
        modelo, fator = ModeloCorrecao.LIQUIDA, _numero(match['erro']) / acerto
    elif (match := _BRUTA.search(texto.texto)) and not _MENCAO_PENALIDADE.search(texto.texto):
        modelo, fator, confianca = ModeloCorrecao.BRUTA, 0.0, CONFIANCA_BRUTA
    else:
        return None
    return ConfiguracaoCorrecao(
        modelo=modelo,
        fator_penalidade=fator,
        nota_maxima=_valor_do_primeiro_padrao(texto, _NOTA_MAXIMA),
        nota_corte=_valor_do_primeiro_padrao(texto, _NOTA_CORTE),
        fonte=FonteCorrecao.EDITAL,
        confianca=confianca,
        trecho_origem=texto.trecho(match),
        pagina_origem=texto.pagina(match.start()),
    )


def mencao_penalidade(paginas: list[str]) -> bool:
    """O texto fala em descontar pontos por erro? "Anulação" e "descontos" soltos não contam."""
    return _MENCAO_PENALIDADE.search(_TextoCorrido.de(paginas).texto) is not None


def resolver_correcao(config: ConcursoConfig, documentos: dict[str, list[str]]) -> list[ConfiguracaoCorrecao]:
    """Regra de correção do concurso, com precedência edital, depois configuração, depois default.

    `documentos` mapeia cada documento do edital às suas páginas, na ordem de leitura (anexos primeiro).
    Campos que a fonte vencedora não define (nota máxima, nota de corte) são completados pelas seguintes;
    sem nota máxima declarada, ela é o número de itens do concurso.
    """
    declarada = config.correcao or CorrecaoConfig()
    extraida = _extrair_dos_documentos(documentos)
    if extraida is not None:
        _avisar_divergencia_da_configuracao(config.nome, extraida, declarada)
        cfg = extraida
    elif declarada.define_regra:
        fator = declarada.fator_penalidade or 0.0
        cfg = ConfiguracaoCorrecao(
            ModeloCorrecao.pelo_fator(fator), fator, fonte=FonteCorrecao.CONFIG, confianca=CONFIANCA_CONFIG
        )
    else:
        cfg = ConfiguracaoCorrecao()
        _avisar_default(config.nome, documentos)
    cfg = replace(
        cfg,
        nota_maxima=_primeiro_definido(cfg.nota_maxima, declarada.nota_maxima, float(config.total_itens)),
        nota_corte=_primeiro_definido(cfg.nota_corte, declarada.nota_corte),
    )
    if cfg.fonte is not FonteCorrecao.DEFAULT:
        _avisar_contradicao_com_pontuacao(config, cfg)
    return [cfg]


def gravar_correcao(configuracoes: list[ConfiguracaoCorrecao], destino: Path) -> None:
    conteudo = json.dumps([asdict(cfg) for cfg in configuracoes], indent=2, ensure_ascii=False)
    (destino / ARQUIVO_CORRECAO).write_text(conteudo, encoding='utf-8')


def _extrair_dos_documentos(documentos: dict[str, list[str]]) -> ConfiguracaoCorrecao | None:
    for documento, paginas in documentos.items():
        if (cfg := extrair_fator_correcao(paginas)) is not None:
            return replace(cfg, documento_origem=documento)
    return None


def _avisar_default(nome: str, documentos: dict[str, list[str]]) -> None:
    if any(mencao_penalidade(paginas) for paginas in documentos.values()):
        logger.warning(
            '%s: regra de correção não reconhecida, mas o edital menciona penalidade por erro; '
            'usando o default (bruta, fator 0). Confira o edital e declare o bloco correcao no concurso.yaml',
            nome,
        )
    else:
        logger.warning(
            '%s: regra de correção não encontrada no edital nem no concurso.yaml; usando o default (bruta, fator 0)',
            nome,
        )


def _avisar_divergencia_da_configuracao(
    nome: str, extraida: ConfiguracaoCorrecao, declarada: CorrecaoConfig
) -> None:
    if declarada.fator_penalidade is not None and declarada.fator_penalidade != extraida.fator_penalidade:
        logger.warning(
            '%s: correcao.fator_penalidade declarado (%g) difere do edital (%g); vale o edital',
            nome,
            declarada.fator_penalidade,
            extraida.fator_penalidade,
        )


def _avisar_contradicao_com_pontuacao(config: ConcursoConfig, cfg: ConfiguracaoCorrecao) -> None:
    if cfg.fator_penalidade != config.pontuacao.fator_penalidade:
        logger.warning(
            "%s: pontuacao '%s' declarada no concurso.yaml contradiz a regra de correção "
            '(%s, fator %g, fonte %s); a nota_liquida dos CSVs segue a pontuacao declarada',
            config.nome,
            config.pontuacao.value,
            cfg.modelo.value,
            cfg.fator_penalidade,
            cfg.fonte.value,
        )


def _primeiro_definido(*valores: float | None) -> float | None:
    return next((v for v in valores if v is not None), None)


def _valor_do_primeiro_padrao(texto: _TextoCorrido, padroes: tuple[re.Pattern, ...]) -> float | None:
    for padrao in padroes:
        if match := padrao.search(texto.texto):
            return _numero(match['valor'])
    return None


def _numero(valor: str) -> float:
    return float(valor.replace(',', '.'))
