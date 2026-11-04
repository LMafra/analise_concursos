"""Regras do edital além do conteúdo programático: identificação, pesos, distribuição, cortes, cronograma e
metadados, cada valor com fonte, trecho, documento e página. Extração por regex, sem LLM."""

import json
import logging
import re
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

from concursos.analytics.correcao import (
    CONFIANCA_CONFIG,
    CONFIANCA_PERFIL,
    CONFIANCA_QUADRO_DE_PESOS,
    ConfiguracaoCorrecao,
    TextoCorrido,
    data_valida,
    extrair_fator_correcao,
    extrair_quadro_de_pesos,
    penalidade_do_perfil,
)
from concursos.analytics.pistas_edital import CANDIDATOS, VERSAO_CANDIDATOS, Candidato
from concursos.concurso_config import ConcursoConfig, PesoItens, pesos_variam
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO, maiusculo, mesclar_json, titulo_legivel
from concursos.modelo import ALTERNATIVAS_PADRAO, Escolaridade, Formato
from concursos.perfis import PERFIL_GENERICO, perfil_da_banca
from concursos.texto import NUMERO_DECIMAL, normalizar, numero_decimal

logger = logging.getLogger(__name__)

CONFIANCA_DESCOBERTA = 0.6
CONFIANCA_LISTA_DE_CARGOS = 0.9
CONFIANCA_CARGO_UNICO = 0.85
CONFIANCA_NOME_DO_CARGO = 0.75
CONFIANCA_CAPA = 0.8
_COBERTURA_MINIMA_CARGO = 0.75
_JANELA_DE_CARGO = 600
_JANELA_DE_ITEM = 4000
_ALCANCE_DA_NOTA_DE_RETIFICACAO = 400
_NOTA_DE_RETIFICACAO = re.compile(r'\(Retificad[oa]\s+(?:por\s+meio\s+d[oa]|pelo)\s+Edital', re.IGNORECASE)
_FIM_DE_FRASE = re.compile(r'\.(?=\s|$)')
_POR_EXTENSO = r'(?:\s*\([^)]*\))?'


class FonteRegra(StrEnum):
    RETIFICACAO = 'retificacao'
    EDITAL = 'edital'
    CONFIG = 'config'
    PERFIL = 'perfil'
    DEFAULT = 'default'
    DESCOBERTA = 'descoberta'
    LLM = 'llm'


@dataclass(frozen=True)
class Campo:
    """Um valor do edital com a sua origem; sem origem no texto, a fonte é `config`, `perfil` ou `default`."""

    valor: Any = None
    fonte: FonteRegra = FonteRegra.DEFAULT
    trecho_origem: str | None = None
    documento_origem: str | None = None
    pagina_origem: int | None = None
    confianca_extracao: float = 0.0


@dataclass(frozen=True)
class Identificacao:
    nome_oficial: Campo = field(default_factory=Campo)
    edital: Campo = field(default_factory=Campo)
    cargo: Campo = field(default_factory=Campo)
    especialidade: Campo = field(default_factory=Campo)
    vagas: Campo = field(default_factory=Campo)
    cadastro_reserva: Campo = field(default_factory=Campo)
    teto_classificados: Campo = field(default_factory=Campo)
    cargo_casado: bool = False
    cargos_do_edital: tuple[str, ...] = ()


class EscopoCorte(StrEnum):
    CONJUNTO = 'conjunto'
    GERAL = 'geral'
    ESPECIFICO = 'especifico'
    DISCIPLINA = 'disciplina'
    DISCURSIVA = 'discursiva'


class UnidadeCorte(StrEnum):
    PONTOS = 'pontos'
    ACERTOS = 'acertos'
    PERCENTUAL = 'percentual'
    NOTA_0_10 = 'nota_0_10'
    ESCORE_PADRONIZADO = 'escore_padronizado'
    CLASSIFICADOS = 'classificados'

    @property
    def calculavel(self) -> bool:
        """O escore padronizado e a quantidade de classificados dependem das notas dos outros candidatos."""
        return self not in {UnidadeCorte.ESCORE_PADRONIZADO, UnidadeCorte.CLASSIFICADOS}


@dataclass(frozen=True, kw_only=True)
class Corte(Campo):
    """Um mínimo eliminatório. No escopo `disciplina`, `bloco` diz de que bloco são as disciplinas (vazio:
    todas); a `discursiva` é só informativa. "Não zerar disciplina" é o escopo `disciplina` com 1 acerto; o
    corte por classificados não tem valor."""

    escopo: EscopoCorte
    unidade: UnidadeCorte
    bloco: EscopoCorte | None = None


@dataclass(frozen=True)
class Distribuicao:
    """Número de questões declarado. `por_disciplina` (nome da disciplina geral no edital → questões) só
    existe onde o edital tem quadro por disciplina (FGV); `por_tipo` mapeia o formato (`certo_errado`,
    `multipla_escolha`, `discursiva`) ao número de questões."""

    total: Campo = field(default_factory=Campo)
    geral: Campo = field(default_factory=Campo)
    especifico: Campo = field(default_factory=Campo)
    por_disciplina: Campo = field(default_factory=Campo)
    por_tipo: Campo = field(default_factory=Campo)


class TipoPeso(StrEnum):
    UNIFORME = 'uniforme'
    POR_DISCIPLINA = 'por_disciplina'
    POR_TIPO_DE_QUESTAO = 'por_tipo_de_questao'
    POR_BLOCO = 'por_bloco'
    POR_FAIXA_DE_ITENS = 'por_faixa_de_itens'
    FORMULA = 'formula'


@dataclass(frozen=True)
class Pesos:
    """Pesos declarados, a expectativa; o realizado é o do correcao.json. `faixas` mapeia a variante (vazia: o
    concurso todo) às faixas de itens no formato do correcao.json, e itens fora delas valem 1. No quadro de
    eixos, a primeira faixa é a dos conhecimentos gerais; `soma_dos_eixos` é o total prometido às demais."""

    tipo: Campo = field(default_factory=Campo)
    faixas: dict[str, Campo] = field(default_factory=dict)
    soma_dos_eixos: Campo = field(default_factory=Campo)


@dataclass(frozen=True)
class Cronograma:
    """Datas que o edital traz; `recurso` é o prazo contra o gabarito (`inicio`, `fim`).
    `discursiva_no_mesmo_dia` fica vazio sem data da discursiva."""

    objetiva: Campo = field(default_factory=Campo)
    discursiva: Campo = field(default_factory=Campo)
    resultado_preliminar: Campo = field(default_factory=Campo)
    resultado_final: Campo = field(default_factory=Campo)
    recurso: Campo = field(default_factory=Campo)
    discursiva_no_mesmo_dia: bool | None = None


class StatusExtracao(StrEnum):
    ENCONTRADO = 'encontrado'
    NAO_ENCONTRADO = 'nao_encontrado'
    AMBIGUO = 'ambiguo'


@dataclass(frozen=True, kw_only=True)
class Metadado(Campo):
    """Um candidato do registro num concurso; ambíguo, o valor é a lista dos valores encontrados."""

    chave: str
    status: StatusExtracao


@dataclass(frozen=True)
class Prova:
    """Formato, alternativas (só na múltipla escolha) e fator de penalidade, na precedência edital,
    `concurso.yaml`, perfil da banca e default (o perfil `generic`)."""

    formato: Campo = field(default_factory=Campo)
    alternativas: Campo = field(default_factory=Campo)
    penalidade: Campo = field(default_factory=Campo)


class NivelConfianca(StrEnum):
    ALTA = 'alta'
    MEDIA = 'media'
    BAIXA = 'baixa'
    MINIMA = 'minima'


LIMIAR_CONFIANCA_ALTA = 0.8
LIMIAR_CONFIANCA_MEDIA = 0.5
FONTES_DO_TEXTO = frozenset(
    {FonteRegra.EDITAL, FonteRegra.RETIFICACAO, FonteRegra.DESCOBERTA, FonteRegra.LLM}
)
CAMADA_DA_FONTE = {
    FonteRegra.EDITAL: 'heuristica',
    FonteRegra.RETIFICACAO: 'heuristica',
    FonteRegra.DESCOBERTA: 'heuristica',
    FonteRegra.LLM: 'llm',
    FonteRegra.PERFIL: 'perfil',
    FonteRegra.CONFIG: 'config',
    FonteRegra.DEFAULT: 'nenhuma',
}


@dataclass(frozen=True)
class ConfiancaEdital:
    """Média da confiança dos campos essenciais, contando 0 nos que não vieram do texto do edital. Sem
    nenhum do texto (edital em imagem, banca desconhecida), o nível é `minima`: só o conteúdo programático,
    se houver, e o que o usuário confirmar."""

    valor: float = 0.0
    nivel: NivelConfianca = NivelConfianca.MINIMA


@dataclass(frozen=True)
class RegrasEdital:
    identificacao: Identificacao = field(default_factory=Identificacao)
    pesos: Pesos = field(default_factory=Pesos)
    distribuicao: Distribuicao = field(default_factory=Distribuicao)
    cortes: tuple[Corte, ...] = ()
    cronograma: Cronograma = field(default_factory=Cronograma)
    metadados: tuple[Metadado, ...] = ()
    prova: Prova = field(default_factory=Prova)
    confianca_edital: ConfiancaEdital = field(default_factory=ConfiancaEdital)
    versao_candidatos: int = VERSAO_CANDIDATOS
    avisos: tuple[str, ...] = ()

    def metadado(self, chave: str) -> Metadado | None:
        return next((m for m in self.metadados if m.chave == chave), None)

    def gravar_json(self, caminho: Path) -> None:
        """Grava as regras no edital estruturado, preservando o conteúdo programático já gravado. Cada campo
        ganha a `camada` que o preencheu."""
        dados = json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str))
        mesclar_json(caminho, _com_camadas(dados))


def _com_camadas(valor: Any) -> Any:
    if isinstance(valor, list):
        return [_com_camadas(item) for item in valor]
    if not isinstance(valor, dict):
        return valor
    valor = {chave: _com_camadas(item) for chave, item in valor.items()}
    if 'fonte' in valor and 'confianca_extracao' in valor:
        valor['camada'] = CAMADA_DA_FONTE[FonteRegra(valor['fonte'])]
    return valor


