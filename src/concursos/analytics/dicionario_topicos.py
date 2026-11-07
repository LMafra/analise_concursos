"""Dicionário de temas (`.concurso/taxonomia_topicos.yaml`): termos e expressões de cada tópico que
aproximam o texto da questão do tópico certo do edital na similaridade TF-IDF.

A questão que cita um termo recebe a marca sintética do tópico (`tema_<disciplina>_<topico>`), e o documento
do tópico recebe só a marca: os termos soltos no documento puxariam questões que não os citam. Sem
dicionário, `topicos.sugerir_topicos` roda como antes."""

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

import pandas as pd
import yaml

from concursos.analytics.consolidado import N_MINIMO_TOPICO
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO, Conhecimento, Disciplina, Edital, Topico
from concursos.erros import ErroDoUsuario
from concursos.texto import normalizar
from concursos.topicos import (
    ARQUIVO_REVISAO,
    NAO_MAPEADO,
    SCORE_BAIXO,
    chave_de_palavras,
    palavras_chave,
    sugerir_topicos,
)

VERSAO_DICIONARIO = 1
MAXIMO_MARCAS = 3
MAXIMO_PALAVRAS_TERMO = 6
CAMPOS_DO_TOPICO = ('nomes', 'termos', 'expressoes', 'origem')
CHAVES_RESERVADAS = ('versao', 'recusados')
PREFIXO_MARCA = 'tema'
MINIMO_QUESTOES_SUGESTAO = 2
MAXIMO_SUGESTOES_POR_TOPICO = 5
ARQUIVO_GANHO = 'ganho_dicionario.md'


def slug(texto: str) -> str:
    return re.sub(r'[^0-9a-z]+', '_', normalizar(texto).lower()).strip('_')


def _norm(texto: str) -> str:
    return ' '.join(re.findall(r'\w+', normalizar(texto).lower()))


@dataclass(frozen=True)
class EntradaTema:
    disciplina: str
    topico: str
    nomes: tuple[str, ...] = ()
    termos: tuple[str, ...] = ()
    expressoes: tuple[str, ...] = ()
    origem: tuple[str, ...] = ()

    @property
    def marca(self) -> str:
        return f'{PREFIXO_MARCA}_{self.disciplina}_{self.topico}'

    @property
    def termos_e_expressoes(self) -> tuple[str, ...]:
        return (*self.termos, *self.expressoes)


@dataclass(frozen=True)
class Dicionario:
    entradas: tuple[EntradaTema, ...]
    recusados: frozenset[str] = frozenset()

    def sem_origem(self, concurso: str) -> 'Dicionario':
        """O dicionário sem as entradas tiradas das revisões de `concurso` (avaliação sem vazamento)."""
        return Dicionario(tuple(e for e in self.entradas if concurso not in e.origem), self.recusados)


def _lista(valor: object, onde: str) -> tuple[str, ...]:
    if valor is None:
        return ()
    if isinstance(valor, str):
        valor = [valor]
    if not isinstance(valor, list) or not all(isinstance(v, str | int | float) for v in valor):
        raise ErroDoUsuario(f'{onde}: esperada uma lista de textos', 'use [termo 1, termo 2]')
    return tuple(str(v).strip() for v in valor)


