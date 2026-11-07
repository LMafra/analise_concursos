"""Normas citadas nos tópicos do edital e o arquivo de cada uma num clone local do `ctresb/leis`."""

import json
import logging
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from concursos.config.contexto import ler_toml
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO
from concursos.erros import avisar

logger = logging.getLogger(__name__)

SECAO = 'legislacao'
TAMANHO_MINIMO_NORMA = 8 * 1024
"""Abaixo disso, uma lei ou decreto provavelmente traz só parte do texto (caso da 14.133 no clone)."""
FONTE_CONSTITUICAO = 'https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm'
URL_CLONE = 'https://github.com/ctresb/leis.git'
DICA_CLONE = 'atualize o clone com `git pull` ou inclua a pasta no `git sparse-checkout`'


class TipoNorma(StrEnum):
    LEI = 'lei'
    LEI_COMPLEMENTAR = 'lei_complementar'
    DECRETO = 'decreto'
    EMENDA_CONSTITUCIONAL = 'emenda_constitucional'
    SUMULA_VINCULANTE = 'sumula_vinculante'
    SUMULA_TCU = 'sumula_tcu'
    CONSTITUICAO = 'constituicao'


_PASTAS = {
    TipoNorma.LEI: 'federal/leis-ordinarias',
    TipoNorma.LEI_COMPLEMENTAR: 'federal/leis-complementares',
    TipoNorma.DECRETO: 'federal/decretos',
    TipoNorma.EMENDA_CONSTITUCIONAL: 'federal/emendas-constitucionais',
}
_ROTULOS = {
    TipoNorma.LEI: 'Lei',
    TipoNorma.LEI_COMPLEMENTAR: 'Lei Complementar',
    TipoNorma.DECRETO: 'Decreto',
    TipoNorma.EMENDA_CONSTITUCIONAL: 'Emenda Constitucional',
    TipoNorma.SUMULA_VINCULANTE: 'Súmula Vinculante',
    TipoNorma.SUMULA_TCU: 'Súmula do TCU',
    TipoNorma.CONSTITUICAO: 'Constituição Federal',
}


@dataclass(frozen=True)
class Citacao:
    tipo: TipoNorma
    numero: str | None
    ano: int | None
    trecho: str

    @property
    def rotulo(self) -> str:
        if self.tipo is TipoNorma.CONSTITUICAO:
            return _ROTULOS[self.tipo]
        ano = f'/{self.ano}' if self.ano else ''
        return f'{_ROTULOS[self.tipo]} nº {self.numero}{ano}'


@dataclass(frozen=True)
class Norma:
    caminho: Path
    relativo: str
    titulo: str
    ementa: str | None
    urn: str | None
    fonte: str | None
    versao_texto: str | None
    revogada: bool
    tamanho: int
    tipo: TipoNorma

    @property
    def chave(self) -> str:
        return self.urn or self.relativo


_NUMERO = r'(?:N\.?\s?[O°]\.?\s*)?(\d{1,3}(?:\.\d{3})+|\d+)'
_ANO = r'(?:\s*[/_-]\s*(\d{4}|\d{2})\b|,?\s+DE\s+\d{1,2}[O°]?\s+DE\s+[A-Z]+\s+DE\s+(\d{4}))?'
_ITEM = re.compile(_NUMERO + _ANO)
_SEPARADOR = re.compile(r'\s*(?:,|\bE\b)\s*')
_TIPOS = re.compile(
    r'\b(?P<tipo>LEIS?\s+COMPLEMENTAR(?:ES)?|LEIS?(?:\s+FEDERA(?:L|IS))?|DECRETOS?(?:-LEI)?'
    r'|EMENDAS?\s+CONSTITUCIONA(?:L|IS))\s+(?=(?:N\.?\s?[O°]\.?\s*)?\d)'
)
_SUMULA_VINCULANTE = re.compile(r'\bSUMULAS?\s+VINCULANTES?\s+' + _NUMERO)
_SUMULA_TCU = re.compile(
    r'\bSUMULAS?\s+(?:DO\s+)?TCU\s+' + _NUMERO + r'|\bSUMULAS?\s+' + _NUMERO + r'\s+DO\s+TCU\b'
)
_CONSTITUICAO = re.compile(
    r'\bCONSTITUICAO\s+(?:DA\s+REPUBLICA\s+|FEDERAL\b)|\bCF\s*/\s*(?:88|1988)\b|\bCRFB\b'
)


