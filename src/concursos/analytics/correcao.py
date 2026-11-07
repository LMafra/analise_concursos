"""Modelo de correção do edital: extração por regex, resolução por precedência e aplicação às questões."""

import bisect
import json
import logging
import re
from dataclasses import asdict, dataclass, replace
from datetime import date
from enum import StrEnum
from pathlib import Path

import pandas as pd

from concursos.concurso_config import (
    ConcursoConfig,
    CorrecaoConfig,
    PesoItens,
    VarianteCorrecaoConfig,
    peso_da_questao,
    pesos_variam,
)
from concursos.correcao import ARQUIVO_QUESTOES
from concursos.erros import avisar
from concursos.modelo import Formato, ModeloCorrecao, Resultado
from concursos.perfis import PERFIL_GENERICO, perfil_da_banca
from concursos.resultado_oficial import formatar
from concursos.texto import NUMERO_DECIMAL, numero_decimal

logger = logging.getLogger(__name__)

ARQUIVO_CORRECAO = 'correcao.json'
CONFIANCA_PENALIDADE_COM_ACERTO = 0.95
CONFIANCA_PENALIDADE_SEM_ACERTO = 0.7
CONFIANCA_PENALIDADE_FRACIONARIA = 0.9
CONFIANCA_PONTOS_POR_PARTE = 0.85
CONFIANCA_QUADRO_DE_PESOS = 0.9
CONFIANCA_BRUTA = 0.9
CONFIANCA_CONFIG = 1.0
CONFIANCA_PERFIL = 0.5


class FonteCorrecao(StrEnum):
    EDITAL = 'edital'
    CONFIG = 'config'
    PERFIL = 'perfil'
    DEFAULT = 'default'


@dataclass(frozen=True)
class ConfiguracaoCorrecao:
    modelo: ModeloCorrecao = ModeloCorrecao.BRUTA
    fator_penalidade: float = 0.0
    pesos: tuple[PesoItens, ...] = ()
    nota_maxima: float | None = None
    nota_corte: float | None = None
    fonte: FonteCorrecao = FonteCorrecao.DEFAULT
    confianca: float = 0.0
    trecho_origem: str | None = None
    documento_origem: str | None = None
    pagina_origem: int | None = None
    variante: str | None = None
    data_prova: date | None = None
    fonte_data: FonteCorrecao | None = None

    def peso_de(self, questao: int) -> float:
        return peso_da_questao(self.pesos, questao)


@dataclass(frozen=True)
class NotaCorrigida:
    """`itens` são as questões com o peso e a pontuação nas três versões (NaN nas anuladas, que não medem
    conhecimento); `nota` é a nota do concurso pela regra do edital, ponderada e com anulada valendo ponto."""

    itens: pd.DataFrame
    nota: float


def aplicar_correcao(
    questoes: pd.DataFrame, cfg: ConfiguracaoCorrecao, formato: Formato, alternativas: int | None = None
) -> NotaCorrigida:
    """Pontuação de cada item: bruta (acerto vale 1), corrigida pela regra do edital e ajustada ao acaso
    (erro vale -1/(k-1), com k alternativas). O peso entra só na nota, para que percentuais de disciplinas
    com pesos diferentes continuem comparáveis."""
    acerto = (questoes['resultado'] == Resultado.ACERTO).astype(float)
    erro = (questoes['resultado'] == Resultado.ERRO).astype(float)
    anulada = questoes['anulada'].astype(bool)
    peso = questoes['questao'].map(cfg.peso_de).astype(float)
    k = len(formato.letras(alternativas))
    corrigida = acerto - cfg.fator_penalidade * erro
    itens = questoes.assign(
        peso=peso,
        pontos_bruta=acerto.mask(anulada),
        pontos_corrigida=corrigida.mask(anulada),
        pontos_ajustada=(acerto - erro / (k - 1)).mask(anulada),
    )
    return NotaCorrigida(itens, float((peso * corrigida.where(~anulada, 1.0)).sum()))