def confianca_do_edital(regras: RegrasEdital) -> ConfiancaEdital:
    calculaveis = [
        c for c in regras.cortes if c.unidade.calculavel and c.escopo is not EscopoCorte.DISCURSIVA
    ]
    essenciais = [
        regras.identificacao.cargo,
        regras.prova.formato,
        regras.prova.penalidade,
        regras.distribuicao.total,
        regras.cronograma.objetiva,
        regras.pesos.tipo,
        max(calculaveis, key=lambda corte: corte.confianca_extracao, default=Campo()),
    ]
    if regras.prova.formato.valor == Formato.MULTIPLA_ESCOLHA:
        essenciais.append(regras.prova.alternativas)
    do_texto = [c.confianca_extracao for c in essenciais if c.fonte in FONTES_DO_TEXTO]
    if not do_texto:
        return ConfiancaEdital()
    valor = round(sum(do_texto) / len(essenciais), 2)
    if valor >= LIMIAR_CONFIANCA_ALTA:
        return ConfiancaEdital(valor, NivelConfianca.ALTA)
    if valor >= LIMIAR_CONFIANCA_MEDIA:
        return ConfiancaEdital(valor, NivelConfianca.MEDIA)
    return ConfiancaEdital(valor, NivelConfianca.BAIXA)


def _fonte_do_documento(retificacao: bool) -> FonteRegra:
    return FonteRegra.RETIFICACAO if retificacao else FonteRegra.EDITAL


@dataclass(frozen=True)
class _Documento:
    nome: str
    texto: TextoCorrido
    retificacao: bool = False


@dataclass(frozen=True)
class _Achado:
    match: re.Match
    documento: _Documento

    @property
    def retificado(self) -> bool:
        """Numa retificação, ou quando a frase do trecho é seguida da nota "(Retificado por meio do Edital
        nº …)" antes do próximo subitem."""
        if self.documento.retificacao:
            return True
        texto = self.documento.texto.texto
        fim = min(len(texto), self.match.end() + _ALCANCE_DA_NOTA_DE_RETIFICACAO)
        if proximo := _SUBITEM.search(texto, self.match.end(), fim):
            fim = proximo.start()
        nota = _NOTA_DE_RETIFICACAO.search(texto, self.match.end(), fim)
        return nota is not None and len(_FIM_DE_FRASE.findall(texto, self.match.end(), nota.start())) <= 1

    def campo(self, valor: Any, confianca: float, trecho: str | None = None) -> Campo:
        texto = self.documento.texto
        return Campo(
            valor,
            _fonte_do_documento(self.retificado),
            trecho or texto.trecho(self.match),
            self.documento.nome,
            texto.pagina(self.match.start()),
            confianca,
        )


class _Documentos:
    """Documentos na ordem de busca: retificações (a mais recente primeiro) e depois o edital e os anexos."""

    def __init__(self, documentos: dict[str, list[str]], retificacoes: dict[str, list[str]] | None = None):
        retificados = [
            _Documento(n, TextoCorrido.de(p), True) for n, p in reversed((retificacoes or {}).items())
        ]
        self.lista = [*retificados, *(_Documento(n, TextoCorrido.de(p)) for n, p in documentos.items())]
        self.paginas = {**documentos, **(retificacoes or {})}

    def todos(self, padrao: re.Pattern) -> list[_Achado]:
        return [_Achado(m, doc) for doc in self.lista for m in padrao.finditer(doc.texto.texto)]

    def primeiro(self, padrao: re.Pattern, escopo: '_Escopo | None' = None) -> _Achado | None:
        achados = (_Achado(m, doc) for doc in self.lista for m in padrao.finditer(doc.texto.texto))
        return next((a for a in achados if escopo is None or escopo.aplica(a)), None)


# --- Escopo por cargo ----------------------------------------------------------------------------------

_ARTIGOS_E_PREPOSICOES = {'A', 'AS', 'AO', 'AOS', 'O', 'OS', 'E', 'EM', 'NA', 'NO', 'PARA'}
_PALAVRAS_VAZIAS = _ARTIGOS_E_PREPOSICOES | {'DA', 'DAS', 'DE', 'DO', 'DOS'}
_MENCAO_DE_CARGO = re.compile(
    r'\b(?:cargos?|empregos?)\s+(?:de\s+)?(?P<nomes>[A-Za-zÀ-ÿ][^:;.()\d]{0,160}?)'
    r'(?=\s+(?:que|ser[áã]o?|ter[áã]o?|obtiver|a\s+prova|o\s+m[óo]dulo|na\s+prova)\b|\s*[:;.(\d]|\s*$)',
    re.IGNORECASE,
)
_SEPARADOR_DE_NOMES = re.compile(r',\s*|\s+e\s+(?=[A-ZÀ-Ý])', re.IGNORECASE)
_GENERICOS = re.compile(r'^(?:TODOS|TODAS|DEMAIS|CADA|QUALQUER|AMBOS|ESTE|ESSE)\b')
_SUBITEM = re.compile(r'(?<![\d.,])(?P<pai>\d{1,2}\.\d{1,2})(?:\.\d{1,2})*\.?\s+(?=[A-Za-zÀ-ÿ])')
_NIVEL = re.compile(r'^NIVEL\s+(?P<nivel>SUPERIOR|MEDIO|INTERMEDIARIO)')


def _palavras(texto: str) -> set[str]:
    return {p for p in re.split(r'[^A-Z0-9]+', normalizar(texto)) if p and p not in _PALAVRAS_VAZIAS}


def _cobertura(nome: str, palavras: set[str]) -> float:
    do_nome = _palavras(nome)
    return len(do_nome & palavras) / len(do_nome) if do_nome else 0.0


@dataclass(frozen=True)
class _Escopo:
    """Decide se um trecho vale para o cargo: pela última menção a cargos antes dele (ou no próprio
    trecho)."""

    palavras: frozenset[str]
    escolaridade: Escolaridade = Escolaridade.NAO_INFORMADO
    nucleo: frozenset[str] = frozenset()
    """Palavras do nome do cargo no edital: uma menção que as contém todas também cita o cargo, como o título
    de quadro "PARA OS CARGOS DE PERITO CRIMINAL FEDERAL NÚMERO DE ITENS"."""

    def aplica(self, achado: _Achado) -> bool:
        texto = achado.documento.texto.texto
        inicio = _inicio_do_item(texto, achado.match.start())
        mencoes = list(_MENCAO_DE_CARGO.finditer(texto, inicio, achado.match.end()))
        return not mencoes or self.cita(mencoes[-1]['nomes'])

    def cita(self, nomes: str) -> bool:
        partes = [n for n in _SEPARADOR_DE_NOMES.split(nomes.strip()) if n.strip()]
        return any(self._nome_aplica(normalizar(n.strip())) for n in partes)

    def _nome_aplica(self, nome: str) -> bool:
        if nivel := _NIVEL.match(nome):
            if self.escolaridade is Escolaridade.NAO_INFORMADO:
                return nivel['nivel'] == 'SUPERIOR'
            return (nivel['nivel'] == 'SUPERIOR') == (self.escolaridade is Escolaridade.SUPERIOR)
        if _GENERICOS.match(nome) or not self.palavras:
            return True
        return (
            _cobertura(nome, set(self.palavras)) == 1.0
            or bool(self.nucleo)
            and self.nucleo <= _palavras(nome)
        )


def _inicio_do_item(texto: str, posicao: int) -> int:
    """Início do subitem de dois níveis que contém a posição ("8.11" para um trecho do 8.11.5 c), onde o
    edital costuma dizer a que cargo a regra vale; sem numeração por perto, uma janela fixa."""
    inicio = max(0, posicao - _JANELA_DE_ITEM)
    subitens = list(_SUBITEM.finditer(texto, inicio, posicao))
    if not subitens:
        return max(0, posicao - _JANELA_DE_CARGO)
    ultimo = subitens[-1]
    cabecalho = re.compile(rf'(?<![\d.]){re.escape(ultimo["pai"])}\.?\s')
    pais = list(cabecalho.finditer(texto, inicio, ultimo.end()))
    return pais[-1].start() if pais else ultimo.start()


# --- Identificação -----------------------------------------------------------------------------------

