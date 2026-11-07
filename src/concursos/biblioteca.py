"""Fontes de estudo para os tópicos fracos: os livros da biblioteca do app, o mapa disciplina → estante, o
catálogo do projeto `books`, a busca de texto nos notebooks de biblioteca do open-notebook e as normas do
clone do `ctresb/leis`.

Tudo aqui é sugestão: nada troca o tópico ou a disciplina de uma questão.
"""

import logging
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from concursos.analytics.consolidado import N_MINIMO_TOPICO, PASTA_CONSOLIDADO, carregar_consolidado
from concursos.analytics.correcao import ARQUIVO_CORRECAO
from concursos.analytics.insights import calcular_achados
from concursos.analytics.taxonomia import DisciplinaCanonica, carregar_taxonomia
from concursos.arquivos import gravar_se_mudou
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.integracoes.open_notebook import ClienteOpenNotebook, OpenNotebookIndisponivelError
from concursos.legislacao import avisos_da_norma, extrair_citacoes, ler_repositorio, normas_citadas
from concursos.livros import indice as indice_livros
from concursos.modelo import FonteRecomendacao
from concursos.texto import abreviar
from concursos.topicos import palavras_chave

logger = logging.getLogger(__name__)

ARQUIVO_MAPA = 'biblioteca.yaml'
ARQUIVO_RECOMENDACOES = 'recomendacoes_estudo.md'
PREFIXO_NOTEBOOK = 'Biblioteca — '
LIVROS_POR_TOPICO = 3
MAXIMO_CONSULTAS = 4
MINIMO_PALAVRAS_CONSULTA = 2
MAXIMO_NOTEBOOKS_BUSCA = 50
TITULO_NOTA = 'concurso-analise: recomendações de estudo'
_SEPARADORES_DE_CONSULTA = re.compile(r'[.:;()]')
_ROTULO_DA_FONTE = {
    FonteRecomendacao.LEGISLACAO: 'legislação',
    FonteRecomendacao.LIVROS: 'meus livros',
    FonteRecomendacao.OPEN_NOTEBOOK: 'open-notebook',
    FonteRecomendacao.CATALOGO: 'catálogo',
}


@dataclass(frozen=True)
class MapaBiblioteca:
    """`.concurso/biblioteca.yaml`: disciplina canônica → categorias `<main> › <sub>` da estante."""

    disciplinas: dict[str, tuple[str, ...]]
    catalogo: Path | None = None
    por_disciplina: bool = False
    """Com os livros da biblioteca do app, a própria disciplina também é categoria."""

    def categorias(self, disciplina: str) -> tuple[str, ...]:
        mapeadas = self.disciplinas.get(disciplina, ())
        return tuple(dict.fromkeys((*mapeadas, disciplina))) if self.por_disciplina else mapeadas

    @property
    def todas_as_categorias(self) -> list[str]:
        return sorted({categoria for categorias in self.disciplinas.values() for categoria in categorias})


def ler_mapa(arquivo: Path, taxonomia: dict[str, DisciplinaCanonica], raiz: Path) -> MapaBiblioteca | None:
    """None sem o arquivo; o catálogo relativo é resolvido a partir da raiz do projeto."""
    if not arquivo.exists():
        return None
    dados = yaml.safe_load(arquivo.read_text(encoding='utf-8')) or {}
    if not isinstance(dados, dict) or not isinstance(dados.get('disciplinas', {}), dict):
        raise ConfiguracaoInvalidaError(
            f'{arquivo}: esperado `disciplinas:` como mapa de disciplina para categorias'
        )
    canonicas = sorted({disciplina.nome for disciplina in taxonomia.values()})
    disciplinas: dict[str, tuple[str, ...]] = {}
    for disciplina, categorias in (dados.get('disciplinas') or {}).items():
        if canonicas and disciplina not in canonicas:
            raise ConfiguracaoInvalidaError(
                f"{arquivo}: disciplina '{disciplina}' fora da taxonomia; use uma de: {', '.join(canonicas)}"
            )
        if isinstance(categorias, str):
            categorias = [categorias]
        if not isinstance(categorias, list) or not all(isinstance(c, str) for c in categorias):
            raise ConfiguracaoInvalidaError(f"{arquivo}: '{disciplina}' precisa de uma lista de categorias")
        disciplinas[disciplina] = tuple(categorias)
    catalogo = dados.get('catalogo')
    caminho = None
    if catalogo:
        caminho = Path(str(catalogo)).expanduser()
        caminho = caminho if caminho.is_absolute() else (raiz / caminho).resolve()
    return MapaBiblioteca(disciplinas, caminho)