def nota_normalizada(nota: float, nota_maxima: float) -> float:
    """Nota na escala 0–100 da nota máxima, truncada em 0."""
    return max(0.0, nota / nota_maxima * 100)


@dataclass(frozen=True)
class NotaFinal:
    nota: float
    nota_maxima: float
    nota_corte: float | None = None
    variante: str | None = None

    @property
    def texto(self) -> str:
        texto = f'{formatar(self.nota)} de {formatar(self.nota_maxima)} pontos'
        if self.nota_corte is None:
            return texto
        situacao = 'atinge o corte' if self.nota >= self.nota_corte else 'abaixo do corte'
        return f'{texto}, nota de corte {formatar(self.nota_corte)} ({situacao})'

    @property
    def rotulado(self) -> str:
        return f'{self.variante}: {self.texto}' if self.variante else self.texto

    @property
    def percentual(self) -> float:
        return round(100 * self.nota / self.nota_maxima, 2) if self.nota_maxima else 0.0


def notas_finais(
    questoes: pd.DataFrame, configuracoes: list[ConfiguracaoCorrecao], formato: Formato
) -> list[NotaFinal]:
    """Uma por variante, só nas regras em que a nota difere da contagem de acertos (desconto por erro ou
    pesos)."""
    return [
        NotaFinal(
            aplicar_correcao(questoes, cfg, formato).nota, cfg.nota_maxima, cfg.nota_corte, cfg.variante
        )
        for cfg in configuracoes
        if cfg.modelo is not ModeloCorrecao.BRUTA
    ]


def notas_pela_regra(
    questoes: pd.DataFrame, configuracoes: list[ConfiguracaoCorrecao], formato: Formato
) -> list[NotaFinal]:
    """Uma por variante, inclusive na bruta, sobre a soma dos pesos das questões: o percentual que a regra da
    banca dá (no Cebraspe, 35 acertos e 15 erros em 50 itens valem 40%)."""
    return [
        NotaFinal(
            aplicar_correcao(questoes, cfg, formato).nota,
            float(questoes['questao'].map(cfg.peso_de).sum()),
            cfg.nota_corte,
            cfg.variante,
        )
        for cfg in configuracoes
    ]


def notas_finais_gravadas(pasta: Path, formato: Formato) -> list[NotaFinal]:
    """As notas finais de um concurso já analisado, a partir do `questoes.csv` e do `correcao.json`."""
    if not (pasta / ARQUIVO_CORRECAO).exists():
        return []
    return notas_finais(_questoes_gravadas(pasta), ler_correcao(pasta), formato)


def notas_pela_regra_gravadas(pasta: Path, formato: Formato) -> list[NotaFinal]:
    if not (pasta / ARQUIVO_CORRECAO).exists():
        return []
    return notas_pela_regra(_questoes_gravadas(pasta), ler_correcao(pasta), formato)


def _questoes_gravadas(pasta: Path) -> pd.DataFrame:
    return pd.read_csv(pasta / ARQUIVO_QUESTOES, usecols=['questao', 'resultado', 'anulada'])


