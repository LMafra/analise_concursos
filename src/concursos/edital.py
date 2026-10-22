import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from concursos.deteccao import normalizar

ARQUIVO_EDITAL_ESTRUTURADO = 'edital_estruturado.json'


class EditalNaoEstruturadoError(ValueError):
    pass


@dataclass(frozen=True)
class Topico:
    numero: str
    nome: str
    descricao: str
    peso: float | None = None


@dataclass(frozen=True)
class Disciplina:
    nome: str
    topicos: tuple[Topico, ...]
    peso: float | None = None


@dataclass(frozen=True)
class Conhecimento:
    nome: str
    disciplinas: tuple[Disciplina, ...]


@dataclass(frozen=True)
class Edital:
    fonte: str
    cargo: str | None
    conhecimentos: tuple[Conhecimento, ...] = field(default_factory=tuple)

    def gravar_json(self, caminho: Path) -> None:
        """Grava o conteúdo programático preservando as demais chaves do arquivo (as regras do edital)."""
        mesclar_json(caminho, asdict(self))


def mesclar_json(caminho: Path, dados: dict) -> None:
    """O edital estruturado é gravado em partes (conteúdo programático e regras): cada uma troca só as
    próprias chaves."""
    existentes = json.loads(caminho.read_text(encoding='utf-8')) if caminho.exists() else {}
    existentes.update(dados)
    caminho.write_text(json.dumps(existentes, ensure_ascii=False, indent=2), encoding='utf-8')


_MINUSCULAS = {
    'a', 'à', 'ao', 'aos', 'as', 'às', 'com', 'da', 'das', 'de', 'do', 'dos', 'e', 'em', 'na', 'nas',
    'no', 'nos', 'o', 'os', 'ou', 'para', 'por', 'sem',
}  # fmt: skip
_IGNORADAS_NO_CARGO = {normalizar(p) for p in _MINUSCULAS}
_CONHECIMENTOS = {
    'GERAIS': 'Conhecimentos Gerais',
    'BASICOS': 'Conhecimentos Básicos',
    'ESPECIFICOS': 'Conhecimentos Específicos',
    'COMPLEMENTARES': 'Conhecimentos Complementares',
}
ESPECIFICOS = 'Conhecimentos Específicos'
_LIMIAR_CARGO = 0.75

_INICIO_CONTEUDO = re.compile(r'CONTEUDO PROGRAMATICO|OBJETOS DE AVALIACAO')
_FIM_CONTEUDO = re.compile(r'^(ANEXO\s+[IVXLC\d]+\b|CRONOGRAMA\b)')
_PREFIXO_CONHECIMENTO = re.compile(r'^(\d+(\.\d+)*\s+|MODULO\s+[IVXLC]+\s*-\s*)')
_TITULO_DE_AREA = re.compile(r'^(AREA|ESPECIALIDADE)\s*:')
_ROMANO = re.compile(r'^(?=[IVX])X{0,3}(IX|IV|V?I{0,3})$')
_NOTA_DE_RETIFICACAO = re.compile(r'^\((Retificad|Alterad|Incluíd|Acrescentad)|^https?://', re.IGNORECASE)
_CONTINUA_COM_DOIS_PONTOS = re.compile(r'^[A-ZÀ-ÖØ-Þ][^a-zà-öø-ÿ]*:')
_CONECTOR_FINAL = re.compile(r'(\b(E|DE|DA|DO|DAS|DOS|EM)|[,–-])$')
_CARGO_NUMERADO = re.compile(r'^((CARGO|EMPREGO)\s+\d+|\d{2,4}\s*-)')
_ID_CARGO = re.compile(r'^(?:(?:CARGO|EMPREGO)\s+)?(\d+)')

_PALAVRA = r"[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ0-9\-/&']*(?![a-zà-öø-ÿ]),?"
_MARCADOR = re.compile(
    rf'(?:^|(?<=[.;]\s))(?P<nome>{_PALAVRA}(?:\s+(?:{_PALAVRA}|[–-]))*)(?P<restricao>\s*\([^)]*\))?'
    rf'\s*(?:(?P<dois_pontos>:)\s*|(?=\s*(?P<numerado>\d{{1,2}})\.?\s)|(?=\s[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]))'
)
_NUMERO_TOPICO = re.compile(r'(?:^|(?<=\s))(\d{1,2})(?:\.(?!\d)\s*|\s+)(?=[A-ZÀ-ÖØ-Þ(])')
_FRASE = re.compile(r'(?<=[.;])\s+(?=[A-ZÀ-ÖØ-Þ])')


@dataclass(frozen=True)
class _Item:
    tipo: str
    texto: str