def ler_dicionario(dados: object, origem: str = 'dicionário') -> Dicionario:
    if not isinstance(dados, dict):
        raise ErroDoUsuario(f'{origem}: esperado um mapa de disciplina para tópicos', 'refaça pela tela')
    versao = dados.get('versao', VERSAO_DICIONARIO)
    if versao != VERSAO_DICIONARIO:
        raise ErroDoUsuario(f'{origem}: versão {versao} desconhecida', f'use versao: {VERSAO_DICIONARIO}')
    entradas = []
    for disciplina, topicos in dados.items():
        if disciplina in CHAVES_RESERVADAS:
            continue
        if not isinstance(topicos, dict):
            raise ErroDoUsuario(f'{origem}: {disciplina} precisa de um mapa de tópicos', 'refaça pela tela')
        for topico, campos in topicos.items():
            onde = f'{origem}: {disciplina}.{topico}'
            campos = campos or {}
            if not isinstance(campos, dict):
                raise ErroDoUsuario(f'{onde}: esperado nomes, termos e expressoes', 'refaça pela tela')
            if desconhecidos := sorted(set(campos) - set(CAMPOS_DO_TOPICO)):
                raise ErroDoUsuario(
                    f"{onde}: campo desconhecido '{desconhecidos[0]}'", f'use {", ".join(CAMPOS_DO_TOPICO)}'
                )
            termos = _lista(campos.get('termos'), f'{onde}.termos')
            expressoes = _lista(campos.get('expressoes'), f'{onde}.expressoes')
            for termo in (*termos, *expressoes):
                palavras = _norm(termo).split()
                if not palavras or len(palavras) > MAXIMO_PALAVRAS_TERMO:
                    raise ErroDoUsuario(
                        f'{onde}: termo "{termo}" vazio ou com mais de {MAXIMO_PALAVRAS_TERMO} palavras',
                        'use termos curtos',
                    )
            entradas.append(
                EntradaTema(
                    slug(str(disciplina)),
                    slug(str(topico)),
                    _lista(campos.get('nomes'), f'{onde}.nomes'),
                    termos,
                    expressoes,
                    _lista(campos.get('origem'), f'{onde}.origem'),
                )
            )
    return Dicionario(tuple(entradas), frozenset(_lista(dados.get('recusados'), f'{origem}: recusados')))


def carregar_dicionario(caminho: Path) -> Dicionario:
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8'))
    except yaml.YAMLError as erro:
        raise ErroDoUsuario(
            'Não consegui ler o dicionário de temas.',
            'refaça o dicionário em Configurações > Disciplinas e temas.',
            f'{caminho}: YAML inválido ({erro})',
        ) from erro
    return ler_dicionario(dados or {}, str(caminho))


def dicionario_em_dados(dicionario: Dicionario) -> dict:
    dados: dict = {'versao': VERSAO_DICIONARIO}
    for entrada in dicionario.entradas:
        campos = {
            nome: list(valor)
            for nome, valor in (
                ('nomes', entrada.nomes),
                ('termos', entrada.termos),
                ('expressoes', entrada.expressoes),
                ('origem', entrada.origem),
            )
            if valor
        }
        dados.setdefault(entrada.disciplina, {})[entrada.topico] = campos
    if dicionario.recusados:
        dados['recusados'] = sorted(dicionario.recusados)
    return dados


def dicionario_em_yaml(dicionario: Dicionario) -> str:
    return yaml.safe_dump(dicionario_em_dados(dicionario), allow_unicode=True, sort_keys=False)


# casamento com o edital e expansão


def _disciplina_casa(entrada: EntradaTema, disciplina: str, canonicas: Mapping[str, str]) -> bool:
    nomes = {disciplina, canonicas.get(disciplina, disciplina)}
    if entrada.disciplina in {slug(n) for n in nomes}:
        return True
    chave = set(entrada.disciplina.split('_')) - {''}
    return any(
        chave and (chave <= palavras_chave(n) or palavras_chave(n) <= chave)
        for n in nomes
        if palavras_chave(n)
    )


def _topico_casa(entrada: EntradaTema, topico: str) -> bool:
    if entrada.nomes:
        return chave_de_palavras(topico) in {chave_de_palavras(n) for n in entrada.nomes}
    chave = set(entrada.topico.split('_')) - {''}
    return bool(chave) and chave <= palavras_chave(topico)


def _forma(texto: str) -> str:
    """O texto normalizado sem o plural simples, para "Tabelas-verdade" casar com "tabela verdade"."""
    return ' '.join(p[:-1] if len(p) > 3 and p.endswith('s') else p for p in _norm(texto).split())


def _contem(texto_forma: str, termo_forma: str) -> bool:
    return bool(termo_forma) and re.search(rf'(?<!\w){re.escape(termo_forma)}(?!\w)', texto_forma) is not None