_POR_EXTENSO = r'(?:\([^)]*\)\s*)?'
_PENALIDADE = re.compile(
    rf'(?:(?P<acerto>{NUMERO_DECIMAL})\s*pontos?,?\s+caso\s+a\s+resposta[^;]{{0,200}}?concordância[^;]{{0,200}};\s*)?'
    rf'(?P<erro>{NUMERO_DECIMAL})\s*pontos?\s+negativos?',
    re.IGNORECASE,
)
_PENALIDADE_FRACIONARIA = re.compile(
    rf'a\s+cada\s+(?P<erros>[1-9]\d*)\s*{_POR_EXTENSO}(?:questões\s+|respostas\s+|itens\s+)?(?:errad|incorret)[oa]s'
    r'[^.]{0,40}?anula(?:-se|rá|m)?\s+(?:uma?|1)\s+(?:\(uma?\)\s+)?(?:questão\s+|resposta\s+)?(?:certa|correta|acerto)',
    re.IGNORECASE,
)
_PONTOS_POR_PARTE = (
    re.compile(
        rf'(?P<gerais>{NUMERO_DECIMAL})\s*pontos?,?\s+caso\s+a\s+resposta[^;]{{0,200}}?concordância'
        rf'[^;]{{0,120}}?conhecimentos\s+(?:básicos|gerais)[^;]*;\s*'
        rf'(?P<especificos>{NUMERO_DECIMAL})\s*pontos?,?\s+caso\s+a\s+resposta[^;]{{0,200}}?concordância'
        r'[^;]{0,120}?específicos',
        re.IGNORECASE,
    ),
    re.compile(
        rf'valer(?:á|ão)\s+(?P<gerais>{NUMERO_DECIMAL})\s*{_POR_EXTENSO}pontos?\s+no\s+módulo\s+de\s+conhecimentos\s+'
        rf'(?:básicos|gerais),?\s+e\s+(?P<especificos>{NUMERO_DECIMAL})\s*{_POR_EXTENSO}pontos?\s+no\s+módulo\s+de\s+'
        r'conhecimentos\s+específicos',
        re.IGNORECASE,
    ),
)
_BRUTA = re.compile(
    r'igual\s+ao\s+total\s+de\s+acertos|valendo\s+1\s*(?:\(um\)\s*)?ponto\s+cada\s+questão'
    r'|cada\s+acerto\s+valerá\s+1\s*(?:\(um\)\s*)?ponto',
    re.IGNORECASE,
)
_ERRO_VALE_ZERO = re.compile(
    r';\s*0,00\s*ponto,?\s+caso\s+a\s+resposta[^;]{0,120}?discordância', re.IGNORECASE
)
_MENCAO_PENALIDADE = re.compile(
    r'pontos?\s+negativos?|desconto\s+de|descontad[oa]\b'
    r'|anula(?:rá|m|-se)?\s+(?:um|uma|1)\s+(?:\(uma?\)\s+)?(?:acerto|certa|questão\s+certa|resposta\s+certa)',
    re.IGNORECASE,
)
_NOTA_MAXIMA = (
    re.compile(rf'prova\s+objetiva\s+totalizará\s+(?P<valor>{NUMERO_DECIMAL})\s*{_POR_EXTENSO}pontos', re.I),
    re.compile(
        rf'provas\s+objetivas,?[^.]{{0,80}}?valerão\s+(?P<valor>{NUMERO_DECIMAL})\s*{_POR_EXTENSO}pontos',
        re.I,
    ),
    re.compile(rf'sendo\s+(?P<valor>{NUMERO_DECIMAL})\s*{_POR_EXTENSO}pontos\s+a\s+pontuação\s+máxima', re.I),
)
_QUESTOES_GERAIS = re.compile(rf'(?P<valor>\d+)\s*{_POR_EXTENSO}questões\s+de\s+conhecimentos\s+gerais', re.I)
_EIXOS_TEMATICOS = re.compile(
    rf'(?P<eixos>\d+)\s*{_POR_EXTENSO}eixos\s+temáticos,?\s+cada\s+um\s+contendo\s+(?P<itens>\d+)', re.I
)
_CODIGO_DE_CARGO = r'[A-Z]\d+-\d{2}-[A-Z]'
_MESES = {
    nome: numero
    for numero, nomes in enumerate(
        [
            ('janeiro',),
            ('fevereiro',),
            ('março', 'marco'),
            ('abril',),
            ('maio',),
            ('junho',),
            ('julho',),
            ('agosto',),
            ('setembro',),
            ('outubro',),
            ('novembro',),
            ('dezembro',),
        ],
        start=1,
    )
    for nome in nomes
}
_DATA_NO_CRONOGRAMA = re.compile(
    r'aplicação\s+d[ao]s?\s+provas?\s+objetivas?(?:\s+e\s+(?:da\s+)?discursivas?)?\.?\s+'
    r'(?P<dia>\d{1,2})/(?P<mes>\d{1,2})/(?P<ano>\d{4})',
    re.IGNORECASE,
)
_DATA_POR_EXTENSO = re.compile(
    r'prova\s+objetiva[^.]{0,200}?ser(?:á|ão)\s+realizad[ao]s?[^.]{0,80}?\bno\s+dia\s+'
    rf'(?P<dia>\d{{1,2}})\s+de\s+(?P<mes>{"|".join(_MESES)})\s+de\s+(?P<ano>\d{{4}})',
    re.IGNORECASE,
)
_NOTA_CORTE = (
    re.compile(
        rf'nota\s+inferior\s+a\s+(?P<valor>{NUMERO_DECIMAL})\s*pontos\s+no\s+conjunto\s+das\s+provas\s+objetivas',
        re.I,
    ),
    re.compile(
        rf'nota\s+inferior\s+a\s+(?P<valor>{NUMERO_DECIMAL})\s*pontos\s+na\s+prova\s+objetiva\s+P\b', re.I
    ),
)
_FIM_DE_FRASE = re.compile(r'\.(?:\s|$)')
_TAMANHO_MAXIMO_TRECHO = 600
_RECUO_MAXIMO_TRECHO = 300