_CARGO_NUMERADO = re.compile(r'^(?P<tipo>CARGO|EMPREGO)\s+(?P<numero>\d+)\s*:\s*(?P<nome>.+)$', re.MULTILINE)
_BLOCO_TEMATICO = re.compile(r'^(?P<nome>BLOCO\s+TEMÁTICO\s+\d+\s*[–-]\s*.+)$', re.MULTILINE)
_CARGO_DA_CAPA = re.compile(
    r'PARA\s+O\s+CARGO\s+DE\s+(?P<nome>[A-ZÀ-Ý]+(?:\s+[A-ZÀ-Ý]+)*?)(?=\s+EDITAL\b|\s*$)'
)
_CARGOS_NO_TEXTO = re.compile(
    r'\bcargos?\s+de\s+(?P<nomes>[A-ZÀ-Ý][\wÀ-ÿ]*(?:(?:,\s*|\s+)(?:[A-ZÀ-Ý][\wÀ-ÿ]*|de|da|do|em|e))*)'
)
_AREA_DO_CARGO = re.compile(
    r'(?P<cargo>[A-ZÀ-Ý][\wÀ-ÿ]*(?:\s+[\wÀ-ÿ]+){0,4}?)\s+[–-]\s+Área:\s+(?P<area>[^.:]{3,120}?)\.'
)
_ID_NA_CONFIGURACAO = re.compile(r'^(?:CARGO|EMPREGO)\s+(\d+)\b')
_FIM_DO_NOME_DO_CARGO = re.compile(r'\s*(?:-\s*)?(?:CÓDIGO:|REQUISITOS?:|DESCRIÇÃO|ATRIBUIÇÕES).*$')
_ESPECIALIDADE = re.compile(r'\s+[–-]\s+(?:ESPECIALIDADE|ÁREA(?:\s+\d+)?|ATRIBUIÇÃO)\s*:\s*', re.IGNORECASE)
_CONECTOR_NO_FIM = re.compile(r'(?:\b(?:DA|DE|DO|DAS|DOS|E|EM)|[–-])$')
_LINHA_DE_EDITAL = re.compile(r'^EDITAL\b.*$', re.MULTILINE)
_NAO_E_ORGAO = re.compile(r'^(?:EDITAL|CONCURSO|PROCESSO|ABERTURA|VERSÃO|ATUALIZADO|RETIFICADO|\d)', re.I)
_ORGAO_NO_TEXTO = re.compile(
    r'\b(?:Diretor|Diretora|Presidente|Presidenta)[\w-]*\s+d[ao]\s+'
    r'(?P<orgao>[A-ZÀ-Ý][^,]{5,120}?)\s*(?:,|tendo|no\s+uso)'
)
_CADASTRO_DE_RESERVA = re.compile(
    r'cadastro\s+(?:de\s+)?reserva|banco\s+de\s+candidatos\s+aprovados', re.IGNORECASE
)
_TETO = re.compile(r'\bos\s+(?P<valor>\d+)\s+candidatos\s+mais\s+bem\s+classificados', re.IGNORECASE)
_VAGAS_DO_CARGO = re.compile(
    r'(?P<valor>\d+)\s*(?:\([^)]*\))?\s*vagas\s+para\s+o\s+cargo\s+de\s+(?P<nomes>[A-ZÀ-Ý][\wÀ-ÿ]*'
    r'(?:\s+(?:[A-ZÀ-Ý][\wÀ-ÿ]*|de|da|do|em))*)'
)


@dataclass(frozen=True)
class _Cargo:
    nome: str
    achado: _Achado
    numero: str | None = None
    especialidade: str | None = None
    confianca: float = CONFIANCA_LISTA_DE_CARGOS


def _identificar(config: ConcursoConfig, docs: _Documentos) -> tuple[Identificacao, _Escopo, list[str]]:
    avisos: list[str] = []
    cargos = _cargos_do_edital(docs)
    escolhido = _casar_cargo(config.cargo, cargos)
    palavras = _palavras(config.cargo or '')
    if escolhido is not None:
        palavras |= _palavras(escolhido.nome)
        cargo = escolhido.achado.campo(escolhido.nome, escolhido.confianca)
        campo_especialidade = _especialidade(config.cargo, escolhido, docs)
    else:
        cargo, campo_especialidade = Campo(), Campo()
        if cargos:
            avisos.append(
                f'{config.nome}: cargo {config.cargo!r} do concurso.yaml não casa com nenhum cargo do edital '
                f'({"; ".join(c.nome for c in cargos)}); extração no escopo do concurso inteiro'
            )
    nucleo = frozenset(_palavras(escolhido.nome)) if escolhido else frozenset()
    escopo = _Escopo(frozenset(palavras), config.escolaridade, nucleo)
    vagas = next(
        (a.campo(int(a.match['valor']), CONFIANCA_NOME_DO_CARGO) for a in docs.todos(_VAGAS_DO_CARGO)
         if escopo.cita(a.match['nomes'])),
        Campo(),
    )  # fmt: skip
    teto = docs.primeiro(_TETO, escopo)
    reserva = docs.primeiro(_CADASTRO_DE_RESERVA)
    identificacao = Identificacao(
        nome_oficial=_orgao(docs),
        edital=_linha_do_edital(docs),
        cargo=cargo,
        especialidade=campo_especialidade,
        vagas=vagas,
        cadastro_reserva=reserva.campo(True, CONFIANCA_CAPA) if reserva else Campo(),
        teto_classificados=teto.campo(int(teto.match['valor']), CONFIANCA_NOME_DO_CARGO) if teto else Campo(),
        cargo_casado=escolhido is not None,
        cargos_do_edital=tuple(c.nome for c in cargos),
    )
    return identificacao, escopo, avisos


def _cargos_do_edital(docs: _Documentos) -> list[_Cargo]:
    numerados: dict[str, _Cargo] = {}
    for doc in docs.lista:
        linhas = _linhas(docs.paginas[doc.nome])
        for indice, linha in enumerate(linhas):
            if (m := _CARGO_NUMERADO.match(linha)) and m['numero'] not in numerados:
                nome = m['nome']
                if _CONECTOR_NO_FIM.search(nome) and indice + 1 < len(linhas):
                    nome = f'{nome} {linhas[indice + 1]}'
                numerados[m['numero']] = _cargo_numerado(m['numero'], nome, doc)
    if numerados:
        return list(numerados.values())
    blocos: dict[str, _Cargo] = {}
    for doc in docs.lista:
        for linha in _linhas(docs.paginas[doc.nome]):
            if (m := _BLOCO_TEMATICO.match(linha)) and (nome := titulo_legivel(m['nome'])) not in blocos:
                achado = _Achado(re.search(_sem_espacos(linha[:25]), doc.texto.texto), doc)
                blocos[nome] = _Cargo(nome, achado)
    if blocos:
        return list(blocos.values())
    if capa := docs.primeiro(_CARGO_DA_CAPA):
        return [_Cargo(titulo_legivel(capa.match['nome']), capa, confianca=CONFIANCA_CARGO_UNICO)]
    return _cargos_citados_no_texto(docs)


def _cargo_numerado(numero: str, nome: str, doc: _Documento) -> _Cargo:
    nome = _FIM_DO_NOME_DO_CARGO.sub('', nome).strip(' -–')
    partes = _ESPECIALIDADE.split(nome, maxsplit=1)
    if len(partes) == 1:
        partes = re.split(r'\s+–\s+', nome, maxsplit=1)
    padrao = re.compile(rf'(?:CARGO|EMPREGO)\s+{numero}\s*:\s*{_sem_espacos(partes[0][:30])}')
    match = padrao.search(doc.texto.texto) or re.search(_sem_espacos(partes[0][:20]), doc.texto.texto)
    achado = _Achado(match, doc)
    especialidade = titulo_legivel(partes[1]) if len(partes) > 1 else None
    return _Cargo(titulo_legivel(partes[0]), achado, numero, especialidade)


def _cargos_citados_no_texto(docs: _Documentos) -> list[_Cargo]:
    """Na FGV os cargos aparecem no preâmbulo ("vagas para o cargo de Analista de Gestão")."""
    cargos: dict[str, _Cargo] = {}
    for achado in docs.todos(_CARGOS_NO_TEXTO)[:20]:
        for nome in _SEPARADOR_DE_NOMES.split(achado.match['nomes']):
            nome = re.sub(r'(?:\s+(?:de|da|do|em|e))+$', '', nome.strip())
            if nome and nome[0].isupper() and nome not in cargos:
                cargos[nome] = _Cargo(nome, achado, confianca=CONFIANCA_NOME_DO_CARGO)
    return list(cargos.values())


def _casar_cargo(cargo: str | None, cargos: list[_Cargo]) -> _Cargo | None:
    if len(cargos) == 1 and not cargo:
        return cargos[0]
    if not cargo or not cargos:
        return None
    if (numero := _ID_NA_CONFIGURACAO.match(normalizar(cargo))) and any(c.numero for c in cargos):
        return next((c for c in cargos if c.numero == numero.group(1)), None)
    palavras = _palavras(cargo)
    notas = {
        indice: (_cobertura(c.nome, palavras), len(_palavras(c.nome) & palavras))
        for indice, c in enumerate(cargos)
    }
    maior = max(notas.values())
    melhores = [i for i, nota in notas.items() if nota == maior]
    if maior[0] < _COBERTURA_MINIMA_CARGO or len(melhores) > 1:
        return cargos[0] if len(cargos) == 1 else None
    return cargos[melhores[0]]


def _especialidade(cargo: str | None, escolhido: _Cargo, docs: _Documentos) -> Campo:
    if escolhido.especialidade:
        return escolhido.achado.campo(escolhido.especialidade, escolhido.confianca)
    if escolhido.numero is not None:
        return Campo()
    palavras = _palavras(cargo or '')
    areas = [
        a
        for a in docs.todos(_AREA_DO_CARGO)
        if _cobertura(escolhido.nome, _palavras(a.match['cargo'])) == 1.0
        and _cobertura(a.match['area'], palavras) == 1.0
    ]
    if areas:
        melhor = max(areas, key=lambda a: len(_palavras(a.match['area'])))
        return melhor.campo(melhor.match['area'].strip(), CONFIANCA_NOME_DO_CARGO)
    if resto := _resto_do_cargo(cargo, escolhido.nome):
        return Campo(resto, FonteRegra.CONFIG, confianca_extracao=1.0)
    return Campo()


def _resto_do_cargo(cargo: str | None, nome: str) -> str | None:
    """A especialidade da FGV: o cargo do concurso.yaml sem as palavras do cargo do edital."""
    if not cargo:
        return None
    do_nome = {normalizar(p) for p in nome.split()}
    resto = [p for p in cargo.split() if normalizar(p) not in do_nome]
    while resto and normalizar(resto[0]) in _PALAVRAS_VAZIAS | {'-', '–'}:
        resto.pop(0)
    return ' '.join(resto) or None


def _orgao(docs: _Documentos) -> Campo:
    for doc in reversed(docs.lista):
        linhas = _linhas(docs.paginas[doc.nome][:1])
        for indice, linha in enumerate(linhas[:4]):
            if maiusculo(linha) and not _NAO_E_ORGAO.match(linha) and len(linha.split()) >= 2:
                if indice + 1 < len(linhas) and re.fullmatch(r'\([^)]+\)', linhas[indice + 1]):
                    linha = f'{linha} {linhas[indice + 1]}'
                match = re.search(_sem_espacos(linha.split()[0]), doc.texto.texto)
                return _Achado(match, doc).campo(_titulo_com_siglas(linha), CONFIANCA_CAPA, linha)
    if achado := docs.primeiro(_ORGAO_NO_TEXTO):
        return achado.campo(achado.match['orgao'].strip(), CONFIANCA_NOME_DO_CARGO)
    return Campo()