def estruturar_edital(paginas: list[str], cargo: str | None, fonte: str) -> Edital:
    """Conteúdo programático do cargo como conhecimento → disciplina → tópicos."""
    linhas = _linhas_limpas(paginas)
    inicios = [
        i
        for i, linha in enumerate(linhas)
        if _maiusculo(linha) and _INICIO_CONTEUDO.search(normalizar(linha))
    ]
    for inicio in inicios:
        fim = next(
            (j for j in range(inicio + 1, len(linhas)) if _FIM_CONTEUDO.match(normalizar(linhas[j]))),
            len(linhas),
        )
        conhecimentos = _estruturar(_classificar(linhas[inicio + 1 : fim]), cargo)
        if conhecimentos:
            return Edital(fonte, cargo, conhecimentos)
    raise EditalNaoEstruturadoError(f'{fonte}: conteúdo programático não encontrado')


def carregar_edital_manual(caminho: Path, cargo: str | None) -> Edital:
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
        conhecimentos = tuple(
            Conhecimento(c['nome'], tuple(_disciplina_manual(d) for d in c['disciplinas']))
            for c in dados['conhecimentos']
        )
    except (KeyError, TypeError, yaml.YAMLError) as erro:
        raise EditalNaoEstruturadoError(f'{caminho}: edital manual inválido ({erro})') from erro
    return Edital(caminho.name, dados.get('cargo', cargo), conhecimentos)


def titulo_legivel(texto: str) -> str:
    """'LÍNGUA PORTUGUESA' → 'Língua Portuguesa'; textos que já têm minúsculas ficam como estão."""
    if not _maiusculo(texto):
        return texto
    palavras = []
    for indice, original in enumerate(texto.split()):
        palavra = original.rstrip(',;:.')
        sufixo = original[len(palavra) :]
        minuscula = palavra.lower()
        if (
            any(c.islower() for c in palavra)
            or not palavra.isalpha()
            or (len(palavra) <= 2 and indice and minuscula not in _MINUSCULAS)
            or _ROMANO.match(palavra)
        ):
            palavras.append(original)
        elif indice and minuscula in _MINUSCULAS:
            palavras.append(minuscula + sufixo)
        else:
            palavras.append(minuscula.capitalize() + sufixo)
    return ' '.join(palavras)


def _disciplina_manual(dados: dict) -> Disciplina:
    topicos = []
    for numero, topico in enumerate(dados['topicos'], start=1):
        if isinstance(topico, str):
            topico = {'nome': topico}
        topicos.append(
            Topico(str(numero), topico['nome'], topico.get('descricao', topico['nome']), topico.get('peso'))
        )
    return Disciplina(dados['nome'], tuple(topicos), dados.get('peso'))


def _linhas_limpas(paginas: list[str]) -> list[str]:
    por_pagina = [[linha.strip() for linha in pagina.splitlines() if linha.strip()] for pagina in paginas]
    contagem = Counter(linha for linhas in por_pagina for linha in set(linhas))
    minimo = max(3, 0.3 * len(paginas))
    repetidas = {linha for linha, n in contagem.items() if n >= minimo and len(linha) <= 80}
    return [
        linha
        for linhas in por_pagina
        for linha in linhas
        if linha not in repetidas and not linha.isdigit() and not _NOTA_DE_RETIFICACAO.match(linha)
    ]


def _maiusculo(texto: str) -> bool:
    letras = [c for c in texto if c.isalpha()]
    return len(letras) >= 4 and sum(c.isupper() for c in letras) >= 0.9 * len(letras)


def _juntar_titulos_quebrados(linhas: list[str]) -> list[str]:
    """'CARGO 2: ... ANALISTA DE TECNOLOGIA DA' + 'INFORMAÇÃO' viram uma linha só."""
    juntas: list[str] = []
    for linha in linhas:
        anterior = juntas[-1] if juntas else ''
        quebrado = anterior.endswith(':') or _CONECTOR_FINAL.search(normalizar(anterior))
        if quebrado and _maiusculo(anterior) and _maiusculo(linha) and ':' not in linha:
            juntas[-1] = f'{anterior} {linha}'
        else:
            juntas.append(linha)
    return juntas


def _classificar(linhas: list[str]) -> list[_Item]:
    linhas = _juntar_titulos_quebrados(linhas)
    itens = []
    for indice, linha in enumerate(linhas):
        seguinte = linhas[indice + 1] if indice + 1 < len(linhas) else ''
        if conhecimento := _conhecimento(linha):
            itens.append(_Item('conhecimento', conhecimento))
        elif _eh_titulo(linha, seguinte):
            itens.append(_Item('titulo', linha))
        else:
            itens.append(_Item('texto', linha))
    return itens


def _conhecimento(linha: str) -> str | None:
    palavras = _PREFIXO_CONHECIMENTO.sub('', normalizar(linha)).rstrip(':').split()
    if len(palavras) >= 2 and palavras[0] == 'CONHECIMENTOS':
        return _CONHECIMENTOS.get(palavras[1])
    return None