@dataclass(frozen=True)
class TextoCorrido:
    """Páginas com espaços normalizados e unidas, para casar regras que atravessam quebras de linha e de página."""

    texto: str
    inicios: tuple[int, ...]

    @classmethod
    def de(cls, paginas: list[str]) -> 'TextoCorrido':
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


def extrair_fator_correcao(paginas: list[str], total_itens: int | None = None) -> ConfiguracaoCorrecao | None:
    """Regra de correção da prova objetiva lida do texto do edital; None quando nenhum padrão casa.

    Pontos diferentes por prova ou módulo só viram pesos quando `total_itens` e a nota máxima permitem
    deduzir quantos itens tem cada parte.
    """
    texto = TextoCorrido.de(paginas)
    nota_maxima = _valor_do_primeiro_padrao(texto, _NOTA_MAXIMA)
    pesos: tuple[PesoItens, ...] = ()
    if match := _PENALIDADE.search(texto.texto):
        acerto = numero_decimal(match['acerto']) if match['acerto'] else 1.0
        confianca = CONFIANCA_PENALIDADE_COM_ACERTO if match['acerto'] else CONFIANCA_PENALIDADE_SEM_ACERTO
        fator = numero_decimal(match['erro']) / acerto
    elif match := _PENALIDADE_FRACIONARIA.search(texto.texto):
        fator, confianca = 1 / int(match['erros']), CONFIANCA_PENALIDADE_FRACIONARIA
    elif (match := _primeiro_match(texto, _PONTOS_POR_PARTE)) and (
        pesos := _pesos_por_parte(match, total_itens, nota_maxima)
    ):
        fator, confianca = 0.0, CONFIANCA_PONTOS_POR_PARTE
    elif (
        (match := _BRUTA.search(texto.texto))
        and not _MENCAO_PENALIDADE.search(texto.texto)
        or (match := _ERRO_VALE_ZERO.search(texto.texto))
    ):
        fator, confianca = 0.0, CONFIANCA_BRUTA
    else:
        return None
    return ConfiguracaoCorrecao(
        modelo=ModeloCorrecao.pelo_fator(fator, ponderada=pesos_variam(pesos)),
        fator_penalidade=fator,
        pesos=pesos,
        nota_maxima=nota_maxima,
        nota_corte=_valor_do_primeiro_padrao(texto, _NOTA_CORTE),
        fonte=FonteCorrecao.EDITAL,
        confianca=confianca,
        trecho_origem=texto.trecho(match),
        pagina_origem=texto.pagina(match.start()),
    )