def _linha_do_edital(docs: _Documentos) -> Campo:
    for doc in reversed(docs.lista):
        if match := _LINHA_DE_EDITAL.search('\n'.join(_linhas(docs.paginas[doc.nome][:1]))):
            linha = match[0].strip()
            achado = _Achado(re.search(_sem_espacos(linha[:20]), doc.texto.texto), doc)
            return achado.campo(linha, CONFIANCA_CAPA, linha)
    return Campo()


def _titulo_com_siglas(linha: str) -> str:
    """Título legível que mantém siglas curtas ("GESTÃO DO SUS" → "Gestão do SUS")."""
    originais = linha.split()
    return ' '.join(
        original
        if original.isalpha()
        and len(original) == 3
        and original.isupper()
        and normalizar(original) not in _PALAVRAS_VAZIAS | {'NAS', 'NOS', 'COM', 'SEM', 'POR'}
        else legivel
        for original, legivel in zip(originais, titulo_legivel(linha).split(), strict=True)
    )


def _sem_espacos(trecho: str) -> str:
    """Padrão de um trecho de linha crua no `TextoCorrido`, que junta os espaços repetidos."""
    return r'\s+'.join(map(re.escape, trecho.split()))


def _linhas(paginas: list[str]) -> list[str]:
    return [linha.strip() for pagina in paginas for linha in pagina.splitlines() if linha.strip()]


# --- Pesos -------------------------------------------------------------------------------------------

_SOMA_DOS_PESOS = re.compile(
    r'pesos\s+atribuídos[^.]{0,150}?totalizando,?\s+(?:em\s+conjunto,?\s+)?o\s+valor\s+de\s+(?P<n>\d+)', re.I
)


def _regra_de_correcao(
    config: ConcursoConfig, docs: _Documentos
) -> tuple[_Documento, ConfiguracaoCorrecao] | None:
    """A regra de correção do primeiro documento, na ordem de busca, em que ela casa."""
    for doc in docs.lista:
        if (regra := extrair_fator_correcao(docs.paginas[doc.nome], config.total_itens)) is not None:
            return doc, regra
    return None


def _campo_da_regra(valor: Any, doc: _Documento, regra: ConfiguracaoCorrecao) -> Campo:
    return Campo(
        valor,
        _fonte_do_documento(doc.retificacao),
        regra.trecho_origem,
        doc.nome,
        regra.pagina_origem,
        regra.confianca,
    )


def _extrair_pesos(config: ConcursoConfig, docs: _Documentos) -> tuple[Pesos, list[str]]:
    """O quadro de eixos por variante (CPNU) ou, sem ele, a regra de pontuação que a correção também lê:
    pontos iguais em todos os itens são peso uniforme, e pontos diferentes por parte, peso por bloco."""
    soma = docs.primeiro(_SOMA_DOS_PESOS)
    soma_dos_eixos = soma.campo(int(soma.match['n']), CONFIANCA_DISTRIBUICAO) if soma else Campo()
    if faixas := _quadro_de_eixos(config, docs):
        tipo = replace(next(iter(faixas.values())), valor=TipoPeso.POR_FAIXA_DE_ITENS)
        return Pesos(tipo, faixas, soma_dos_eixos), []
    uniforme = None
    if achada := _regra_de_correcao(config, docs):
        doc, regra = achada
        if pesos_variam(regra.pesos):
            return Pesos(
                _campo_da_regra(TipoPeso.POR_BLOCO, doc, regra),
                {'': _campo_da_regra(regra.pesos, doc, regra)},
                soma_dos_eixos,
            ), []
        uniforme = Pesos(_campo_da_regra(TipoPeso.UNIFORME, doc, regra), {}, soma_dos_eixos)
    if por_prova := _pesos_por_prova(config, docs, soma_dos_eixos):
        return por_prova, []
    if uniforme is not None:
        return uniforme, []
    aviso = _aviso_de_default(config, docs, 'pesos não encontrados no edital')
    return Pesos(soma_dos_eixos=soma_dos_eixos), [aviso]


CONFIANCA_PESO_POR_PROVA = 0.8
_PESO = rf'(?P<gerais>{NUMERO_DECIMAL}){_POR_EXTENSO}'
_PESO_ESPECIFICO = rf'(?P<especificos>{NUMERO_DECIMAL}){_POR_EXTENSO}'
_PESOS_POR_PROVA = (
    re.compile(
        rf'{_PESO}\s*pontos?,?\s+caso\s+a\s+resposta[^;]{{0,200}}?concordância[^;]{{0,120}}?'
        rf'conhecimentos\s+(?:básicos|gerais).{{0,600}}?{_PESO_ESPECIFICO}\s*pontos?,?\s+caso\s+a\s+resposta'
        r'[^;]{0,200}?concordância[^;]{0,120}?conhecimentos\s+específicos',
        re.IGNORECASE,
    ),
    re.compile(
        rf'{_PESO}\s*pontos?,\s*no\s*caso\s*de\s*questão\s*de\s*conhecimentos?\s*com(?:um|uns),?\s*e\s*'
        rf'{_PESO_ESPECIFICO}\s*pontos?,\s*no\s*caso\s*de\s*questão\s*de\s*conhecimentos?\s*específicos?',
        re.IGNORECASE,
    ),
    re.compile(
        rf'peso\s+{_PESO}\s+à\s+nota\s+da\s+prova\s+(?:objetiva\s+)?de\s+conhecimentos\s+gerais[^;]{{0,40}};'
        rf'\s*b\)\s*peso\s+{_PESO_ESPECIFICO}\s+à\s+nota\s+da\s+prova\s+(?:objetiva\s+)?de\s+conhecimentos\s+'
        r'específicos',
        re.IGNORECASE,
    ),
    re.compile(rf'quest[õo]es,?\s+com\s+pesos\s+{_PESO}\s+e\s+{_PESO_ESPECIFICO}', re.IGNORECASE),
)
_PONTOS_POR_PROVA = (
    re.compile(
        r'(?P<n_gerais>\d+)\s+quest[õo]es\s+de\s+conhecimentos\s+gerais,?\s+que\s+valer[ãa]o\s+'
        rf'(?P<pontos_gerais>{NUMERO_DECIMAL})\s+pontos,?\s+e\s+(?P<n_especificos>\d+)\s+quest[õo]es\s+de\s+'
        rf'conhecimentos\s+espec[íi]ficos,?\s+que\s+valer[ãa]o\s+(?P<pontos_especificos>{NUMERO_DECIMAL})\s+pontos',
        re.IGNORECASE,
    ),
    re.compile(
        rf'Conhecimentos\s+(?P<n_gerais>\d+)\s+(?P<gerais>\d+,\d+)\s+{NUMERO_DECIMAL}\s+[\d,\s]*Gerais\s+'
        rf'Conhecimentos\s+(?P<n_especificos>\d+)\s+(?P<especificos>\d+,\d+)\s',
    ),
)


def _pesos_por_prova(config: ConcursoConfig, docs: _Documentos, soma_dos_eixos: Campo) -> Pesos | None:
    """Peso diferente nos conhecimentos gerais e nos específicos: pontos por item de cada prova, peso da nota
    de cada prova ou pontos totais de cada prova. Com o número de questões de cada uma (e somando o total do
    concurso), viram faixas de itens."""
    for padrao in _PONTOS_POR_PROVA:
        if achado := docs.primeiro(padrao):
            m = achado.match
            n_gerais, n_especificos = int(m['n_gerais']), int(m['n_especificos'])
            if 'pontos_gerais' in m.re.groupindex:
                gerais = numero_decimal(m['pontos_gerais']) / n_gerais
                especificos = numero_decimal(m['pontos_especificos']) / n_especificos
            else:
                gerais, especificos = numero_decimal(m['gerais']), numero_decimal(m['especificos'])
            return _pesos_por_bloco(
                config, achado, gerais, especificos, (n_gerais, n_especificos), soma_dos_eixos
            )
    for padrao in _PESOS_POR_PROVA:
        if achado := docs.primeiro(padrao):
            gerais, especificos = (
                numero_decimal(achado.match['gerais']),
                numero_decimal(achado.match['especificos']),
            )
            return _pesos_por_bloco(config, achado, gerais, especificos, None, soma_dos_eixos)
    return None


def _pesos_por_bloco(
    config: ConcursoConfig,
    achado: _Achado,
    gerais: float,
    especificos: float,
    quantidades: tuple[int, int] | None,
    soma_dos_eixos: Campo,
) -> Pesos | None:
    if gerais == especificos:
        return None
    tipo = achado.campo(TipoPeso.POR_BLOCO, CONFIANCA_PESO_POR_PROVA)
    if quantidades is None or sum(quantidades) != config.total_itens:
        return Pesos(tipo, {}, soma_dos_eixos)
    n_gerais = quantidades[0]
    faixas = (PesoItens(1, n_gerais, gerais), PesoItens(n_gerais + 1, config.total_itens, especificos))
    return Pesos(tipo, {'': replace(tipo, valor=faixas)}, soma_dos_eixos)


def _quadro_de_eixos(config: ConcursoConfig, docs: _Documentos) -> dict[str, Campo]:
    if config.correcao is None or not config.correcao.variantes:
        return {}
    retificacoes = {doc.nome for doc in docs.lista if doc.retificacao}
    quadro = extrair_quadro_de_pesos(config, {doc.nome: docs.paginas[doc.nome] for doc in docs.lista})
    return {
        variante: Campo(
            linha.pesos,
            _fonte_do_documento(linha.documento in retificacoes),
            linha.trecho,
            linha.documento,
            linha.pagina,
            CONFIANCA_QUADRO_DE_PESOS,
        )
        for variante, linha in quadro.items()
    }


# --- Distribuição ------------------------------------------------------------------------------------