def _eh_titulo(linha: str, seguinte: str) -> bool:
    if _TITULO_DE_AREA.match(normalizar(linha)):
        return True
    if not _maiusculo(linha) or linha.endswith(':') or len(linha.split()) < 2:
        return False
    continua = _CONECTOR_FINAL.search(normalizar(linha)) and _CONTINUA_COM_DOIS_PONTOS.match(seguinte)
    return not continua


def _estruturar(itens: list[_Item], cargo: str | None) -> tuple[Conhecimento, ...]:
    secoes = _secoes_do_cargo(itens, cargo)
    conhecimentos = []
    for nome, titulo, itens_secao, restricao in secoes:
        disciplinas = _disciplinas(itens_secao, titulo or nome, restricao)
        if disciplinas:
            conhecimentos.append(Conhecimento(nome, disciplinas))
    return tuple(conhecimentos)


def _secoes_do_cargo(itens: list[_Item], cargo: str | None):
    """Seções (conhecimento, título do bloco, itens, restrição) que valem para o cargo."""
    cabecalhos = [i for i, item in enumerate(itens) if item.tipo == 'conhecimento']
    if not cabecalhos:
        return [('Conhecimentos', None, itens, None)]
    titulos = [i for i, item in enumerate(itens) if item.tipo == 'titulo']
    numerados = [itens[i].texto for i in titulos if _CARGO_NUMERADO.match(normalizar(itens[i].texto))]
    escolhido = _titulo_do_cargo(itens, titulos, cargo) if cargo else None
    if escolhido is None:
        if len(numerados) >= 2:
            raise EditalNaoEstruturadoError(_mensagem_cargo(cargo, numerados))
        return [(itens[c].texto, None, _ate_proximo_cabecalho(itens, c), None) for c in cabecalhos]

    restricao = _Restricao(cargo, itens[escolhido].texto)
    secoes = []
    gerais = [c for c in cabecalhos if c < escolhido and itens[c].texto != ESPECIFICOS]
    if gerais:
        secoes.append((itens[gerais[-1]].texto, None, _ate_proximo_cabecalho(itens, gerais[-1]), restricao))
    assinatura = _assinatura(itens[escolhido].texto)
    inicio = escolhido + 1
    while inicio < len(itens) and itens[inicio].tipo == 'conhecimento':
        inicio += 1
    fim = next(
        (
            j
            for j in range(inicio, len(itens))
            if itens[j].tipo == 'conhecimento'
            or (itens[j].tipo == 'titulo' and _assinatura(itens[j].texto) == assinatura)
        ),
        len(itens),
    )
    bloco = itens[inicio:fim]
    secoes.append((ESPECIFICOS, titulo_legivel(itens[escolhido].texto), bloco, restricao))
    return secoes


def _mensagem_cargo(cargo: str | None, numerados: list[str]) -> str:
    opcoes = '; '.join(numerados)
    if cargo is None:
        return f'edital com vários cargos ({opcoes}); informe cargo no concurso.yaml'
    return f'cargo {cargo!r} não encontrado no edital (cargos: {opcoes})'


def _titulo_do_cargo(itens: list[_Item], titulos: list[int], cargo: str) -> int | None:
    """Título que melhor descreve o cargo, junto com o título de nível acima (cargo → área)."""
    pontuados = {}
    for posicao, i in enumerate(titulos):
        texto = itens[i].texto
        acima = next(
            (
                itens[j].texto
                for j in reversed(titulos[:posicao])
                if _assinatura(itens[j].texto) != _assinatura(texto)
            ),
            '',
        )
        pontuados[i] = (_semelhanca(cargo, f'{acima} {texto}'), _semelhanca(cargo, texto))
    if not pontuados:
        return None
    maior = max(pontuados.values())
    melhores = [i for i, nota in pontuados.items() if nota == maior]
    return melhores[0] if maior[0] >= _LIMIAR_CARGO and len(melhores) == 1 else None


def _semelhanca(cargo: str, texto: str) -> float:
    palavras_cargo = _palavras(cargo)
    return len(palavras_cargo & _palavras(texto)) / len(palavras_cargo) if palavras_cargo else 0.0


def _palavras(texto: str) -> set[str]:
    return {p for p in re.split(r'[^A-Z0-9]+', normalizar(texto)) if p and p not in _IGNORADAS_NO_CARGO}


def _assinatura(titulo: str) -> str:
    primeira = normalizar(titulo).split()[0]
    return '#' if primeira.isdigit() else primeira


def _ate_proximo_cabecalho(itens: list[_Item], cabecalho: int) -> list[_Item]:
    fim = next((j for j in range(cabecalho + 1, len(itens)) if itens[j].tipo == 'conhecimento'), len(itens))
    return itens[cabecalho + 1 : fim]