def extrair_data_prova(paginas: list[str]) -> date | None:
    """Data (provável) de aplicação da prova objetiva: no cronograma ("Aplicação das provas objetivas 22/2/2026")
    ou no texto corrido ("a Prova Objetiva será realizada … no dia 12 de outubro de 2025")."""
    texto = TextoCorrido.de(paginas).texto
    if match := _DATA_NO_CRONOGRAMA.search(texto):
        mes = int(match['mes'])
    elif match := _DATA_POR_EXTENSO.search(texto):
        mes = _MESES[match['mes'].lower()]
    else:
        return None
    return data_valida(int(match['dia']), mes, int(match['ano']))


def data_valida(dia: int, mes: int, ano: int) -> date | None:
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def mencao_penalidade(paginas: list[str]) -> bool:
    """O texto fala em descontar pontos por erro? "Anulação" e "descontos" soltos não contam."""
    return _MENCAO_PENALIDADE.search(TextoCorrido.de(paginas).texto) is not None


def resolver_correcao(config: ConcursoConfig, documentos: dict[str, list[str]]) -> list[ConfiguracaoCorrecao]:
    """Regra de correção do concurso, uma por variante, com precedência edital, depois configuração, depois default.

    `documentos` mapeia cada documento do edital às suas páginas, na ordem de leitura (anexos primeiro).
    Campos que a fonte vencedora não define (pesos, nota máxima, nota de corte) são completados pelas
    seguintes; sem nota máxima declarada, ela é a soma dos pesos dos itens. Nos pesos de uma variante a
    precedência se inverte: os declarados no concurso.yaml sobrescrevem o quadro de pesos do edital.
    """
    declarada = config.correcao or CorrecaoConfig()
    base = _resolver_regra(config, documentos, declarada)
    if declarada.variantes:
        quadro = extrair_quadro_de_pesos(config, documentos)
        configuracoes = [_resolver_variante(config.nome, v, base, quadro) for v in declarada.variantes]
    else:
        configuracoes = [base]
    data_prova, fonte_data = _resolver_data_prova(config, documentos)
    return [
        replace(_completar(config, cfg, declarada), data_prova=data_prova, fonte_data=fonte_data)
        for cfg in configuracoes
    ]


def gravar_correcao(configuracoes: list[ConfiguracaoCorrecao], destino: Path) -> None:
    conteudo = json.dumps(
        [asdict(cfg) for cfg in configuracoes], indent=2, ensure_ascii=False, default=date.isoformat
    )
    (destino / ARQUIVO_CORRECAO).write_text(conteudo, encoding='utf-8')


def ler_correcao(pasta: Path) -> list[ConfiguracaoCorrecao]:
    dados = json.loads((pasta / ARQUIVO_CORRECAO).read_text(encoding='utf-8'))
    return [
        ConfiguracaoCorrecao(
            **{
                **cfg,
                'modelo': ModeloCorrecao(cfg['modelo']),
                'fonte': FonteCorrecao(cfg['fonte']),
                'pesos': tuple(PesoItens(**faixa) for faixa in cfg['pesos']),
                'data_prova': cfg['data_prova'] and date.fromisoformat(cfg['data_prova']),
                'fonte_data': cfg['fonte_data'] and FonteCorrecao(cfg['fonte_data']),
            }
        )
        for cfg in dados
    ]


def _resolver_data_prova(
    config: ConcursoConfig, documentos: dict[str, list[str]]
) -> tuple[date | None, FonteCorrecao | None]:
    """A configuração vem antes porque a data do edital é só provável e pode ter sido retificada."""
    if config.data_prova is not None:
        return config.data_prova, FonteCorrecao.CONFIG
    for paginas in documentos.values():
        if (data := extrair_data_prova(paginas)) is not None:
            return data, FonteCorrecao.EDITAL
    avisar(
        logger,
        f'{config.nome}: não encontrei a data da prova no edital nem nos dados do concurso. '
        'Ele fica sem data e fora da análise de evolução.',
        'informe a data em Concursos > Conferir > Dados do edital.',
        'data_prova ausente no edital e no concurso.yaml',
    )
    return None, None


