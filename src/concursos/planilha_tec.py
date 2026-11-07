"""Planilha do TEC (CSV ou XLSX) convertida para o contrato v1 do tec-erros, para seguir pelo mesmo caminho das
exportações da captura. O app não acessa o TEC: a planilha é um arquivo que o usuário já tem."""

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from concursos.pratica_tec import APP, VERSAO, impressao_digital, normalizar

EXTENSOES = ('.csv', '.xlsx')
DISPOSITIVO = 'planilha'
TAMANHO_HASH = 600

CAMPOS = (
    'materia',
    'assunto',
    'enunciado',
    'resultado',
    'data',
    'banca',
    'orgao',
    'ano',
    'gabarito',
    'marcada',
)
OBRIGATORIOS = ('materia', 'resultado')
ROTULOS = {
    'materia': 'Disciplina',
    'assunto': 'Assunto',
    'enunciado': 'Questão',
    'resultado': 'Resultado',
    'data': 'Data',
    'banca': 'Banca',
    'orgao': 'Órgão',
    'ano': 'Ano',
    'gabarito': 'Gabarito',
    'marcada': 'Sua resposta',
}
SINONIMOS = {
    'materia': ('materia', 'disciplina'),
    'assunto': ('assunto', 'topico', 'tema'),
    'enunciado': ('enunciado', 'questao', 'texto da questao', 'texto', 'id', 'codigo', 'id da questao'),
    'resultado': (
        'resultado',
        'acertou',
        'acertou?',
        'certo/errado',
        'certo ou errado',
        'situacao',
        'acerto',
    ),
    'data': ('data', 'resolvida em', 'data da resolucao', 'dia'),
    'banca': ('banca',),
    'orgao': ('orgao', 'instituicao'),
    'ano': ('ano',),
    'gabarito': ('gabarito', 'resposta correta', 'alternativa correta'),
    'marcada': ('marcada', 'sua resposta', 'resposta marcada', 'minha resposta', 'resposta dada'),
}
ACERTO = {
    'c',
    'certo',
    'certa',
    'acertou',
    'acerto',
    'sim',
    's',
    '1',
    'true',
    'verdadeiro',
    'correta',
    'correto',
    'v',
}
ERRO = {
    'e',
    'errado',
    'errada',
    'errou',
    'erro',
    'nao',
    'n',
    '0',
    'false',
    'falso',
    'incorreta',
    'incorreto',
    'x',
}
_DATA_BR = re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{4})')
_DATA_ISO = re.compile(r'^(\d{4})-(\d{2})-(\d{2})')


class PlanilhaInvalidaError(ValueError):
    pass


@dataclass(frozen=True)
class Planilha:
    cabecalho: list[str]
    linhas: list[dict[str, str]]


@dataclass(frozen=True)
class Conversao:
    exportacao: dict
    linhas: int
    erradas: int
    ignoradas: int


def _decodificar(conteudo: bytes) -> str:
    for codificacao in ('utf-8-sig', 'latin-1'):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise PlanilhaInvalidaError('codificação do CSV não reconhecida')


def _separador(texto: str) -> str:
    primeira = texto.splitlines()[0] if texto else ''
    return max((';', ',', '\t'), key=primeira.count)


def _ler_csv(caminho: Path) -> Planilha:
    texto = _decodificar(caminho.read_bytes())
    leitor = csv.reader(io.StringIO(texto), delimiter=_separador(texto))
    linhas = [linha for linha in leitor if any(c.strip() for c in linha)]
    if not linhas:
        raise PlanilhaInvalidaError(f'{caminho.name}: a planilha está vazia')
    cabecalho = [c.strip() for c in linhas[0]]
    return Planilha(
        cabecalho, [dict(zip(cabecalho, (c.strip() for c in linha), strict=False)) for linha in linhas[1:]]
    )


def _texto_da_celula(valor) -> str:
    if valor is None:
        return ''
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _ler_xlsx(caminho: Path) -> Planilha:
    from openpyxl import load_workbook

    try:
        livro = load_workbook(caminho, read_only=True, data_only=True)
    except Exception as erro:  # noqa: BLE001 - o openpyxl levanta tipos variados para arquivo corrompido
        raise PlanilhaInvalidaError(f'{caminho.name}: não é uma planilha XLSX legível ({erro})') from erro
    try:
        linhas = [
            [_texto_da_celula(c) for c in linha]
            for linha in livro.worksheets[0].iter_rows(values_only=True)
            if any(c not in (None, '') for c in linha)
        ]
    finally:
        livro.close()
    if not linhas:
        raise PlanilhaInvalidaError(f'{caminho.name}: a planilha está vazia')
    cabecalho = linhas[0]
    return Planilha(cabecalho, [dict(zip(cabecalho, linha, strict=False)) for linha in linhas[1:]])


def ler_planilha(caminho: Path) -> Planilha:
    extensao = caminho.suffix.lower()
    if extensao == '.csv':
        return _ler_csv(caminho)
    if extensao == '.xlsx':
        return _ler_xlsx(caminho)
    raise PlanilhaInvalidaError(f'{caminho.name}: use uma planilha .csv ou .xlsx')


def _cabecalho_normalizado(coluna: str) -> str:
    return normalizar(coluna).strip(' :')