class _Restricao:
    """Decide se disciplinas marcadas com '(SOMENTE/EXCETO PARA ...)' valem para o cargo."""

    def __init__(self, cargo: str, titulo: str) -> None:
        self.cargo = cargo
        identificador = _ID_CARGO.match(normalizar(titulo))
        self.identificador = identificador.group(1) if identificador else None

    def aplica(self, texto: str) -> bool:
        restricao = normalizar(texto)
        if 'DISCURSIVA' in restricao:
            return False
        mencionado = (
            bool(self.identificador and re.search(rf'\b{self.identificador}\b', restricao))
            or _semelhanca(self.cargo, restricao) >= _LIMIAR_CARGO
        )
        if 'EXCETO' in restricao:
            return not mencionado
        if 'SOMENTE' in restricao:
            return mencionado
        return True


def _disciplinas(
    itens: list[_Item], nome_padrao: str, restricao: _Restricao | None
) -> tuple[Disciplina, ...]:
    disciplinas: list[Disciplina] = []
    titulo, linhas = None, []

    def fechar() -> None:
        disciplinas.extend(_disciplinas_do_texto(_juntar(linhas), titulo or nome_padrao, restricao))

    for item in itens:
        if item.tipo == 'titulo':
            fechar()
            titulo, linhas = titulo_legivel(item.texto), []
        else:
            linhas.append(item.texto)
    fechar()
    return tuple(disciplinas)


def _juntar(linhas: list[str]) -> str:
    texto = ''
    for linha in linhas:
        if texto.endswith('-') and linha[:1].islower():
            texto = texto[:-1] + linha
        else:
            texto = f'{texto} {linha}' if texto else linha
    return re.sub(r'\s+', ' ', texto).strip()


def _disciplinas_do_texto(texto: str, nome_padrao: str, restricao: _Restricao | None) -> list[Disciplina]:
    marcadores = [m for m in _MARCADOR.finditer(texto) if _eh_marcador(m)]
    disciplinas = []
    preambulo = texto[: marcadores[0].start()] if marcadores else texto
    if topicos := _topicos(preambulo, exigir_numeracao=True):
        disciplinas.append(Disciplina(nome_padrao, topicos))
    for indice, marcador in enumerate(marcadores):
        fim = marcadores[indice + 1].start() if indice + 1 < len(marcadores) else len(texto)
        parenteses = marcador.group('restricao')
        if parenteses and restricao is not None and not restricao.aplica(parenteses):
            continue
        if topicos := _topicos(texto[marcador.end() : fim], exigir_numeracao=False):
            disciplinas.append(Disciplina(titulo_legivel(marcador.group('nome').rstrip(',')), topicos))
    return disciplinas


def _eh_marcador(marcador: re.Match) -> bool:
    nome = marcador.group('nome')
    letras = sum(c.isalpha() for c in nome)
    palavras = [p for p in nome.split() if any(c.isalpha() for c in p)]
    so_siglas = all(sum(c.isalpha() for c in p) <= 3 for p in palavras)
    explicito = marcador.group('dois_pontos') is not None or marcador.group('numerado') == '1'
    return letras >= 6 and not so_siglas and (len(palavras) >= 2 or explicito)


def _topicos(texto: str, exigir_numeracao: bool) -> tuple[Topico, ...]:
    texto = texto.strip()
    if not texto:
        return ()
    inicios, ultimo = [], 0
    for numero in _NUMERO_TOPICO.finditer(texto):
        valor = int(numero.group(1))
        if (ultimo == 0 and valor == 1) or (ultimo and ultimo < valor <= ultimo + 3):
            inicios.append((valor, numero.start(), numero.end()))
            ultimo = valor
    if len(inicios) >= 2 or (inicios and inicios[0][1] == 0):
        topicos = []
        for indice, (valor, _, fim) in enumerate(inicios):
            proximo = inicios[indice + 1][1] if indice + 1 < len(inicios) else len(texto)
            topicos.append(_topico(str(valor), texto[fim:proximo], numerado=True))
        return tuple(topicos)
    if exigir_numeracao:
        return ()
    frases = [f for f in _FRASE.split(texto) if f.strip(' .;')]
    return tuple(_topico(str(numero), frase, numerado=False) for numero, frase in enumerate(frases, start=1))


def _topico(numero: str, texto: str, numerado: bool) -> Topico:
    descricao = texto.strip().rstrip(' ;')
    subtopico = re.search(rf'\s{numero}\.\d{{1,2}}(?!\d)', descricao) if numerado else None
    nome = (descricao[: subtopico.start()] if subtopico else descricao).strip().rstrip('.;: ')
    return Topico(numero, nome[:150], descricao)