def _resolver_regra(
    config: ConcursoConfig, documentos: dict[str, list[str]], declarada: CorrecaoConfig
) -> ConfiguracaoCorrecao:
    extraida = _extrair_dos_documentos(documentos, config.total_itens)
    if extraida is not None:
        _avisar_divergencia_da_configuracao(config.nome, extraida, declarada)
        cfg = extraida if extraida.pesos else replace(extraida, pesos=declarada.pesos)
    elif declarada.define_regra:
        cfg = ConfiguracaoCorrecao(
            fator_penalidade=declarada.fator_penalidade or 0.0,
            pesos=declarada.pesos,
            fonte=FonteCorrecao.CONFIG,
            confianca=CONFIANCA_CONFIG,
        )
    elif (fator := penalidade_do_perfil(config)) is not None:
        cfg = ConfiguracaoCorrecao(
            fator_penalidade=fator,
            pesos=declarada.pesos,
            fonte=FonteCorrecao.PERFIL,
            confianca=CONFIANCA_PERFIL,
        )
        avisar(
            logger,
            f'{config.nome}: não encontrei a regra de correção no edital. '
            f'Vou usar a regra padrão da {perfil_da_banca(config.banca).nome or config.banca}.',
            'se estiver errada, ajuste em Concursos > Conferir > Dados do edital.',
            f'regra do perfil da banca {config.banca} (fator {fator:g}); o edital e o concurso.yaml não a trazem',
        )
    else:
        cfg = ConfiguracaoCorrecao()
        _avisar_default(config.nome, documentos)
    if cfg.fonte is not FonteCorrecao.DEFAULT:
        _avisar_contradicao_com_pontuacao(config, cfg)
    return cfg


def penalidade_do_perfil(config: ConcursoConfig) -> float | None:
    """O fator do perfil da banca, só quando o formato do concurso é o padrão do perfil; o `generic` é o
    default do projeto, não um perfil que preencha valor."""
    perfil = perfil_da_banca(config.banca)
    if perfil.id == PERFIL_GENERICO or perfil.formato != config.formato:
        return None
    return perfil.penalidade


@dataclass(frozen=True)
class _LinhaDoQuadro:
    pesos: tuple[PesoItens, ...]
    trecho: str
    documento: str
    pagina: int


def _resolver_variante(
    nome: str, variante: VarianteCorrecaoConfig, base: ConfiguracaoCorrecao, quadro: dict[str, _LinhaDoQuadro]
) -> ConfiguracaoCorrecao:
    """Com pesos próprios, a variante descarta a nota máxima do edital, que vale para os pesos do concurso."""
    if variante.pesos:
        return replace(
            base,
            pesos=variante.pesos,
            nota_maxima=None,
            fonte=FonteCorrecao.CONFIG,
            confianca=CONFIANCA_CONFIG,
            trecho_origem=None,
            documento_origem=None,
            pagina_origem=None,
            variante=variante.nome,
        )
    if (linha := quadro.get(variante.nome)) is not None:
        return replace(
            base,
            pesos=linha.pesos,
            nota_maxima=None,
            fonte=FonteCorrecao.EDITAL,
            confianca=CONFIANCA_QUADRO_DE_PESOS,
            trecho_origem=linha.trecho,
            documento_origem=linha.documento,
            pagina_origem=linha.pagina,
            variante=variante.nome,
        )
    avisar(
        logger,
        f'{nome}: não encontrei no edital os pesos do cargo {variante.nome}. Vou usar os pesos gerais do concurso.',
        'confira a tabela de pesos no edital.',
        f'variante {variante.nome} sem pesos no quadro do edital nem no concurso.yaml',
    )
    return replace(base, variante=variante.nome)