def extrair_citacoes(texto: str) -> list[Citacao]:
    """As normas federais citadas em `texto`, na ordem em que aparecem e sem repetição.

    "Decreto Legislativo" fica de fora: não é decreto do Executivo e não está no clone.
    """
    dobrado = _dobrar(texto)
    achadas: list[tuple[int, Citacao]] = []
    for casamento in _TIPOS.finditer(dobrado):
        tipo = _tipo(casamento.group('tipo'))
        if tipo is TipoNorma.DECRETO and 'LEI' in casamento.group('tipo'):
            continue
        posicao = casamento.end()
        while item := _ITEM.match(dobrado, posicao):
            numero, ano = _numero(item.group(1)), _ano(item.group(2) or item.group(3))
            achadas.append(
                (item.start(), Citacao(tipo, numero, ano, _trecho(texto, casamento.start(), item.end())))
            )
            separador = _SEPARADOR.match(dobrado, item.end())
            seguinte = separador and _ITEM.match(dobrado, separador.end())
            if not seguinte or not (seguinte.group(2) or seguinte.group(3)):
                break
            posicao = separador.end()
    for casamento in _SUMULA_VINCULANTE.finditer(dobrado):
        citacao = Citacao(
            TipoNorma.SUMULA_VINCULANTE, _numero(casamento.group(1)), None, _trecho(texto, *casamento.span())
        )
        achadas.append((casamento.start(), citacao))
    for casamento in _SUMULA_TCU.finditer(dobrado):
        numero = _numero(casamento.group(1) or casamento.group(2))
        achadas.append(
            (
                casamento.start(),
                Citacao(TipoNorma.SUMULA_TCU, numero, None, _trecho(texto, *casamento.span())),
            )
        )
    for casamento in _CONSTITUICAO.finditer(dobrado):
        achadas.append(
            (
                casamento.start(),
                Citacao(TipoNorma.CONSTITUICAO, None, None, _trecho(texto, *casamento.span())),
            )
        )
    unicas: dict[tuple, Citacao] = {}
    for _posicao, citacao in sorted(achadas, key=lambda par: par[0]):
        unicas.setdefault((citacao.tipo, citacao.numero, citacao.ano), citacao)
    return list(unicas.values())


def _dobrar(texto: str) -> str:
    """Sem acento e em maiúsculas, com o mesmo comprimento do original, para o trecho sair do texto real."""
    letras = []
    for caractere in texto:
        base = ''.join(c for c in unicodedata.normalize('NFKD', caractere) if not unicodedata.combining(c))
        letras.append((base or caractere)[0].upper()[0])
    return ''.join(letras)


def _tipo(texto: str) -> TipoNorma:
    if 'COMPLEMENTAR' in texto:
        return TipoNorma.LEI_COMPLEMENTAR
    if texto.startswith('DECRETO'):
        return TipoNorma.DECRETO
    if texto.startswith('EMENDA'):
        return TipoNorma.EMENDA_CONSTITUCIONAL
    return TipoNorma.LEI


def _numero(texto: str) -> str:
    return texto.replace('.', '').lstrip('0') or '0'


def _ano(texto: str | None) -> int | None:
    if not texto:
        return None
    ano = int(texto)
    if len(texto) == 2:
        ano += 1900 if ano > 30 else 2000
    return ano


def _trecho(texto: str, inicio: int, fim: int) -> str:
    return ' '.join(texto[inicio:fim].split())


def citacoes_do_edital(pasta_analise: Path) -> list[Citacao]:
    """As citações dos tópicos do `edital_estruturado.json` de um concurso; vazio sem o arquivo."""
    caminho = pasta_analise / ARQUIVO_EDITAL_ESTRUTURADO
    if not caminho.exists():
        return []
    edital = json.loads(caminho.read_text(encoding='utf-8'))
    textos = (
        topico['nome']
        for conhecimento in edital.get('conhecimentos', [])
        for disciplina in conhecimento.get('disciplinas', [])
        for topico in disciplina.get('topicos', [])
    )
    return _sem_repeticao(c for texto in textos for c in extrair_citacoes(texto))


def _sem_repeticao(citacoes: Iterable[Citacao]) -> list[Citacao]:
    unicas: dict[tuple, Citacao] = {}
    for citacao in citacoes:
        unicas.setdefault((citacao.tipo, citacao.numero, citacao.ano), citacao)
    return list(unicas.values())


def ler_repositorio(config_global: Path) -> Path | None:
    """`[legislacao] repositorio` da configuração global (um caminho desta máquina); None sem a seção."""
    valor = ler_toml(config_global).get(SECAO, {}).get('repositorio')
    return Path(valor).expanduser() if valor else None


def resolver(citacao: Citacao, repositorio: Path) -> Norma | None:
    """O arquivo da norma no clone, ou None quando ele não está lá."""
    caminho = _arquivo(citacao, repositorio)
    return _ler_norma(caminho, repositorio, citacao.tipo) if caminho else None