@dataclass(frozen=True)
class FontesDeEstudo:
    """O mapa da estante e o clone das leis de uma execução; sem nenhum dos dois, nada muda nas saídas."""

    mapa: MapaBiblioteca | None
    repositorio: Path | None
    taxonomia: dict[str, DisciplinaCanonica] = field(default_factory=dict)

    @property
    def vazias(self) -> bool:
        return self.mapa is None and self.repositorio is None


def ler_fontes_de_estudo(
    pasta_projeto: Path, raiz: Path, arquivo_taxonomia: Path, config_global: Path
) -> FontesDeEstudo:
    taxonomia = carregar_taxonomia(arquivo_taxonomia) if arquivo_taxonomia.exists() else {}
    return FontesDeEstudo(
        ler_mapa(pasta_projeto / ARQUIVO_MAPA, taxonomia, raiz), ler_repositorio(config_global), taxonomia
    )


@dataclass(frozen=True)
class Livro:
    titulo: str
    autor: str
    arquivo: str
    categoria: str


def ler_catalogo(caminho: Path) -> tuple[dict[str, list[Livro]], list[str]]:
    """As tabelas Título | Autor | Arquivo do `Bookshelf/README.md`, por seção `## <main> › <sub>`."""
    livros: dict[str, list[Livro]] = {}
    avisos: list[str] = []
    categoria: str | None = None
    for linha in caminho.read_text(encoding='utf-8').splitlines():
        if linha.startswith('## '):
            titulo = linha[3:].strip()
            categoria = titulo if ' › ' in titulo else None
            if categoria is None and titulo.lower() not in ('índice', 'indice'):
                avisos.append(f'{caminho}: seção sem categoria ignorada: {titulo}')
            if categoria is not None:
                livros.setdefault(categoria, [])
            continue
        if categoria is None or not linha.startswith('|'):
            continue
        celulas = [c.replace('\\|', '|').strip() for c in re.split(r'(?<!\\)\|', linha.strip())[1:-1]]
        if len(celulas) != 3 or celulas[0] in ('Título', '') or set(celulas[0]) <= set('-: '):
            continue
        titulo, autor, arquivo = celulas
        livros[categoria].append(Livro(titulo, '' if autor == '—' else autor, arquivo.strip('`'), categoria))
    return livros, avisos


def validar_categorias(mapa: MapaBiblioteca, conhecidas: set[str]) -> list[str]:
    """Categorias do mapa sem notebook nem seção no catálogo: só aviso, o resto segue."""
    return [
        f"biblioteca: categoria '{categoria}' não aparece na estante nem no open-notebook"
        for categoria in mapa.todas_as_categorias
        if categoria not in conhecidas
    ]


def consultas_do_topico(topico: str) -> list[str]:
    """Trechos curtos do tópico do edital, que costuma ser um parágrafo, para a busca por texto achar algo."""
    consultas: list[str] = []
    for parte in _SEPARADORES_DE_CONSULTA.split(topico):
        parte = ' '.join(parte.split()).strip(' ,-–')
        if len(palavras_chave(parte)) >= MINIMO_PALAVRAS_CONSULTA and parte not in consultas:
            consultas.append(parte)
    return consultas[:MAXIMO_CONSULTAS] or [' '.join(topico.split())[:200]]


@dataclass(frozen=True)
class Recomendacao:
    titulo: str
    origem: str
    fonte: FonteRecomendacao
    detalhe: str | None = None

    def em_markdown(self) -> str:
        detalhe = f'. {self.detalhe}' if self.detalhe else ''
        return f'- [{_ROTULO_DA_FONTE[self.fonte]}] {self.titulo} ({self.origem}){detalhe}'


@dataclass
class IndiceBiblioteca:
    """Os notebooks de biblioteca da instância e as sources de cada um, lidos uma vez por execução."""

    notebooks: dict[str, str]
    sources: dict[str, dict[str, str]] = field(default_factory=dict)
    """categoria → id da source → título."""

    def ids_das_sources(self, categorias: tuple[str, ...]) -> set[str]:
        return {source for categoria in categorias for source in self.sources.get(categoria, {})}

    def categoria_da_source(self, source_id: str) -> str | None:
        return next((c for c, sources in self.sources.items() if source_id in sources), None)