@dataclass
class Expansao:
    """As entradas do dicionário casadas com os tópicos de um edital."""

    por_topico: dict[tuple[str, str], list[EntradaTema]]
    ambiguos: set[tuple[str, str, str]] = field(default_factory=set)
    """(disciplina, marca, termo) cujo termo já nomeia outro tópico da disciplina: a questão que o cita
    fica sem marcas da disciplina, e o edital decide sozinho."""
    _termos: list[tuple[str, EntradaTema, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        vistos = set()
        for (disciplina, _topico), entradas in self.por_topico.items():
            for entrada in entradas:
                for termo in entrada.termos_e_expressoes:
                    chave = (disciplina, entrada.marca, _forma(termo))
                    if chave not in vistos and chave not in self.ambiguos:
                        vistos.add(chave)
                        self._termos.append((disciplina, entrada, _forma(termo)))
        self._termos.sort(key=lambda item: -len(item[2]))

    def documento(self, disciplina: str, topico: str, documento: str) -> str:
        marcas = [entrada.marca for entrada in self.por_topico.get((disciplina, topico), [])]
        return f'{documento} {" ".join(marcas)}' if marcas else documento

    def marcas(self, texto: str, aceitas: set[str] | None = None) -> list[str]:
        forma = _forma(texto)
        literais = {d for d, _marca, termo in self.ambiguos if _contem(forma, termo)}
        marcas = [
            entrada.marca
            for disciplina, entrada, termo in self._termos
            if (aceitas is None or disciplina in aceitas)
            and disciplina not in literais
            and _contem(forma, termo)
        ]
        return list(dict.fromkeys(marcas))[:MAXIMO_MARCAS]

    def texto(self, texto: str, aceitas: set[str] | None = None) -> str:
        return texto + ''.join(f' {marca}' for marca in self.marcas(texto, aceitas))


def expansao_para(
    dicionario: Dicionario, topicos: Iterable[tuple[str, str]], canonicas: Mapping[str, str] | None = None
) -> Expansao:
    canonicas = canonicas or {}
    topicos = list(topicos)
    por_topico: dict[tuple[str, str], list[EntradaTema]] = {}
    for disciplina, topico in topicos:
        casadas = [
            e
            for e in dicionario.entradas
            if _disciplina_casa(e, disciplina, canonicas) and _topico_casa(e, topico)
        ]
        if casadas:
            por_topico[(disciplina, topico)] = casadas
    ambiguos = set()
    for (disciplina, topico), entradas in por_topico.items():
        outros = [
            _forma(t)
            for d, t in topicos
            if d == disciplina and t != topico and not any(e in por_topico.get((d, t), []) for e in entradas)
        ]
        for entrada in entradas:
            for termo in entrada.termos_e_expressoes:
                if any(_contem(outro, _forma(termo)) for outro in outros):
                    ambiguos.add((disciplina, entrada.marca, _forma(termo)))
    return Expansao(por_topico, ambiguos)


def expandir_consulta(dicionario: Dicionario | None, consulta: str, limite: int = 12) -> list[str]:
    """Os termos das entradas que a consulta menciona, para acrescentar em OR na busca nos livros."""
    if dicionario is None:
        return []
    forma = _forma(consulta)
    termos: list[str] = []
    for entrada in dicionario.entradas:
        if any(_contem(forma, _forma(t)) for t in entrada.termos_e_expressoes):
            termos += [t for t in entrada.termos_e_expressoes if not _contem(forma, _forma(t))]
    return list(dict.fromkeys(termos))[:limite]


# métrica de ganho


def edital_do_json(caminho: Path) -> Edital | None:
    if not caminho.exists():
        return None
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    conhecimentos = tuple(
        Conhecimento(
            c.get('nome', ''),
            tuple(
                Disciplina(
                    d['nome'],
                    tuple(
                        Topico(str(t.get('numero') or ''), t['nome'], t.get('descricao') or t['nome'])
                        for t in d.get('topicos') or []
                    ),
                )
                for d in c.get('disciplinas') or []
            ),
        )
        for c in dados.get('conhecimentos') or []
    )
    return Edital(dados.get('fonte', ''), dados.get('cargo'), conhecimentos)


@dataclass(frozen=True)
class Questao:
    concurso: str
    questao: int
    prova: str
    disciplina: str
    enunciado: str
    revisado: str


def questoes_revisadas(raiz_provas: Path, analises: Path) -> dict[str, tuple[Edital, list[Questao]]]:
    """Por concurso, o edital estruturado e as questões com o tópico preenchido na revisão."""
    por_concurso = {}
    for caminho in sorted(raiz_provas.glob(f'*/{ARQUIVO_REVISAO}')):
        concurso = caminho.parents[1].name
        edital = edital_do_json(_edital_estruturado(analises, concurso))
        if edital is None or not edital.conhecimentos:
            continue
        tabela = pd.read_csv(caminho, dtype=str, keep_default_na=False)
        questoes = [
            Questao(
                concurso,
                int(linha.questao),
                linha.prova,
                linha.disciplina.strip() or linha.disciplina_sugerida,
                linha.enunciado,
                linha.topico.strip(),
            )
            for linha in tabela.itertuples()
            if linha.topico.strip()
        ]
        if questoes:
            por_concurso[concurso] = (edital, questoes)
    return por_concurso


def _edital_estruturado(analises: Path, concurso: str) -> Path:
    direto = analises / concurso / ARQUIVO_EDITAL_ESTRUTURADO
    if direto.exists():
        return direto
    return next(iter(sorted(analises.glob(f'**/{concurso}/{ARQUIVO_EDITAL_ESTRUTURADO}'))), direto)


@dataclass(frozen=True)
class Placar:
    n: int
    antes: int
    depois: int
    baixos_antes: int
    baixos_depois: int

    @property
    def taxa_antes(self) -> float:
        return self.antes / self.n if self.n else 0.0

    @property
    def taxa_depois(self) -> float:
        return self.depois / self.n if self.n else 0.0

    @property
    def delta_pp(self) -> float:
        return round(100 * (self.taxa_depois - self.taxa_antes), 1)

    @property
    def amostra_suficiente(self) -> bool:
        return self.n >= N_MINIMO_TOPICO


@dataclass(frozen=True)
class Mudanca:
    concurso: str
    questao: int
    revisado: str
    antes: str
    depois: str


@dataclass(frozen=True)
class Ganho:
    geral: Placar
    por_disciplina: dict[str, Placar]
    corrigidas: list[Mudanca]
    quebradas: list[Mudanca]

    @property
    def alerta(self) -> bool:
        """Piorou: mais quebradas que corrigidas, ou uma disciplina com amostra suficiente caindo."""
        caiu = any(p.amostra_suficiente and p.depois < p.antes for p in self.por_disciplina.values())
        return len(self.quebradas) > len(self.corrigidas) or caiu


def _acertou(sugerido: str, revisado: str) -> bool:
    if revisado == NAO_MAPEADO or sugerido == NAO_MAPEADO:
        return sugerido == revisado
    return chave_de_palavras(sugerido) == chave_de_palavras(revisado)


def avaliar_ganho(
    revisadas: dict[str, tuple[Edital, list[Questao]]],
    dicionario: Dicionario,
    canonicas: Mapping[str, str] | None = None,
) -> Ganho:
    """Acerto top-1 contra a revisão, com e sem o dicionário, no mesmo texto e nas mesmas disciplinas.
    As entradas tiradas das revisões de um concurso não entram na avaliação dele."""
    contagem: dict[str, list[int]] = {}
    corrigidas: list[Mudanca] = []
    quebradas: list[Mudanca] = []
    for concurso, (edital, questoes) in revisadas.items():
        textos = {i: q.enunciado for i, q in enumerate(questoes)}
        disciplinas = {i: q.disciplina for i, q in enumerate(questoes) if q.disciplina != NAO_MAPEADO}
        antes = sugerir_topicos(edital, textos, disciplinas)
        depois = sugerir_topicos(edital, textos, disciplinas, dicionario.sem_origem(concurso), canonicas)
        for i, questao in enumerate(questoes):
            certo_antes = _acertou(antes[i].topico, questao.revisado)
            certo_depois = _acertou(depois[i].topico, questao.revisado)
            for chave in ('', questao.disciplina):
                n, a, d, ba, bd = contagem.setdefault(chave, [0, 0, 0, 0, 0])
                contagem[chave] = [
                    n + 1,
                    a + certo_antes,
                    d + certo_depois,
                    ba + (antes[i].score < SCORE_BAIXO),
                    bd + (depois[i].score < SCORE_BAIXO),
                ]
            mudanca = Mudanca(concurso, questao.questao, questao.revisado, antes[i].topico, depois[i].topico)
            if certo_depois and not certo_antes:
                corrigidas.append(mudanca)
            elif certo_antes and not certo_depois:
                quebradas.append(mudanca)
    geral = Placar(*contagem.pop('', [0, 0, 0, 0, 0]))
    return Ganho(geral, {d: Placar(*v) for d, v in sorted(contagem.items())}, corrigidas, quebradas)


def _pct(valor: float) -> str:
    return f'{100 * valor:.1f}%'.replace('.', ',')


def _pp(valor: float) -> str:
    return f'{valor:+.1f}'.replace('.', ',')


def ganho_em_markdown(ganho: Ganho) -> str:
    g = ganho.geral
    linhas = [
        '# Ganho do dicionário de temas',
        '',
        'Acerto do tópico sugerido contra as suas revisões, sem e com o dicionário (o mesmo texto, as mesmas '
        'disciplinas). Termos tirados das revisões de um concurso não entram na avaliação dele.',
        '',
        f'- Acerto: {_pct(g.taxa_antes)} → {_pct(g.taxa_depois)} (n = {g.n}; Δ {_pp(g.delta_pp)} p.p.)'
        if g.n
        else '- Nenhuma questão revisada com tópico para avaliar.',
        f'- Corrigidas: {len(ganho.corrigidas)}; quebradas: {len(ganho.quebradas)}',
        f'- Score abaixo de {SCORE_BAIXO:.2f}: {g.baixos_antes} → {g.baixos_depois}'.replace('.', ','),
        '',
    ]
    if ganho.alerta:
        linhas += ['**Atenção:** o dicionário piorou a sugestão. Desligue-o ou revise os termos.', '']
    if ganho.por_disciplina:
        linhas += [
            '## Por disciplina',
            '',
            '| Disciplina | n | Antes | Depois | Δ (p.p.) |',
            '|---|---|---|---|---|',
        ]
        for disciplina, p in ganho.por_disciplina.items():
            aviso = '' if p.amostra_suficiente else ' (amostra insuficiente)'
            linhas.append(
                f'| {disciplina}{aviso} | {p.n} | {_pct(p.taxa_antes)} | {_pct(p.taxa_depois)} | {_pp(p.delta_pp)} |'
            )
        linhas.append('')
    if ganho.quebradas:
        linhas += ['## Quebradas', '']
        linhas += [
            f'- {m.concurso}, questão {m.questao}: revisado "{m.revisado}"; antes "{m.antes}", depois "{m.depois}"'
            for m in ganho.quebradas
        ]
        linhas.append('')
    return '\n'.join(linhas)


# sugestões tiradas das revisões


@dataclass(frozen=True)
class SugestaoTermo:
    disciplina: str
    topico: str
    nome_topico: str
    termo: str
    n: int
    concursos: tuple[str, ...]

    @property
    def chave(self) -> str:
        return f'{self.disciplina}/{self.topico}/{self.termo}'


def _bigramas(palavras: list[str]) -> list[str]:
    return [f'{a} {b}' for a, b in zip(palavras, palavras[1:], strict=False)]


def sugerir_termos(
    revisadas: dict[str, tuple[Edital, list[Questao]]], dicionario: Dicionario | None = None
) -> list[SugestaoTermo]:
    """Palavras e pares de palavras que se repetem nos enunciados revisados para um mesmo tópico, em ao
    menos `MINIMO_QUESTOES_SUGESTAO` questões, e que ainda não são termo do tópico nem foram recusados."""
    dicionario = dicionario or Dicionario(())
    por_topico: dict[tuple[str, str], Counter] = {}
    concursos: dict[tuple[str, str, str], set[str]] = {}
    for concurso, (_edital, questoes) in revisadas.items():
        for questao in questoes:
            if questao.revisado == NAO_MAPEADO:
                continue
            chave = (questao.disciplina, questao.revisado)
            palavras = [p for p in _norm(questao.enunciado).split() if p in palavras_chave(p) and len(p) > 3]
            vistos = set(palavras) | set(_bigramas(palavras))
            por_topico.setdefault(chave, Counter()).update(vistos)
            for termo in vistos:
                concursos.setdefault((*chave, termo), set()).add(concurso)

    def _outros_topicos(termo: str, chave: tuple[str, str]) -> int:
        """Em quantos outros tópicos o termo também aparece: quanto menos, mais ele distingue o tópico."""
        return sum(1 for outra, c in por_topico.items() if outra != chave and termo in c)

    sugestoes = []
    for (disciplina, nome_topico), contagem in sorted(por_topico.items()):
        d_slug, t_slug = slug(disciplina), slug(' '.join(_norm(nome_topico).split()[:4]))
        ja = {
            _norm(t)
            for e in dicionario.entradas
            if e.disciplina == d_slug and e.topico == t_slug
            for t in e.termos_e_expressoes
        }
        cobertas = {
            palavra
            for termo, n in contagem.items()
            if ' ' in termo
            for palavra in termo.split()
            if contagem[palavra] == n
        }
        candidatos = sorted(
            (
                (termo, n)
                for termo, n in contagem.items()
                if n >= MINIMO_QUESTOES_SUGESTAO
                and termo not in ja
                and termo not in cobertas
                and f'{d_slug}/{t_slug}/{termo}' not in dicionario.recusados
                and not set(termo.split()) <= palavras_chave(nome_topico)
            ),
            key=lambda item: (
                -item[1],
                _outros_topicos(item[0], (disciplina, nome_topico)),
                -len(item[0].split()),
                item[0],
            ),
        )
        for termo, n in candidatos[:MAXIMO_SUGESTOES_POR_TOPICO]:
            sugestoes.append(
                SugestaoTermo(
                    d_slug,
                    t_slug,
                    nome_topico,
                    termo,
                    n,
                    tuple(sorted(concursos[(disciplina, nome_topico, termo)])),
                )
            )
    return sugestoes


def com_termo(dicionario: Dicionario, sugestao: SugestaoTermo) -> Dicionario:
    campo = 'expressoes' if ' ' in sugestao.termo else 'termos'
    entradas = list(dicionario.entradas)
    for i, entrada in enumerate(entradas):
        if entrada.disciplina == sugestao.disciplina and entrada.topico == sugestao.topico:
            entradas[i] = replace(
                entrada,
                nomes=entrada.nomes or (sugestao.nome_topico,),
                origem=tuple(dict.fromkeys((*entrada.origem, *sugestao.concursos))),
                **{campo: (*getattr(entrada, campo), sugestao.termo)},
            )
            return Dicionario(tuple(entradas), dicionario.recusados)
    nova = EntradaTema(
        sugestao.disciplina,
        sugestao.topico,
        (sugestao.nome_topico,),
        () if ' ' in sugestao.termo else (sugestao.termo,),
        (sugestao.termo,) if ' ' in sugestao.termo else (),
        sugestao.concursos,
    )
    return Dicionario((*entradas, nova), dicionario.recusados)


def com_recusa(dicionario: Dicionario, sugestao: SugestaoTermo) -> Dicionario:
    return Dicionario(dicionario.entradas, dicionario.recusados | {sugestao.chave})
