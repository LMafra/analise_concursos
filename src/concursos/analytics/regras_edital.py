"""Regras do edital além do conteúdo programático: identificação, pesos, distribuição, cortes, cronograma e
metadados, cada valor com fonte, trecho, documento e página. Extração por regex, sem LLM."""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from concursos.analytics.correcao import TextoCorrido
from concursos.concurso_config import ConcursoConfig
from concursos.deteccao import normalizar
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO, titulo_legivel
from concursos.modelo import Escolaridade

logger = logging.getLogger(__name__)

CHAVES_DAS_REGRAS = ('identificacao', 'cortes', 'avisos')
CONFIANCA_LISTA_DE_CARGOS = 0.9
CONFIANCA_CARGO_UNICO = 0.85
CONFIANCA_NOME_DO_CARGO = 0.75
CONFIANCA_CAPA = 0.8
CONFIANCA_SEM_CASAMENTO = 0.5
_COBERTURA_MINIMA_CARGO = 0.75
_JANELA_DE_CARGO = 600
_JANELA_DE_ITEM = 4000


class FonteRegra(StrEnum):
    RETIFICACAO = 'retificacao'
    EDITAL = 'edital'
    CONFIG = 'config'
    DEFAULT = 'default'
    DESCOBERTA = 'descoberta'


@dataclass(frozen=True)
class Campo:
    """Um valor do edital com a sua origem; sem origem no texto, a fonte é `config` ou `default`."""

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


@dataclass(frozen=True, kw_only=True)
class Corte(Campo):
    """Um mínimo eliminatório. No escopo `disciplina`, `bloco` diz de que bloco são as disciplinas (vazio:
    todas); a `discursiva` é só informativa."""

    escopo: EscopoCorte
    unidade: UnidadeCorte
    bloco: EscopoCorte | None = None


@dataclass(frozen=True)
class RegrasEdital:
    identificacao: Identificacao = field(default_factory=Identificacao)
    cortes: tuple[Corte, ...] = ()
    avisos: tuple[str, ...] = ()

    def gravar_json(self, caminho: Path) -> None:
        """Grava as regras no edital estruturado, preservando o conteúdo programático já gravado."""
        dados = json.loads(caminho.read_text(encoding='utf-8')) if caminho.exists() else {}
        dados.update(json.loads(json.dumps(asdict(self), ensure_ascii=False, default=str)))
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')


@dataclass(frozen=True)
class _Documento:
    nome: str
    texto: TextoCorrido
    retificacao: bool = False