CONFIANCA_DISTRIBUICAO = 0.9
CONFIANCA_QUADRO_POR_POSICAO = 0.7
_ALCANCE_DO_QUADRO = 800
_POR_EXTENSO_NUMERO = {'UM': 1, 'UMA': 1, 'DOIS': 2, 'DUAS': 2, 'TRES': 3, 'QUATRO': 4, 'CINCO': 5}
_QUADRO_DE_PROVAS = re.compile(r'NÚMERO\s+DE(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ/]+)*?\s+ITENS')
_LINHA_DE_PROVA = re.compile(
    r'Conhecimentos\s+(?P<bloco>b[áa]sicos|gerais|espec[íi]ficos)(?:\s+[–-]\s+Bloco\s+[IVX]+)?\s+'
    r'(?P<n>\d{1,3})\b',
    re.IGNORECASE,
)
_PROVA_OBJETIVA_NO_QUADRO = re.compile(r'\(P\s*\d?\s*\)\s*Objetiva\s+(?P<n>\d{1,3})\b')
_QUESTOES_POR_BLOCO = re.compile(
    rf'(?P<geral>\d+){_POR_EXTENSO}\s+quest[õo]es\s+de\s+Conhecimentos\s+Gerais\s+e\s+'
    rf'(?P<especifico>\d+){_POR_EXTENSO}\s+quest[õo]es\s+de\s+Conhecimentos\s+Espec[íi]ficos'
    rf'|Conhecimentos\s+Gerais\)\s+com\s+(?P<geral_modulo>\d+){_POR_EXTENSO}\s+quest[õo]es\s+e\s+'
    rf'M[óo]dulo\s+II\s+\(Conhecimentos\s+Espec[íi]ficos\)\s+com\s+(?P<especifico_modulo>\d+)',
    re.IGNORECASE,
)
_TOTAL_DE_QUESTOES = re.compile(
    rf'composta\s+por\s+(?P<n>\d+){_POR_EXTENSO}\s+quest[õo]es(?!\s+de\s+Conhecimentos)', re.IGNORECASE
)
_CERTO_OU_ERRADO = re.compile(r'\bCERTO\b.{0,60}?\bERRADO\b')
_MULTIPLA_ESCOLHA = re.compile(r'm[úu]ltipla\s*escolha', re.IGNORECASE)
_DISCURSIVAS = re.compile(
    r'\b(?P<n>\d+|uma?|dois|duas|tr[êe]s|quatro|cinco)\s+(?:\([^)]*\)\s+)?'
    r'(?:quest(?:[õo]es|[ãa]o)|textos?|pe[çc]as?)(?:\s+\S+){0,3}?\s+(?:discursiv|dissertativ)',
    re.IGNORECASE,
)
_CABECALHO_DE_DISCIPLINAS = re.compile(r'^(?:CONHECIMENTOS\s+)?(?:Prova\s+Objetiva\s+)?DISCIPLINAS?\b', re.I)
_TOTAL_DO_QUADRO = re.compile(r'^Total\b', re.IGNORECASE)
_ROTULO_DE_BLOCO = re.compile(
    r'^(?:(?P<geral>GERAIS|M[óo]dulo\s+I\s*:\s*Conhecimentos\s+Gerais)'
    r'|(?P<especifico>ESPEC[ÍI]FICOS|M[óo]dulo\s+II\s*:\s*Conhecimentos\s+Espec[íi]ficos))\s*',
    re.IGNORECASE,
)
_LINHA_DO_QUADRO = re.compile(r'^(?P<nome>\D*?[^\d\s])\s+(?P<n>\d{1,3})(?:\s+\d{1,3})?$')


@dataclass(frozen=True)
class _QuadroDeDisciplinas:
    titulo: str
    gerais: dict[str, int]
    especifico: int | None
    achado: _Achado
    trecho: str


def _inteiro(texto: str) -> int:
    return int(texto) if texto.isdigit() else _POR_EXTENSO_NUMERO[normalizar(texto)]


def _extrair_distribuicao(
    config: ConcursoConfig, docs: _Documentos, escopo: _Escopo
) -> tuple[Distribuicao, list[str]]:
    quadro = _quadro_do_cargo(config, docs, escopo)
    geral, especifico = _blocos_declarados(docs, escopo)
    if geral.valor is None and quadro is not None:
        geral = quadro.achado.campo(sum(quadro.gerais.values()), CONFIANCA_DISTRIBUICAO, quadro.trecho)
        if quadro.especifico is not None:
            especifico = quadro.achado.campo(quadro.especifico, CONFIANCA_DISTRIBUICAO, quadro.trecho)
    if total := docs.primeiro(_TOTAL_DE_QUESTOES, escopo):
        campo_total = total.campo(int(total.match['n']), CONFIANCA_DISTRIBUICAO)
    elif geral.valor is not None and especifico.valor is not None:
        campo_total = replace(geral, valor=geral.valor + especifico.valor)
    else:
        campo_total = Campo()
    distribuicao = Distribuicao(
        total=campo_total,
        geral=geral,
        especifico=especifico,
        por_disciplina=(
            quadro.achado.campo(quadro.gerais, CONFIANCA_DISTRIBUICAO, quadro.trecho) if quadro else Campo()
        ),
        por_tipo=_por_tipo(docs, escopo, campo_total.valor),
    )
    avisos = []
    if campo_total.valor is None:
        avisos.append(_aviso_de_default(config, docs, 'número de questões não encontrado no edital'))
    return distribuicao, avisos


def _blocos_declarados(docs: _Documentos, escopo: _Escopo) -> tuple[Campo, Campo]:
    if frase := docs.primeiro(_QUESTOES_POR_BLOCO, escopo):
        m = frase.match
        return (
            frase.campo(int(m['geral'] or m['geral_modulo']), CONFIANCA_DISTRIBUICAO),
            frase.campo(int(m['especifico'] or m['especifico_modulo']), CONFIANCA_DISTRIBUICAO),
        )
    for ancora in docs.todos(_QUADRO_DE_PROVAS):
        if not escopo.aplica(ancora):
            continue
        texto = ancora.documento.texto.texto
        fim = min(len(texto), ancora.match.end() + _ALCANCE_DO_QUADRO)
        if proximo := _SUBITEM.search(texto, ancora.match.end(), fim):
            fim = proximo.start()
        linhas = [
            _Achado(m, ancora.documento) for m in _LINHA_DE_PROVA.finditer(texto, ancora.match.end(), fim)
        ]
        if linhas:
            return _soma_do_bloco(linhas, geral=True), _soma_do_bloco(linhas, geral=False)
        objetivas = list(_PROVA_OBJETIVA_NO_QUADRO.finditer(texto, ancora.match.end(), fim))
        if len(objetivas) == 2:
            geral, especifico = (
                _Achado(m, ancora.documento).campo(int(m['n']), CONFIANCA_QUADRO_POR_POSICAO)
                for m in objetivas
            )
            return geral, especifico
    return Campo(), Campo()


def _soma_do_bloco(linhas: list[_Achado], geral: bool) -> Campo:
    do_bloco = [a for a in linhas if (normalizar(a.match['bloco']) != 'ESPECIFICOS') == geral]
    if not do_bloco:
        return Campo()
    return do_bloco[0].campo(sum(int(a.match['n']) for a in do_bloco), CONFIANCA_DISTRIBUICAO)


def _quadro_do_cargo(
    config: ConcursoConfig, docs: _Documentos, escopo: _Escopo
) -> _QuadroDeDisciplinas | None:
    """O quadro de disciplinas (FGV) cujo título mais casa com o cargo; no empate, o de "demais"
    especialidades. Sem um vencedor único, nenhum."""
    quadros = _quadros_de_disciplinas(docs)
    if len(quadros) <= 1:
        return quadros[0] if quadros else None
    palavras = _palavras(config.cargo or '') | escopo.nucleo

    def nota(quadro: _QuadroDeDisciplinas) -> tuple[int, bool]:
        do_titulo = _palavras(quadro.titulo)
        return len(do_titulo & palavras), 'DEMAIS' in do_titulo

    maior = max(map(nota, quadros))
    melhores = [q for q in quadros if nota(q) == maior]
    return melhores[0] if maior[0] and len(melhores) == 1 else None


def _quadros_de_disciplinas(docs: _Documentos) -> list[_QuadroDeDisciplinas]:
    quadros = []
    for doc in docs.lista:
        linhas = _linhas(docs.paginas[doc.nome])
        for indice, linha in enumerate(linhas):
            if _CABECALHO_DE_DISCIPLINAS.match(linha) and (quadro := _ler_quadro(doc, linhas, indice)):
                quadros.append(quadro)
    return quadros


def _ler_quadro(doc: _Documento, linhas: list[str], cabecalho: int) -> _QuadroDeDisciplinas | None:
    titulo: list[str] = []
    for anterior in reversed(linhas[max(0, cabecalho - 4) : cabecalho]):
        if _TOTAL_DO_QUADRO.match(anterior):
            break
        titulo.insert(0, anterior)
    gerais: dict[str, int] = {}
    especifico, no_especifico, corpo = None, False, []
    for linha in linhas[cabecalho + 1 : cabecalho + 20]:
        if _TOTAL_DO_QUADRO.match(linha):
            break
        corpo.append(linha)
        if rotulo := _ROTULO_DE_BLOCO.match(linha):
            no_especifico = rotulo['especifico'] is not None
            linha = linha[rotulo.end() :]
        if not (m := _LINHA_DO_QUADRO.match(linha)):
            continue
        if no_especifico:
            especifico = (especifico or 0) + int(m['n'])
        else:
            gerais[m['nome'].strip()] = int(m['n'])
    if not gerais:
        return None
    texto = doc.texto.texto
    match = re.search(_sem_espacos(' '.join([*titulo, linhas[cabecalho]])), texto) or re.search(
        _sem_espacos(linhas[cabecalho]), texto
    )
    trecho = ' '.join([*titulo, linhas[cabecalho], *corpo])
    return _QuadroDeDisciplinas(' '.join(titulo), gerais, especifico, _Achado(match, doc), trecho)