def detectar_colunas(cabecalho: list[str]) -> dict[str, str | None]:
    """Cada campo pela coluna cujo nome é um sinônimo; sem nome exato, pela que começa com ele. Uma coluna
    serve a um campo só."""
    normalizados = {coluna: _cabecalho_normalizado(coluna) for coluna in cabecalho if coluna}
    usadas: set[str] = set()
    mapeamento: dict[str, str | None] = {}
    for exato in (True, False):
        for campo in CAMPOS:
            if mapeamento.get(campo):
                continue
            for sinonimo in SINONIMOS[campo]:
                achada = next(
                    (
                        c
                        for c, n in normalizados.items()
                        if c not in usadas and (n == sinonimo if exato else n.startswith(sinonimo))
                    ),
                    None,
                )
                if achada:
                    mapeamento[campo] = achada
                    usadas.add(achada)
                    break
    return {campo: mapeamento.get(campo) for campo in CAMPOS}


def assinatura(cabecalho: list[str]) -> str:
    """A chave do mapeamento lembrado: a mesma planilha (os mesmos cabeçalhos) reaproveita a conferência."""
    return hashlib.sha256('\x1f'.join(_cabecalho_normalizado(c) for c in cabecalho).encode()).hexdigest()[:16]


def faltando(mapeamento: dict[str, str | None]) -> list[str]:
    return [campo for campo in OBRIGATORIOS if not mapeamento.get(campo)]


def acertou(valor: str) -> bool | None:
    texto = normalizar(valor).strip(' .!')
    if texto in ACERTO:
        return True
    if texto in ERRO:
        return False
    return None


def data_iso(valor: str) -> str | None:
    texto = (valor or '').strip()
    if encontrada := _DATA_ISO.match(texto):
        return '-'.join(encontrada.groups())
    if encontrada := _DATA_BR.match(texto):
        dia, mes, ano = encontrada.groups()
        return f'{ano}-{int(mes):02d}-{int(dia):02d}'
    return None


def fnv1a(texto: str) -> str:
    """O mesmo hash do `nucleo.js` do tec-erros, para que a questão da planilha e a da captura se juntem."""
    h = 0x811C9DC5
    for caractere in texto:
        h ^= ord(caractere)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f'{h:08x}'


def _slug(texto: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', normalizar(texto)).strip('-') or 'sem-materia'


def converter(
    planilha: Planilha, mapeamento: dict[str, str | None], arquivo: str, agora: datetime
) -> Conversao:
    """Cada linha errada vira um erro de origem `historico`; cada matéria, um caderno sintético com os totais da
    planilha. Linha sem matéria ou com resultado que não se reconhece fica de fora (contada em `ignoradas`)."""
    if campos := faltando(mapeamento):
        raise PlanilhaInvalidaError('falta escolher a coluna de ' + ', '.join(ROTULOS[c] for c in campos))

    def valor(linha: dict[str, str], campo: str) -> str:
        coluna = mapeamento.get(campo)
        return (linha.get(coluna) or '').strip() if coluna else ''

    hoje = agora.date().isoformat()
    erros, totais, ignoradas = [], {}, 0
    for linha in planilha.linhas:
        materia, resultado = valor(linha, 'materia'), acertou(valor(linha, 'resultado'))
        if not materia or resultado is None:
            ignoradas += 1
            continue
        dia = data_iso(valor(linha, 'data')) or hoje
        total = totais.setdefault(materia, {'tot': 0, 'ac': 0, 'er': 0, 'd': dia})
        total['tot'] += 1
        total['ac' if resultado else 'er'] += 1
        total['d'] = max(total['d'], dia)
        if resultado:
            continue
        enunciado = valor(linha, 'enunciado')
        codigo = re.sub(r'\D', '', enunciado) if re.fullmatch(r'[#\s\d]+', enunciado or 'x') else ''
        base = enunciado or f'{materia} {valor(linha, "assunto")} {len(erros)}'
        erro = {
            'id': f'q{codigo}' if codigo else 'h' + fnv1a(base[:TAMANHO_HASH]),
            'd': dia,
            't': 0,
            'v': 1,
            'ds': [],
            'dev': DISPOSITIVO,
            'origem': 'historico',
            'mat': materia,
        }
        if enunciado and not codigo:
            erro['fp'] = impressao_digital(enunciado)
            erro['enun'] = enunciado
        for campo, chave in (
            ('assunto', 'ass'),
            ('banca', 'banca'),
            ('orgao', 'orgao'),
            ('ano', 'ano'),
            ('marcada', 'marc'),
            ('gabarito', 'gab'),
        ):
            if texto := valor(linha, campo):
                erro[chave] = texto
        erros.append(erro)
    cadernos = [
        {
            'id': f'planilha:{arquivo}:{_slug(materia)}',
            'cad': f'planilha:{arquivo}',
            'mat': materia,
            'tot': t['tot'],
            'res': t['tot'],
            'ac': t['ac'],
            'er': t['er'],
            'd': t['d'],
            't': 0,
            'dev': DISPOSITIVO,
        }
        for materia, t in sorted(totais.items())
    ]
    exportacao = {
        'app': APP,
        'v': VERSAO,
        'em': agora.isoformat(timespec='seconds'),
        'dev': DISPOSITIVO,
        'erros': erros,
        'cads': cadernos,
    }
    return Conversao(exportacao, len(planilha.linhas), len(erros), ignoradas)


def nome_da_exportacao(arquivo: Path, agora: datetime) -> str:
    return f'tec-erros-planilha-{_slug(arquivo.stem)}-{agora:%Y-%m-%d}.json'