@dataclass(frozen=True)
class _Achado:
    match: re.Match
    documento: _Documento

    def campo(self, valor: Any, confianca: float, trecho: str | None = None) -> Campo:
        texto = self.documento.texto
        return Campo(
            valor,
            FonteRegra.RETIFICACAO if self.documento.retificacao else FonteRegra.EDITAL,
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
        return next((a for a in self.todos(padrao) if escopo is None or escopo.aplica(a)), None)


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
    """Fração das palavras de `nome` presentes em `palavras`."""
    do_nome = _palavras(nome)
    return len(do_nome & palavras) / len(do_nome) if do_nome else 0.0


@dataclass(frozen=True)
class _Escopo:
    """Decide se um trecho vale para o cargo: pela última menção a cargos antes dele (ou no próprio
    trecho)."""

    palavras: frozenset[str]
    escolaridade: Escolaridade = Escolaridade.NAO_INFORMADO

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
        return _cobertura(nome, set(self.palavras)) == 1.0


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
    escopo = _Escopo(frozenset(palavras), config.escolaridade)
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
                achado = _Achado(re.search(re.escape(linha[:25]), doc.texto.texto), doc)
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
    padrao = re.compile(rf'(?:CARGO|EMPREGO)\s+{numero}\s*:\s*{re.escape(partes[0][:30])}')
    match = padrao.search(doc.texto.texto) or re.search(re.escape(partes[0][:20]), doc.texto.texto)
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
            if _maiusculo(linha) and not _NAO_E_ORGAO.match(linha) and len(linha.split()) >= 2:
                if indice + 1 < len(linhas) and re.fullmatch(r'\([^)]+\)', linhas[indice + 1]):
                    linha = f'{linha} {linhas[indice + 1]}'
                match = re.search(re.escape(linha.split()[0]), doc.texto.texto)
                return _Achado(match, doc).campo(_titulo_com_siglas(linha), CONFIANCA_CAPA, linha)
    if achado := docs.primeiro(_ORGAO_NO_TEXTO):
        return achado.campo(achado.match['orgao'].strip(), CONFIANCA_NOME_DO_CARGO)
    return Campo()


def _linha_do_edital(docs: _Documentos) -> Campo:
    for doc in reversed(docs.lista):
        if match := _LINHA_DE_EDITAL.search('\n'.join(_linhas(docs.paginas[doc.nome][:1]))):
            linha = match[0].strip()
            achado = _Achado(re.search(re.escape(linha[:20]), doc.texto.texto), doc)
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


def _linhas(paginas: list[str]) -> list[str]:
    return [linha.strip() for pagina in paginas for linha in pagina.splitlines() if linha.strip()]


def _maiusculo(texto: str) -> bool:
    letras = [c for c in texto if c.isalpha()]
    return len(letras) >= 4 and sum(c.isupper() for c in letras) >= 0.9 * len(letras)


# --- Cortes ------------------------------------------------------------------------------------------

CONFIANCA_CORTE = 0.9
CONFIANCA_CORTE_DA_DISCURSIVA = 0.8
_NUMERO = r'\d+(?:,\d+)?'
_POR_EXTENSO = r'(?:\s*\([^)]*\))?'
_CORTE_EM_PONTOS = re.compile(
    rf'nota\s+inferior\s+a\s+(?P<valor>{_NUMERO})\s*pontos\s+(?P<alvo>[^;.]{{0,120}})', re.IGNORECASE
)
_CORTE_EM_ACERTOS_NO_BLOCO = re.compile(
    rf'acertar,?\s+no\s+m[íi]nimo,?\s+em\s+(?P<alvo>conhecimentos\s+\w+),?\s+'
    rf'(?P<valor>\d+){_POR_EXTENSO}\s+quest'
    rf'|acertar\s+(?P<valor_modulo>\d+){_POR_EXTENSO}\s+quest[õo]es\s+do\s+'
    rf'(?P<modulo>m[óo]dulo\s+[IV]+\b[^;.]{{0,40}})',
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
    rf'(?P<alvo>[^;.]{{0,80}})',
    re.IGNORECASE,
)
_CORTE_DA_DISCURSIVA = re.compile(
    rf'\baprovad[oa]s?\s+n[ao]s?\s+provas?\s+discursivas?[^.]{{0,250}}?'
    rf'(?:≥|igual\s+ou\s+superior\s+a)\s*(?P<valor>{_NUMERO}){_POR_EXTENSO}\s*pontos'
    rf'|\breprovad[oa]s?\s+n[ao]s?\s+provas?\s+discursivas?[^.]{{0,250}}?'
    rf'<\s*(?P<valor_menor>{_NUMERO})\s*pontos',
    re.IGNORECASE,
)
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


def _corte(achado: _Achado, valor: str, escopo: EscopoCorte, unidade: UnidadeCorte, **extra) -> Corte:
    confianca = CONFIANCA_CORTE_DA_DISCURSIVA if escopo is EscopoCorte.DISCURSIVA else CONFIANCA_CORTE
    campo = achado.campo(float(valor.replace(',', '.')), confianca)
    return Corte(**vars(campo), escopo=escopo, unidade=unidade, **extra)


def _cortes_do_texto(achado: _Achado) -> Corte | None:
    m, padrao = achado.match, achado.match.re
    pontos, acertos = UnidadeCorte.PONTOS, UnidadeCorte.ACERTOS
    if padrao is _CORTE_EM_PONTOS:
        escopo = _escopo_em_pontos(m['alvo'])
        return _corte(achado, m['valor'], escopo, pontos) if escopo else None
    if padrao is _CORTE_EM_ACERTOS_NO_BLOCO:
        escopo = _bloco_citado(m['alvo'] or m['modulo'])
        return _corte(achado, m['valor'] or m['valor_modulo'], escopo, acertos) if escopo else None
    if padrao is _CORTE_EM_ACERTOS_NO_CONJUNTO:
        return _corte(achado, m['valor'], EscopoCorte.CONJUNTO, acertos)
    if padrao is _MINIMO_POR_DISCIPLINA:
        bloco = _bloco_citado(m['alvo']) if m['alvo'] else None
        return _corte(achado, m['valor'] or '1', EscopoCorte.DISCIPLINA, acertos, bloco=bloco)
    return _corte(achado, m['valor'] or m['valor_menor'], EscopoCorte.DISCURSIVA, pontos)


def _extrair_cortes(
    config: ConcursoConfig, docs: _Documentos, escopo: _Escopo
) -> tuple[tuple[Corte, ...], list[str]]:
    """Todos os cortes do cargo, na ordem do edital; para cada escopo (e bloco), vale o primeiro na ordem de
    busca, de modo que a retificação vence o edital."""
    padroes = (
        _CORTE_EM_PONTOS,
        _CORTE_EM_ACERTOS_NO_BLOCO,
        _CORTE_EM_ACERTOS_NO_CONJUNTO,
        _MINIMO_POR_DISCIPLINA,
        _CORTE_DA_DISCURSIVA,
    )
    ordem = {doc.nome: indice for indice, doc in enumerate(docs.lista)}
    achados = sorted(
        (a for padrao in padroes for a in docs.todos(padrao) if escopo.aplica(a)),
        key=lambda a: (ordem[a.documento.nome], a.match.start()),
    )
    cortes: dict[tuple, Corte] = {}
    for achado in achados:
        if (corte := _cortes_do_texto(achado)) and (chave := (corte.escopo, corte.bloco)) not in cortes:
            cortes[chave] = corte
    avisos = []
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
    cortes, avisos_dos_cortes = _extrair_cortes(config, docs, escopo)
    avisos += avisos_dos_cortes
    for aviso in avisos:
        logger.warning('%s', aviso)
    return RegrasEdital(identificacao, cortes, tuple(avisos))


def ler_regras(pasta: Path) -> dict | None:
    """As regras gravadas no edital estruturado de um concurso analisado, como dicionário."""
    caminho = pasta / ARQUIVO_EDITAL_ESTRUTURADO
    if not caminho.exists():
        return None
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    return dados if 'identificacao' in dados else None