def _por_tipo(docs: _Documentos, escopo: _Escopo, total: int | None) -> Campo:
    tipos: dict[str, int] = {}
    origem = None
    if total is not None:
        for tipo, padrao in (('certo_errado', _CERTO_OU_ERRADO), ('multipla_escolha', _MULTIPLA_ESCOLHA)):
            if achado := docs.primeiro(padrao):
                tipos[tipo], origem = total, achado
                break
    if discursivas := docs.primeiro(_DISCURSIVAS, escopo):
        tipos['discursiva'] = _inteiro(discursivas.match['n'])
        origem = origem or discursivas
    return origem.campo(tipos, CONFIANCA_QUADRO_POR_POSICAO) if origem else Campo()


# --- Cortes ------------------------------------------------------------------------------------------

CONFIANCA_CORTE = 0.9
CONFIANCA_CORTE_DA_DISCURSIVA = 0.8
_CORTE_EM_PONTOS = re.compile(
    rf'nota\s+inferior\s+a\s+(?P<valor>{NUMERO_DECIMAL})\s*pontos,?\s+(?P<alvo>[^;.]{{0,120}})', re.IGNORECASE
)
_CORTE_EM_PONTOS_NA_PROVA = re.compile(
    rf'acertado,?\s+no\s+m[íi]nimo,?\s+(?P<valor>{NUMERO_DECIMAL}){_POR_EXTENSO}\s+pontos\s+na\s+prova\s+de\s+'
    r'(?P<alvo>conhecimentos\s+\w+)',
    re.IGNORECASE,
)
_CORTE_NA_FORMULA = re.compile(
    rf'\bNP\s*<\s*(?P<valor>{NUMERO_DECIMAL})\s*pontos?\s*;?\s*(?P<prova>[12])\b'
    rf'|\bNFPO\s*<\s*(?P<valor_final>{NUMERO_DECIMAL})\s*pontos?'
)
_CORTE_EM_ACERTOS_NO_BLOCO = re.compile(
    rf'acertar,?\s+no\s+m[íi]nimo,?\s+em\s+(?P<alvo>conhecimentos\s+\w+),?\s+'
    rf'(?P<valor>\d+){_POR_EXTENSO}\s+quest'
    rf'|acertar\s+(?P<valor_modulo>\d+){_POR_EXTENSO}\s+quest[õo]es\s+do\s+'
    rf'(?P<modulo>m[óo]dulo\s+[IV]+\b[^;.]{{0,40}})'
    rf'|obtiver\s+(?P<valor_obtiver>\d+){_POR_EXTENSO}\s+acertos\s+em\s+(?P<alvo_obtiver>conhecimentos\s+\w+)',
    re.IGNORECASE,
)
_CORTE_EM_ACERTOS_NO_CONJUNTO = re.compile(
    rf'(?P<valor>\d+){_POR_EXTENSO}\s+acertos\s+nas\s+provas\s+objetivas[^;.]{{0,120}}?'
    r'para\s+os\s+cargos\s+de\s+n[íi]vel\s+\w+',
    re.IGNORECASE,
)
_MINIMO_POR_DISCIPLINA = re.compile(
    rf'n[ãa]o\s+zerar\s+nenhuma\s+das\s+disciplinas'
    rf'|ao\s+menos\s+(?P<valor>\d+){_POR_EXTENSO}\s+quest[ãa]o\s+em\s+cada\s+disciplina'
    rf'(?P<alvo>[^;.]{{0,80}})'
    r'|n[ãa]o\s+(?:tenha\s+obtido|podendo\s+obter)\s+(?:pontua[çc][ãa]o|nota)\s+igual\s+a\s+0,00\s*'
    r'(?:\(zero\))?\s*em\s*qualquer\s*uma\s+das\s+disciplinas',
    re.IGNORECASE,
)
_NOTA_MINIMA = re.compile(
    rf'nota\s+m[íi]nima[^.]{{0,160}}?igual\s+ou\s+superior\s+a\s+(?P<valor>{NUMERO_DECIMAL})', re.IGNORECASE
)
_ESCALA_DE_0_A_10 = re.compile(r'escala\s+de\s+0\s*(?:\(zero\))?\s+a\s+10\b', re.IGNORECASE)
_CORTE_PERCENTUAL = re.compile(
    r'm[íi]nimo,?\s*(?P<valor>\d+(?:,\d+)?)\s*%\s*(?:\([^)]*\))?\s*(?P<alvo>[^;.,]{0,80})', re.IGNORECASE
)
_CORTE_POR_ESCORE = re.compile(
    rf'somat[óo]rio\s+das\s+notas\s+padronizadas[^.]{{0,200}}?igual\s+ou\s+superior\s+a\s+'
    rf'(?P<valor>{NUMERO_DECIMAL})',
    re.IGNORECASE,
)
_CORTE_POR_CLASSIFICADOS = re.compile(
    r'considerad[oa]s\s+aprovad[oa]s\s+nas?\s+provas?\s+objetivas?\s+os\s+candidatos.{0,250}?'
    r'mais\s+bem\s+classificados',
    re.IGNORECASE,
)
_CORTE_DA_DISCURSIVA = re.compile(
    rf'\baprovad[oa]s?\s+n[ao]s?\s+provas?\s+discursivas?[^.]{{0,250}}?'
    rf'(?:≥|igual\s+ou\s+superior\s+a)\s*(?P<valor>{NUMERO_DECIMAL}){_POR_EXTENSO}\s*pontos'
    rf'|\breprovad[oa]s?\s+n[ao]s?\s+provas?\s+discursivas?[^.]{{0,250}}?'
    rf'<\s*(?P<valor_menor>{NUMERO_DECIMAL})\s*pontos',
    re.IGNORECASE,
)
_PADROES_DE_CORTE = (
    _CORTE_EM_PONTOS,
    _CORTE_EM_ACERTOS_NO_BLOCO,
    _CORTE_EM_ACERTOS_NO_CONJUNTO,
    _MINIMO_POR_DISCIPLINA,
    _CORTE_DA_DISCURSIVA,
    _CORTE_EM_PONTOS_NA_PROVA,
    _CORTE_NA_FORMULA,
    _NOTA_MINIMA,
    _CORTE_PERCENTUAL,
    _CORTE_POR_ESCORE,
    _CORTE_POR_CLASSIFICADOS,
)
NAO_CALCULAVEIS = {
    UnidadeCorte.ESCORE_PADRONIZADO: 'escore padronizado',
    UnidadeCorte.CLASSIFICADOS: 'quantidade de classificados',
}
_GATILHOS_DE_DEFAULT = {
    'peso': r'\bPESOS?\b',
    'nota mínima': r'\bNOTA\s+MINIMA\b',
    'corte': r'\bCORTE\b',
    'desempate': r'\bDESEMPATE\b',
    'distribuição': r'\bDISTRIBUICAO\b',
}


def _bloco_citado(alvo: str) -> EscopoCorte | None:
    texto = normalizar(alvo)
    if re.search(r'ESPECIFIC|MODULO\s+II\b', texto):
        return EscopoCorte.ESPECIFICO
    if re.search(r'GERA|BASIC|MODULO\s+I\b', texto):
        return EscopoCorte.GERAL
    return None


def _escopo_em_pontos(alvo: str) -> EscopoCorte | None:
    texto = normalizar(alvo)
    if 'DISCURSIVA' in texto:
        return EscopoCorte.DISCURSIVA
    if 'CONJUNTO' in texto:
        return EscopoCorte.CONJUNTO
    if 'BLOCO' in texto:
        return None
    return _bloco_citado(alvo) or (EscopoCorte.CONJUNTO if 'PROVA OBJETIVA' in texto else None)


def _escopos_do_percentual(alvo: str) -> tuple[EscopoCorte, ...]:
    texto = normalizar(alvo)
    if 'CADA BLOCO' in texto:
        return EscopoCorte.GERAL, EscopoCorte.ESPECIFICO
    if bloco := _bloco_citado(alvo):
        return (bloco,)
    return (EscopoCorte.CONJUNTO,) if 'PROVA OBJETIVA' in texto or 'TOTAL' in texto else ()


def _corte(achado: _Achado, valor: str | None, escopo: EscopoCorte, unidade: UnidadeCorte, **extra) -> Corte:
    confianca = CONFIANCA_CORTE_DA_DISCURSIVA if escopo is EscopoCorte.DISCURSIVA else CONFIANCA_CORTE
    campo = achado.campo(None if valor is None else numero_decimal(valor), confianca)
    return Corte(**vars(campo), escopo=escopo, unidade=unidade, **extra)


def _cortes_do_texto(achado: _Achado) -> list[Corte]:
    m, padrao = achado.match, achado.match.re
    pontos, acertos = UnidadeCorte.PONTOS, UnidadeCorte.ACERTOS
    conjunto = EscopoCorte.CONJUNTO
    if padrao is _CORTE_EM_PONTOS:
        escopo = _escopo_em_pontos(m['alvo'])
        return [_corte(achado, m['valor'], escopo, pontos)] if escopo else []
    if padrao is _CORTE_EM_PONTOS_NA_PROVA:
        escopo = _bloco_citado(m['alvo'])
        return [_corte(achado, m['valor'], escopo, pontos)] if escopo else []
    if padrao is _CORTE_NA_FORMULA:
        if m['valor_final']:
            return [_corte(achado, m['valor_final'], conjunto, pontos)]
        escopo = EscopoCorte.GERAL if m['prova'] == '1' else EscopoCorte.ESPECIFICO
        return [_corte(achado, m['valor'], escopo, pontos)]
    if padrao is _CORTE_EM_ACERTOS_NO_BLOCO:
        escopo = _bloco_citado(m['alvo'] or m['modulo'] or m['alvo_obtiver'])
        valor = m['valor'] or m['valor_modulo'] or m['valor_obtiver']
        return [_corte(achado, valor, escopo, acertos)] if escopo else []
    if padrao is _CORTE_EM_ACERTOS_NO_CONJUNTO:
        return [_corte(achado, m['valor'], conjunto, acertos)]
    if padrao is _MINIMO_POR_DISCIPLINA:
        bloco = _bloco_citado(m['alvo']) if m['alvo'] else None
        return [_corte(achado, m['valor'] or '1', EscopoCorte.DISCIPLINA, acertos, bloco=bloco)]
    if padrao is _NOTA_MINIMA:
        escala = _ESCALA_DE_0_A_10.search(achado.documento.texto.texto)
        return [_corte(achado, m['valor'], conjunto, UnidadeCorte.NOTA_0_10 if escala else pontos)]
    if padrao is _CORTE_PERCENTUAL:
        return [
            _corte(achado, m['valor'], escopo, UnidadeCorte.PERCENTUAL)
            for escopo in _escopos_do_percentual(m['alvo'])
        ]
    if padrao is _CORTE_POR_ESCORE:
        return [_corte(achado, m['valor'], conjunto, UnidadeCorte.ESCORE_PADRONIZADO)]
    if padrao is _CORTE_POR_CLASSIFICADOS:
        return [_corte(achado, None, conjunto, UnidadeCorte.CLASSIFICADOS)]
    return [_corte(achado, m['valor'] or m['valor_menor'], EscopoCorte.DISCURSIVA, pontos)]