def _arquivo(citacao: Citacao, repositorio: Path) -> Path | None:
    if citacao.tipo is TipoNorma.CONSTITUICAO:
        caminho = repositorio / 'constituicao.md'
        return caminho if caminho.exists() else None
    if citacao.tipo is TipoNorma.SUMULA_VINCULANTE:
        caminho = (
            repositorio / f'jurisprudencia/stf/sumulas-vinculantes/sumula-vinculante-{citacao.numero}.md'
        )
        return caminho if caminho.exists() else None
    if citacao.tipo is TipoNorma.SUMULA_TCU:
        caminho = repositorio / f'jurisprudencia/outros-tribunais/tcu/sumula-{citacao.numero}.md'
        return caminho if caminho.exists() else None
    pasta = repositorio / _PASTAS[citacao.tipo]
    if citacao.ano:
        candidatos = sorted(pasta.glob(f'{citacao.ano}/*-{citacao.numero}-{citacao.ano}-*.md'))
        candidatos = candidatos or sorted(pasta.glob(f'**/*-{citacao.numero}-{citacao.ano}-*.md'))
    else:
        candidatos = sorted(pasta.glob(f'**/*-{citacao.numero}-*.md'))
        if len(candidatos) > 1:
            avisar(
                logger,
                f'legislação: {citacao.rotulo} sem o ano bate com {len(candidatos)} normas diferentes; deixei de '
                'fora.',
            )
            return None
    return candidatos[0] if candidatos else None


def _ler_norma(caminho: Path, repositorio: Path, tipo: TipoNorma) -> Norma:
    texto = caminho.read_text(encoding='utf-8')
    cabecalho = _cabecalho(texto)
    relativo = caminho.relative_to(repositorio).as_posix()
    titulo = cabecalho.get('titulo') or (_ROTULOS[tipo] if tipo is TipoNorma.CONSTITUICAO else caminho.stem)
    fonte = cabecalho.get('fonte') or (FONTE_CONSTITUICAO if tipo is TipoNorma.CONSTITUICAO else None)
    return Norma(
        caminho=caminho,
        relativo=relativo,
        titulo=str(titulo),
        ementa=cabecalho.get('ementa'),
        urn=cabecalho.get('urn'),
        fonte=fonte,
        versao_texto=cabecalho.get('versao_texto'),
        revogada=bool(cabecalho.get('revogada')),
        tamanho=caminho.stat().st_size,
        tipo=tipo,
    )


def _cabecalho(texto: str) -> dict:
    if not texto.startswith('---'):
        return {}
    partes = texto.split('\n---', 1)
    if len(partes) < 2:
        return {}
    try:
        dados = yaml.safe_load(partes[0].lstrip('-')) or {}
    except yaml.YAMLError:
        return {}
    return dados if isinstance(dados, dict) else {}


def avisos_da_norma(norma: Norma) -> list[str]:
    avisos = []
    if norma.versao_texto and 'compilad' not in norma.versao_texto.lower():
        avisos.append(
            f'texto não compilado ({norma.versao_texto}); confira a versão vigente na fonte oficial'
        )
    sumula = norma.tipo in (TipoNorma.SUMULA_VINCULANTE, TipoNorma.SUMULA_TCU)
    if not sumula and norma.tamanho < TAMANHO_MINIMO_NORMA:
        avisos.append(f'arquivo de {norma.tamanho // 1024} KB; o texto pode estar incompleto')
    if norma.revogada:
        avisos.append('norma revogada')
    return avisos


def normas_citadas(citacoes: Iterable[Citacao], repositorio: Path) -> dict[str, tuple[Norma, Citacao]]:
    """Chave da norma → norma e a primeira citação dela; citação sem arquivo vira aviso no log."""
    normas: dict[str, tuple[Norma, Citacao]] = {}
    for citacao in citacoes:
        norma = resolver(citacao, repositorio)
        if norma is None:
            avisar(
                logger,
                f'legislação: não achei o texto de {citacao.rotulo} na sua cópia das leis; deixei de fora.',
                DICA_CLONE,
                f'{citacao.rotulo} não encontrada em {repositorio}',
            )
            continue
        normas.setdefault(norma.chave, (norma, citacao))
    return normas


def conteudo_para_notebook(norma: Norma) -> str:
    """O arquivo inteiro, com os avisos da norma no topo para o chat não tratar texto parcial como vigente."""
    avisos = avisos_da_norma(norma)
    topo = ''.join(f'AVISO: {aviso}\n' for aviso in avisos)
    origem = f'Fonte oficial: {norma.fonte}\n' if norma.fonte else ''
    return f'{topo}{origem}Arquivo: {norma.relativo}\n\n{norma.caminho.read_text(encoding="utf-8").strip()}\n'


def titulo_para_notebook(norma: Norma, limite: int = 120) -> str:
    if not norma.ementa:
        return norma.titulo
    ementa = ' '.join(str(norma.ementa).split())
    curta = ementa if len(ementa) <= limite else ementa[: limite - 1].rsplit(' ', 1)[0] + '…'
    return f'{norma.titulo} — {curta}'