def indexar_biblioteca(cliente: ClienteOpenNotebook, mapa: MapaBiblioteca) -> IndiceBiblioteca:
    """Levanta OpenNotebookIndisponivelError; quem chama decide se cai para o catálogo."""
    por_nome = {}
    for notebook in cliente.listar_notebooks():
        por_nome.setdefault(notebook.get('name'), notebook['id'])
    indice = IndiceBiblioteca({})
    for categoria in mapa.todas_as_categorias:
        notebook_id = por_nome.get(f'{PREFIXO_NOTEBOOK}{categoria}')
        if notebook_id is None:
            continue
        indice.notebooks[categoria] = notebook_id
        indice.sources[categoria] = {
            s['id']: s.get('title') or s['id'] for s in cliente.listar_sources(notebook_id)
        }
    return indice


@dataclass
class BuscaBiblioteca:
    cliente: ClienteOpenNotebook
    indice: IndiceBiblioteca

    @property
    def conhecidas(self) -> set[str]:
        return set(self.indice.notebooks)

    def livros(self, categorias: tuple[str, ...], topico: str) -> list[Recomendacao]:
        ids = [self.indice.notebooks[c] for c in categorias if c in self.indice.notebooks][
            :MAXIMO_NOTEBOOKS_BUSCA
        ]
        if not ids:
            return []
        melhores: dict[str, tuple[float, str]] = {}
        for consulta in consultas_do_topico(topico):
            for resultado in self.cliente.buscar_texto(consulta, ids):
                source_id = resultado.get('parent_id') or resultado.get('id')
                relevancia = float(resultado.get('relevance') or 0)
                titulo = resultado.get('title') or source_id
                if relevancia > melhores.get(source_id, (-1.0, ''))[0]:
                    melhores[source_id] = (relevancia, titulo)
        ordenados = sorted(melhores.items(), key=lambda par: (-par[1][0], par[1][1]))[:LIVROS_POR_TOPICO]
        return [
            Recomendacao(
                titulo,
                f'{PREFIXO_NOTEBOOK}{self.indice.categoria_da_source(source_id) or "?"}',
                FonteRecomendacao.OPEN_NOTEBOOK,
                f'relevância {_numero(relevancia)}',
            )
            for source_id, (relevancia, titulo) in ordenados
        ]


@dataclass
class BuscaLocal:
    """Os livros da biblioteca do app, pelo índice local: não precisa do open-notebook aberto."""

    banco: Path
    por_disciplina: dict[str, dict[str, str]]
    """disciplina → sha → nome do livro."""

    @property
    def conhecidas(self) -> set[str]:
        return set(self.por_disciplina)

    def livros(self, categorias: tuple[str, ...], topico: str) -> list[Recomendacao]:
        nomes = {sha: nome for c in categorias for sha, nome in self.por_disciplina.get(c, {}).items()}
        if not nomes or not self.banco.exists():
            return []
        melhores: dict[str, tuple[float, int]] = {}
        conexao = indice_livros.abrir(self.banco)
        try:
            for consulta in consultas_do_topico(topico):
                for trecho in indice_livros.buscar(conexao, consulta, shas=list(nomes)):
                    if trecho.relevancia > melhores.get(trecho.sha, (float('-inf'), 0))[0]:
                        melhores[trecho.sha] = (trecho.relevancia, trecho.pagina)
        finally:
            conexao.close()
        ordenados = sorted(melhores.items(), key=lambda par: (-par[1][0], nomes[par[0]]))[:LIVROS_POR_TOPICO]
        return [
            Recomendacao(nomes[sha], 'Meus livros', FonteRecomendacao.LIVROS, f'p. {pagina}')
            for sha, (_relevancia, pagina) in ordenados
        ]


def recomendar_por_catalogo(
    categorias: tuple[str, ...], topico: str, catalogo: dict[str, list[Livro]]
) -> list[Recomendacao]:
    """Os livros das categorias mapeadas, primeiro os que dividem palavras com o tópico."""
    palavras = palavras_chave(topico)
    livros = [livro for categoria in categorias for livro in catalogo.get(categoria, [])]
    ordenados = sorted(
        livros, key=lambda livro: (-len(palavras & palavras_chave(livro.titulo)), livro.titulo)
    )
    return [
        Recomendacao(
            f'{livro.titulo} — {livro.autor}' if livro.autor else livro.titulo,
            livro.categoria,
            FonteRecomendacao.CATALOGO,
        )
        for livro in ordenados[:LIVROS_POR_TOPICO]
    ]