def _completar(
    config: ConcursoConfig, cfg: ConfiguracaoCorrecao, declarada: CorrecaoConfig
) -> ConfiguracaoCorrecao:
    soma_dos_pesos = sum(cfg.peso_de(questao) for prova in config.provas for questao in prova.questoes)
    return replace(
        cfg,
        modelo=ModeloCorrecao.pelo_fator(cfg.fator_penalidade, ponderada=pesos_variam(cfg.pesos)),
        nota_maxima=_primeiro_definido(cfg.nota_maxima, declarada.nota_maxima, float(soma_dos_pesos)),
        nota_corte=_primeiro_definido(cfg.nota_corte, declarada.nota_corte),
    )


def _extrair_dos_documentos(
    documentos: dict[str, list[str]], total_itens: int
) -> ConfiguracaoCorrecao | None:
    for documento, paginas in documentos.items():
        if (cfg := extrair_fator_correcao(paginas, total_itens)) is not None:
            return replace(cfg, documento_origem=documento)
    return None


def extrair_quadro_de_pesos(
    config: ConcursoConfig, documentos: dict[str, list[str]]
) -> dict[str, _LinhaDoQuadro]:
    """Pesos por eixo temático de cada variante, lidos do quadro de pesos (CPNU).

    As faixas vêm do texto do edital: primeiro os itens de conhecimentos gerais, com peso 1, e depois um
    bloco de itens consecutivos por eixo. A linha do quadro é o código do cargo seguido de um peso de 1 a 5
    por eixo; a tabela de vagas repete o código com quantidades e não pode casar.
    """
    textos = {documento: TextoCorrido.de(paginas) for documento, paginas in documentos.items()}
    gerais, eixos = _primeiro_em(textos, _QUESTOES_GERAIS), _primeiro_em(textos, _EIXOS_TEMATICOS)
    if gerais is None or eixos is None:
        return {}
    n_gerais, n_eixos, por_eixo = int(gerais['valor']), int(eixos['eixos']), int(eixos['itens'])
    if n_gerais + n_eixos * por_eixo != config.total_itens:
        avisar(
            logger,
            f'{config.nome}: o edital diz que a prova tem {n_gerais + n_eixos * por_eixo} questões, '
            f'mas o concurso cadastrado tem {config.total_itens}. Não usei a tabela de pesos por cargo do edital.',
            'confira se todas as provas do concurso foram cadastradas.',
            f'{n_gerais} itens gerais e {n_eixos} eixos de {por_eixo}; quadro de pesos ignorado',
        )
        return {}
    encontrados = {}
    for variante in config.correcao.variantes:
        linha = re.compile(
            rf'(?<![\w-]){re.escape(variante.nome)}(?![\w-])(?:(?!{_CODIGO_DE_CARGO})\D){{0,80}}?'
            rf'(?P<pesos>[1-5](?:\s[1-5]){{{n_eixos - 1}}})(?!\s?\d)'
        )
        for documento, texto in textos.items():
            if match := linha.search(texto.texto):
                pesos = _faixas_dos_eixos(n_gerais, por_eixo, [float(p) for p in match['pesos'].split()])
                encontrados[variante.nome] = _LinhaDoQuadro(
                    pesos, match[0], documento, texto.pagina(match.start())
                )
                break
    return encontrados


def _faixas_dos_eixos(n_gerais: int, por_eixo: int, pesos_eixos: list[float]) -> tuple[PesoItens, ...]:
    eixos = (
        PesoItens(n_gerais + i * por_eixo + 1, n_gerais + (i + 1) * por_eixo, peso)
        for i, peso in enumerate(pesos_eixos)
    )
    return (PesoItens(1, n_gerais, 1.0), *eixos)


def _primeiro_em(textos: dict[str, TextoCorrido], padrao: re.Pattern) -> re.Match | None:
    return next((match for texto in textos.values() if (match := padrao.search(texto.texto))), None)