def _chave_do_corte(corte: Corte) -> tuple:
    """Um corte calculável por escopo (e bloco); os não calculáveis convivem com ele."""
    if corte.unidade.calculavel:
        return corte.escopo, corte.bloco
    return corte.escopo, corte.bloco, corte.unidade


def _extrair_cortes(
    config: ConcursoConfig, docs: _Documentos, escopo: _Escopo
) -> tuple[tuple[Corte, ...], list[str]]:
    """Todos os cortes do cargo, na ordem do edital; para cada escopo (e bloco), vale o primeiro na ordem de
    busca, de modo que a retificação vence o edital."""
    ordem = {doc.nome: indice for indice, doc in enumerate(docs.lista)}
    lidos = [
        (achado, corte)
        for padrao in _PADROES_DE_CORTE
        for achado in docs.todos(padrao)
        if escopo.aplica(achado)
        for corte in _cortes_do_texto(achado)
    ]

    def na_busca(par: tuple[_Achado, Corte]) -> tuple:
        return ordem[par[0].documento.nome], par[0].match.start()

    def na_leitura(par: tuple[_Achado, Corte]) -> tuple:
        return par[0].documento.retificacao, *na_busca(par)

    vencedores: dict[tuple, Corte] = {}
    for _, corte in sorted(lidos, key=na_busca):
        vencedores.setdefault(_chave_do_corte(corte), corte)
    chaves = dict.fromkeys(_chave_do_corte(corte) for _, corte in sorted(lidos, key=na_leitura))
    cortes = {chave: vencedores[chave] for chave in chaves}
    avisos = [
        f'{config.nome}: corte por {NAO_CALCULAVEIS[corte.unidade]} não calculável localmente; '
        'fica fora do "atingido"'
        for corte in cortes.values()
        if not corte.unidade.calculavel
    ]
    declarado = config.correcao.nota_corte if config.correcao else None
    conjunto = cortes.get((EscopoCorte.CONJUNTO, None))
    if declarado is not None and conjunto is None:
        cortes[(EscopoCorte.CONJUNTO, None)] = Corte(
            declarado,
            FonteRegra.CONFIG,
            confianca_extracao=1.0,
            escopo=EscopoCorte.CONJUNTO,
            unidade=UnidadeCorte.PONTOS,
        )
    elif declarado is not None and conjunto.valor != declarado:
        avisos.append(
            f'{config.nome}: nota de corte do concurso.yaml ({declarado:g}) difere da do edital '
            f'({conjunto.valor:g} {conjunto.unidade}); vale o edital'
        )
    if not cortes:
        avisos.append(_aviso_de_default(config, docs, 'nenhuma nota de corte no edital nem no concurso.yaml'))
    return tuple(cortes.values()), avisos


# --- Formato, alternativas e penalidade -------------------------------------------------------------

CONFIANCA_FORMATO = 0.9
CONFIANCA_FORMATO_PELAS_ALTERNATIVAS = 0.7
CONFIANCA_ALTERNATIVAS = 0.9
_ALTERNATIVAS = re.compile(
    r'(?:(?P<numero>\d{1,2})\s*(?:\([a-zç]+\))?|(?P<extenso>quatro|cinco))\s*(?:alternativas|opções)\b',
    re.IGNORECASE,
)


def _extrair_prova(config: ConcursoConfig, docs: _Documentos, escopo: _Escopo) -> Prova:
    alternativas_do_edital = docs.primeiro(_ALTERNATIVAS, escopo)
    if achado := docs.primeiro(_CERTO_OU_ERRADO, escopo):
        formato = achado.campo(Formato.CERTO_ERRADO.value, CONFIANCA_FORMATO)
    elif achado := docs.primeiro(_MULTIPLA_ESCOLHA, escopo):
        formato = achado.campo(Formato.MULTIPLA_ESCOLHA.value, CONFIANCA_FORMATO)
    elif alternativas_do_edital:
        formato = alternativas_do_edital.campo(
            Formato.MULTIPLA_ESCOLHA.value, CONFIANCA_FORMATO_PELAS_ALTERNATIVAS
        )
    else:
        formato = Campo(config.formato.value, FonteRegra.CONFIG, confianca_extracao=CONFIANCA_CONFIG)
    return Prova(
        formato,
        _alternativas(config, formato.valor, alternativas_do_edital),
        _penalidade(config, docs),
    )


def _alternativas(config: ConcursoConfig, formato: str, achado: _Achado | None) -> Campo:
    if formato == Formato.CERTO_ERRADO:
        return Campo()
    if achado is not None:
        m = achado.match
        numero = int(m['numero']) if m['numero'] else _POR_EXTENSO_NUMERO[normalizar(m['extenso'])]
        return achado.campo(numero, CONFIANCA_ALTERNATIVAS)
    if config.alternativas is not None:
        return Campo(config.alternativas, FonteRegra.CONFIG, confianca_extracao=CONFIANCA_CONFIG)
    perfil = perfil_da_banca(config.banca)
    if perfil.id != PERFIL_GENERICO and perfil.alternativas is not None:
        return Campo(perfil.alternativas, FonteRegra.PERFIL, confianca_extracao=CONFIANCA_PERFIL)
    return Campo(ALTERNATIVAS_PADRAO)


def _penalidade(config: ConcursoConfig, docs: _Documentos) -> Campo:
    if achada := _regra_de_correcao(config, docs):
        doc, regra = achada
        return _campo_da_regra(regra.fator_penalidade, doc, regra)
    if config.correcao is not None and config.correcao.fator_penalidade is not None:
        return Campo(config.correcao.fator_penalidade, FonteRegra.CONFIG, confianca_extracao=CONFIANCA_CONFIG)
    if (fator := penalidade_do_perfil(config)) is not None:
        return Campo(fator, FonteRegra.PERFIL, confianca_extracao=CONFIANCA_PERFIL)
    return Campo(0.0)


# --- Cronograma --------------------------------------------------------------------------------------

_MESES = (
    'janeiro',
    'fevereiro',
    'março',
    'abril',
    'maio',
    'junho',
    'julho',
    'agosto',
    'setembro',
    'outubro',
    'novembro',
    'dezembro',
)
_DATA = r'(?P<dia>\d{1,2})/(?P<mes>\d{1,2})/(?P<ano>\d{4})'
_DATA_POR_EXTENSO = rf'(?P<dia>\d{{1,2}})\s+de\s+(?P<mes>{"|".join(_MESES)})\s+de\s+(?P<ano>\d{{4}})'
_COM_A_DISCURSIVA = r'(?P<discursiva>\s+e\s+(?:a\s+|da\s+)?(?:prova\s+)?discursivas?)?'
_APLICACAO_DA_OBJETIVA = (
    re.compile(rf'Aplicação\s+d[ao]s?\s+provas?\s+objetivas?{_COM_A_DISCURSIVA}\.?\s+{_DATA}', re.I),
    re.compile(
        rf'Prova\s+Objetiva{_COM_A_DISCURSIVA}[^.]{{0,160}}?ser(?:á|ão)\s+realizad[ao]s?[^.]{{0,80}}?'
        rf'\bno\s+dia\s+{_DATA_POR_EXTENSO}',
        re.I,
    ),
)
_APLICACAO_DA_DISCURSIVA = re.compile(rf'Aplicação\s+da\s+prova\s+discursiva\.?\s+{_DATA}', re.I)


def _resultado_da_objetiva(nome: str) -> tuple[re.Pattern, ...]:
    """A data depois da atividade ou no meio dela, quando a célula do anexo quebra entre "provas" e
    "objetivas"."""
    return (
        re.compile(rf'{nome}\s+(?:nas?|das?)\s+provas?\s+objetivas?\D{{0,120}}?{_DATA}', re.I),
        re.compile(rf'{nome}\s+(?:nas?|das?)\s+provas?\s+{_DATA}\s+objetivas?', re.I),
    )


_RESULTADO_PRELIMINAR = _resultado_da_objetiva(
    r'(?:resultado\s+(?:preliminar|provisório)|notas\s+preliminares)'
)
_RESULTADO_FINAL = _resultado_da_objetiva(r'(?:resultado\s+final|notas\s+finais)')
_RECURSO_CONTRA_O_GABARITO = re.compile(
    r'recursos\s+quanto\s+às\s+(?:questões\s+formuladas\s+)?'
    r'(?P<dia1>\d{1,2})(?:/(?P<mes1>\d{1,2}))?\s+[ae]\s+(?P<dia>\d{1,2})/(?P<mes>\d{1,2})/(?P<ano>\d{4})',
    re.I,
)