def recomendar_por_legislacao(topico: str, repositorio: Path) -> list[Recomendacao]:
    recomendacoes = []
    for norma, citacao in normas_citadas(extrair_citacoes(topico), repositorio).values():
        partes = [f'citada como "{citacao.trecho}"']
        if norma.fonte:
            partes.append(f'fonte: {norma.fonte}')
        partes.append(f'arquivo: {norma.relativo}')
        partes += [f'aviso: {aviso}' for aviso in avisos_da_norma(norma)]
        ementa = f' — {abreviar(" ".join(str(norma.ementa).split()), 160)}' if norma.ementa else ''
        recomendacoes.append(
            Recomendacao(
                f'{norma.titulo}{ementa}',
                'clone do ctresb/leis',
                FonteRecomendacao.LEGISLACAO,
                '; '.join(partes),
            )
        )
    return recomendacoes


def recomendar_pela_pratica(textos: Sequence[str], repositorio: Path) -> list[Recomendacao]:
    """As normas do clone citadas nos erros do TEC, das mais citadas para as menos."""
    contagem: Counter[str] = Counter()
    normas = {}
    for texto in textos:
        citadas = normas_citadas(extrair_citacoes(texto), repositorio)
        contagem.update(citadas.keys())
        normas |= {chave: norma for chave, (norma, _) in citadas.items()}
    recomendacoes = []
    for chave, vezes in sorted(contagem.items(), key=lambda par: (-par[1], par[0])):
        norma = normas[chave]
        partes = [f'citada em {vezes} erro{"s" if vezes > 1 else ""}', f'arquivo: {norma.relativo}']
        partes += [f'aviso: {aviso}' for aviso in avisos_da_norma(norma)]
        recomendacoes.append(
            Recomendacao(
                norma.titulo, 'clone do ctresb/leis', FonteRecomendacao.LEGISLACAO, '; '.join(partes)
            )
        )
    return recomendacoes


@dataclass
class ResultadoRecomendacoes:
    texto: str
    avisos: list[str]
    fontes: set[FonteRecomendacao]


def recomendar(
    fracos: pd.DataFrame,
    limiar: float,
    mapa: MapaBiblioteca | None,
    repositorio: Path | None,
    busca: BuscaBiblioteca | BuscaLocal | None = None,
    avisos: list[str] | None = None,
    textos_pratica: Sequence[str] = (),
) -> ResultadoRecomendacoes:
    """O markdown das recomendações para `fracos` (de `topicos_fracos`); cada camada que falha vira aviso e
    a próxima é tentada. `textos_pratica` são enunciados e comentários dos erros do TEC."""
    avisos = list(avisos or [])
    catalogo: dict[str, list[Livro]] = {}
    if mapa is not None and mapa.catalogo is not None:
        if mapa.catalogo.exists():
            catalogo, avisos_catalogo = ler_catalogo(mapa.catalogo)
            avisos += avisos_catalogo
        else:
            avisos.append(f'biblioteca: catálogo {mapa.catalogo} não encontrado')
    if mapa is not None:
        conhecidas = set(catalogo) | (busca.conhecidas if busca else set())
        avisos += validar_categorias(mapa, conhecidas)
    if repositorio is not None and not repositorio.is_dir():
        avisos.append(f'legislação: {repositorio} não existe; clone o ctresb/leis ou corrija [legislacao]')
        repositorio = None
    fontes: set[FonteRecomendacao] = set()
    sem_mapa: set[str] = set()
    secoes: list[str] = []
    for linha in fracos.itertuples():
        itens: list[Recomendacao] = []
        if repositorio is not None:
            itens += recomendar_por_legislacao(str(linha.topico), repositorio)
        categorias = mapa.categorias(linha.disciplina) if mapa else ()
        if mapa is not None and not categorias:
            sem_mapa.add(linha.disciplina)
        livros: list[Recomendacao] = []
        if categorias and busca is not None:
            try:
                livros = busca.livros(categorias, str(linha.topico))
            except OpenNotebookIndisponivelError as erro:
                avisos.append(f'open-notebook: busca indisponível ({erro.causa}); seguindo com o catálogo')
                busca = None
        if categorias and not livros:
            livros = recomendar_por_catalogo(categorias, str(linha.topico), catalogo)
        itens += livros
        fontes |= {item.fonte for item in itens}
        secoes += _secao(linha, itens)
    da_pratica = recomendar_pela_pratica(textos_pratica, repositorio) if repositorio is not None else []
    fontes |= {item.fonte for item in da_pratica}
    texto = _markdown(secoes, limiar, sorted(sem_mapa), bool(len(fracos)), da_pratica)
    for aviso in avisos:
        logger.warning(aviso)
    return ResultadoRecomendacoes(texto, avisos, fontes)