def _pesos_por_parte(
    match: re.Match, total_itens: int | None, nota_maxima: float | None
) -> tuple[PesoItens, ...]:
    """Pesos de conhecimentos gerais e específicos, nessa ordem de itens. Quantos itens tem cada parte sai de
    itens = gerais + específicos e nota máxima = soma dos pesos; sem solução inteira, não há pesos."""
    gerais, especificos = numero_decimal(match['gerais']), numero_decimal(match['especificos'])
    if total_itens is None or nota_maxima is None or gerais == especificos:
        return ()
    n_especificos = (nota_maxima - gerais * total_itens) / (especificos - gerais)
    if abs(n_especificos - round(n_especificos)) > 1e-9 or not 0 < round(n_especificos) < total_itens:
        return ()
    fim_gerais = total_itens - round(n_especificos)
    return (PesoItens(1, fim_gerais, gerais), PesoItens(fim_gerais + 1, total_itens, especificos))


def _avisar_default(nome: str, documentos: dict[str, list[str]]) -> None:
    dica = 'informe a regra em Concursos > Conferir > Dados do edital.'
    if any(mencao_penalidade(paginas) for paginas in documentos.values()):
        avisar(
            logger,
            f'{nome}: o edital fala em desconto por erro, mas não entendi a regra. '
            'Por enquanto, cada acerto vale um ponto, sem desconto.',
            dica,
            'regra de correção não reconhecida, mas o edital menciona penalidade; default (bruta, fator 0)',
        )
    else:
        avisar(
            logger,
            f'{nome}: não encontrei a regra de correção no edital. '
            'Vou usar a regra padrão: cada acerto vale um ponto, sem desconto.',
            dica,
            'regra de correção ausente no edital e no concurso.yaml; default (bruta, fator 0)',
        )


def _avisar_divergencia_da_configuracao(
    nome: str, extraida: ConfiguracaoCorrecao, declarada: CorrecaoConfig
) -> None:
    if declarada.fator_penalidade is not None and declarada.fator_penalidade != extraida.fator_penalidade:
        avisar(
            logger,
            f'{nome}: a regra de correção do cadastro é diferente da do edital; vale a do edital.',
            detalhe=(
                f'correcao.fator_penalidade declarado ({declarada.fator_penalidade:g}) '
                f'difere do edital ({extraida.fator_penalidade:g})'
            ),
        )
    if declarada.pesos and extraida.pesos and declarada.pesos != extraida.pesos:
        avisar(
            logger,
            f'{nome}: os pesos das questões no cadastro são diferentes dos do edital; valem os do edital.',
            detalhe='correcao.pesos declarados diferem dos pesos do edital',
        )


def _avisar_contradicao_com_pontuacao(config: ConcursoConfig, cfg: ConfiguracaoCorrecao) -> None:
    if cfg.fator_penalidade != config.pontuacao.fator_penalidade:
        avisar(
            logger,
            f'{config.nome}: o jeito de calcular a nota no cadastro não bate com a regra de correção. '
            'As planilhas por questão seguem o cadastro.',
            'confira o tipo de prova e a regra de correção em Concursos.',
            f"pontuacao '{config.pontuacao.value}' do concurso.yaml contradiz a regra de correção "
            f'({cfg.modelo.value}, fator {cfg.fator_penalidade:g}, fonte {cfg.fonte.value}); '
            'a nota_liquida dos CSVs segue a pontuacao declarada',
        )


def _primeiro_definido(*valores: float | None) -> float | None:
    return next((v for v in valores if v is not None), None)


def _primeiro_match(texto: TextoCorrido, padroes: tuple[re.Pattern, ...]) -> re.Match | None:
    return next((match for padrao in padroes if (match := padrao.search(texto.texto))), None)


def _valor_do_primeiro_padrao(texto: TextoCorrido, padroes: tuple[re.Pattern, ...]) -> float | None:
    match = _primeiro_match(texto, padroes)
    return None if match is None else numero_decimal(match['valor'])