def _extrair_cronograma(config: ConcursoConfig, docs: _Documentos) -> tuple[Cronograma, list[str]]:
    """Datas do cronograma (anexo do Cebraspe e do CPNU) ou do texto ("será realizada … no dia 12 de outubro
    de 2025", FGV); nenhuma é imputada."""
    objetiva = discursiva = Campo()
    no_mesmo_dia = None
    if (achado := _primeira_data(docs, *_APLICACAO_DA_OBJETIVA)) is not None:
        objetiva = achado.campo(_data(achado.match), CONFIANCA_DISTRIBUICAO)
        if achado.match['discursiva']:
            discursiva, no_mesmo_dia = objetiva, True
    if no_mesmo_dia is None and (achado := _primeira_data(docs, _APLICACAO_DA_DISCURSIVA)) is not None:
        discursiva = achado.campo(_data(achado.match), CONFIANCA_DISTRIBUICAO)
        no_mesmo_dia = discursiva.valor == objetiva.valor
    preliminar, final = (
        achado.campo(_data(achado.match), CONFIANCA_DISTRIBUICAO) if achado else Campo()
        for achado in (_primeira_data(docs, *_RESULTADO_PRELIMINAR), _primeira_data(docs, *_RESULTADO_FINAL))
    )
    recurso = Campo()
    if (achado := _primeira_data(docs, _RECURSO_CONTRA_O_GABARITO)) is not None:
        m, fim = achado.match, _data(achado.match)
        inicio = data_valida(int(m['dia1']), int(m['mes1'] or m['mes']), int(m['ano']))
        if inicio is not None:
            recurso = achado.campo({'inicio': inicio, 'fim': fim}, CONFIANCA_DISTRIBUICAO)
    cronograma = Cronograma(objetiva, discursiva, preliminar, final, recurso, no_mesmo_dia)
    nomes = {
        'objetiva': objetiva,
        'discursiva': discursiva,
        'resultado preliminar': preliminar,
        'resultado final': final,
        'recurso': recurso,
    }
    ausentes = [nome for nome, campo in nomes.items() if campo.valor is None]
    if not ausentes:
        return cronograma, []
    return cronograma, [
        f'{config.nome}: cronograma do edital sem data de {", ".join(ausentes)}; ficam vazias'
    ]


def _primeira_data(docs: _Documentos, *padroes: re.Pattern) -> _Achado | None:
    """O primeiro padrão com uma data válida vence."""
    achados = (a for padrao in padroes for a in docs.todos(padrao))
    return next((a for a in achados if _data(a.match) is not None), None)


def _data(match: re.Match) -> date | None:
    mes = match['mes']
    numero = int(mes) if mes.isdigit() else _MESES.index(mes.lower()) + 1
    return data_valida(int(match['dia']), numero, int(match['ano']))


# --- Descoberta dirigida -----------------------------------------------------------------------------


def _extrair_metadados(
    docs: _Documentos, escopo: _Escopo, derivados: dict[str, Campo]
) -> tuple[Metadado, ...]:
    """Um metadado por candidato do registro, na ordem dele; os sem padrão vêm de `derivados`."""
    return tuple(
        _derivado(candidato, derivados.get(candidato.chave, Campo()))
        if not candidato.padroes
        else _descobrir(candidato, docs, escopo)
        for candidato in CANDIDATOS
    )


def _descobrir(candidato: Candidato, docs: _Documentos, escopo: _Escopo) -> Metadado:
    padroes = [re.compile(p, re.IGNORECASE) for p in candidato.padroes]
    achados = [a for padrao in padroes for a in docs.todos(padrao) if escopo.aplica(a)]
    achados = [a for a in achados if a.documento.retificacao] or achados
    if not achados:
        return Metadado(chave=candidato.chave, status=StatusExtracao.NAO_ENCONTRADO)
    valores = list(dict.fromkeys(_valor_descoberto(a.match) for a in achados))
    ambiguo = candidato.unico and len(valores) > 1
    campo = achados[0].campo(valores if ambiguo else valores[0], CONFIANCA_DESCOBERTA)
    status = StatusExtracao.AMBIGUO if ambiguo else StatusExtracao.ENCONTRADO
    return _metadado(candidato, campo, status)


def _derivado(candidato: Candidato, campo: Campo) -> Metadado:
    if campo.valor is None:
        return Metadado(chave=candidato.chave, status=StatusExtracao.NAO_ENCONTRADO)
    return _metadado(candidato, campo, StatusExtracao.ENCONTRADO)


def _metadado(candidato: Candidato, campo: Campo, status: StatusExtracao) -> Metadado:
    fonte = FonteRegra.RETIFICACAO if campo.fonte is FonteRegra.RETIFICACAO else FonteRegra.DESCOBERTA
    origem = {f.name: getattr(campo, f.name) for f in fields(Campo)}
    return Metadado(**{**origem, 'fonte': fonte}, chave=candidato.chave, status=status)


def _valor_descoberto(match: re.Match) -> Any:
    """Sem zeros à esquerda, para que "02 (dois) anos" e "2 (dois) anos" sejam o mesmo valor."""
    valor = ' '.join(match['valor' if 'valor' in match.re.groupindex else 0].split())
    valor = re.sub(r'\b0+(?=\d)', '', valor)
    return int(valor) if valor.isdigit() else valor


_DESEMPATE = re.compile(
    r'empate[^.]{0,200}?ter[áa]\s+prefer[êe]ncia\s+[oa]\s+(?:pessoa\s+)?candidat[oa]\s+que,?\s+'
    r'na\s+seguinte\s+ordem:\s*(?P<lista>.{1,2000}?)'
    r'(?=(?-i:\s\d{1,2}(?:\.\d{1,2})+\.?\s+[A-ZÀ-Ý]|\s\d{1,2}\s+D[AEO]S?\s+[A-ZÀ-Ý])|$)',
    re.IGNORECASE,
)
_ALINEA = re.compile(r'(?<!\w)(?P<letra>[a-z])\)\s+')
_PROVA_SUBSCRITA = re.compile(r'\(?\bP\s*\)?\s*[;.]?\s*(?P<numero>\d)$')
"""O "(P₂)" do Cebraspe vira "(P ); 2" na extração do PDF: o subscrito cai depois da pontuação."""
_FIM_DA_ALINEA = re.compile(r'(?:[;,]\s*e)?[\s;.,]*$')


def _extrair_desempate(docs: _Documentos, escopo: _Escopo) -> Campo:
    """Os critérios na ordem das alíneas, sem cálculo."""
    achado = docs.primeiro(_DESEMPATE, escopo)
    if achado is None:
        return Campo()
    criterios = _alineas(achado.match['lista'])
    return achado.campo(criterios, CONFIANCA_DESCOBERTA) if criterios else Campo()


def _alineas(lista: str) -> list[str]:
    """Só as alíneas em sequência (a, b, c…): uma letra fora da sequência é texto da alínea anterior."""
    marcas, esperada = [], 'a'
    for marca in _ALINEA.finditer(lista):
        if marca['letra'] == esperada:
            marcas.append(marca)
            esperada = chr(ord(esperada) + 1)
    fins = [m.start() for m in marcas[1:]] + [len(lista)]
    criterios = []
    for marca, fim in zip(marcas, fins, strict=True):
        criterio = _FIM_DA_ALINEA.sub('', lista[marca.end() : fim].strip())
        criterio = _PROVA_SUBSCRITA.sub(r'(P\g<numero>)', criterio)
        criterios.append(_FIM_DA_ALINEA.sub('', criterio))
    return criterios


def _derivados(
    identificacao: Identificacao, pesos: Pesos, cortes: tuple[Corte, ...], desempate: Campo
) -> dict[str, Campo]:
    ponderada = pesos.tipo.valor in {TipoPeso.POR_FAIXA_DE_ITENS, TipoPeso.POR_BLOCO}
    em_acertos = next((c for c in cortes if c.unidade is UnidadeCorte.ACERTOS), None)
    derivados = {
        'teto_de_classificados': identificacao.teto_classificados,
        'soma_dos_pesos_dos_eixos': pesos.soma_dos_eixos,
        'desempate': desempate,
    }
    if ponderada and em_acertos is not None:
        derivados['corte_em_acertos_com_nota_ponderada'] = em_acertos
    return derivados


def _aviso_de_default(config: ConcursoConfig, docs: _Documentos, motivo: str) -> str:
    texto = ' '.join(normalizar(doc.texto.texto) for doc in docs.lista)
    gatilhos = [nome for nome, padrao in _GATILHOS_DE_DEFAULT.items() if re.search(padrao, texto)]
    if not gatilhos:
        return f'{config.nome}: {motivo}'
    return f'{config.nome}: {motivo}, embora o edital mencione {", ".join(gatilhos)}; confira à mão'


# --- Extração ----------------------------------------------------------------------------------------


def extrair_regras(
    config: ConcursoConfig,
    documentos: dict[str, list[str]],
    retificacoes: dict[str, list[str]] | None = None,
) -> RegrasEdital:
    """Regras do edital do cargo do concurso. `documentos` são as páginas do edital e dos anexos, na ordem de
    leitura; as `retificacoes`, na ordem de publicação, vencem o edital campo a campo."""
    docs = _Documentos(documentos, retificacoes)
    identificacao, escopo, avisos = _identificar(config, docs)
    pesos, avisos_dos_pesos = _extrair_pesos(config, docs)
    distribuicao, avisos_da_distribuicao = _extrair_distribuicao(config, docs, escopo)
    cortes, avisos_dos_cortes = _extrair_cortes(config, docs, escopo)
    cronograma, avisos_do_cronograma = _extrair_cronograma(config, docs)
    derivados = _derivados(identificacao, pesos, cortes, _extrair_desempate(docs, escopo))
    metadados = _extrair_metadados(docs, escopo, derivados)
    avisos += avisos_dos_pesos + avisos_da_distribuicao + avisos_dos_cortes + avisos_do_cronograma
    for aviso in avisos:
        logger.warning('%s', aviso)
    regras = RegrasEdital(
        identificacao,
        pesos,
        distribuicao,
        cortes,
        cronograma,
        metadados,
        prova=_extrair_prova(config, docs, escopo),
        avisos=tuple(avisos),
    )
    return replace(regras, confianca_edital=confianca_do_edital(regras))


def ler_regras(pasta: Path) -> dict | None:
    """As regras gravadas no edital estruturado de um concurso analisado, como dicionário."""
    caminho = pasta / ARQUIVO_EDITAL_ESTRUTURADO
    if not caminho.exists():
        return None
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    return dados if 'identificacao' in dados else None