def gravar_recomendacoes(pasta_candidato: Path, resultado: ResultadoRecomendacoes) -> bool:
    destino = pasta_candidato / PASTA_CONSOLIDADO / ARQUIVO_RECOMENDACOES
    destino.parent.mkdir(parents=True, exist_ok=True)
    return gravar_se_mudou(destino, resultado.texto)


def topicos_fracos(
    raiz_provas: Path, pasta_candidato: Path, arquivo_taxonomia: Path, limiar: float
) -> tuple[pd.DataFrame, list[str]]:
    """Os tópicos fracos persistentes de `insights`; sem evolução, uma tabela vazia e o motivo."""
    vazio = pd.DataFrame(columns=['disciplina', 'topico', 'n', 'percentual', 'concursos_abaixo'])
    if not any(pasta_candidato.glob(f'*/{ARQUIVO_CORRECAO}')):
        return vazio, []
    try:
        consolidado = carregar_consolidado(raiz_provas, pasta_candidato, arquivo_taxonomia)
        return (calcular_achados(consolidado, limiar).fracos if not consolidado.empty else vazio), []
    except Exception as erro:  # noqa: BLE001 - sem evolução, as recomendações saem vazias com o motivo
        return vazio, [f'recomendações sem tópicos fracos: {erro}']


def _secao(linha, itens: list[Recomendacao]) -> list[str]:
    concursos = ', '.join(linha.concursos_abaixo) if isinstance(linha.concursos_abaixo, list) else ''
    return [
        f'## {linha.disciplina}: {abreviar(str(linha.topico), 120)}',
        '',
        f'n = {int(linha.n)}, percentual ajustado = {_numero(linha.percentual)}%'
        + (f' (abaixo do limiar em: {concursos})' if concursos else ''),
        '',
        *([item.em_markdown() for item in itens] or ['- Sem livro na estante nem norma citada.']),
        '',
    ]


def _markdown(
    secoes: list[str], limiar: float, sem_mapa: list[str], tem_fracos: bool, da_pratica: list[Recomendacao]
) -> str:
    linhas = [
        '# Recomendações de estudo',
        '',
        f'Para os tópicos abaixo de {_numero(limiar * 100)}% (percentual ajustado) em mais de um concurso, com '
        f'n ≥ {N_MINIMO_TOPICO}. São sugestões: não mudam o tópico nem a disciplina de nenhuma questão.',
        '',
    ]
    linhas += secoes if tem_fracos else ['Nenhum tópico fraco persistente.', '']
    if da_pratica:
        linhas += [
            '## Normas citadas nos seus erros do TEC',
            '',
            *(item.em_markdown() for item in da_pratica),
            '',
        ]
    if sem_mapa:
        linhas += ['## Disciplinas sem livros mapeados', '', *(f'- {d}' for d in sem_mapa), '']
    return '\n'.join(linhas).rstrip() + '\n'


def _numero(valor: float) -> str:
    return f'{float(valor):.1f}'.replace('.', ',')


def disciplinas_do_concurso(pasta_analise: Path, taxonomia: dict[str, DisciplinaCanonica]) -> set[str]:
    """As disciplinas canônicas cobradas no concurso, pelo `questoes.csv`."""
    caminho = pasta_analise / 'questoes.csv'
    if not caminho.exists():
        return set()
    brutas = set(pd.read_csv(caminho, usecols=['disciplina'], keep_default_na=False)['disciplina'])
    return {taxonomia[bruta].nome if bruta in taxonomia else bruta for bruta in brutas}
