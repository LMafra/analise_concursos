"""O que vai para o open-notebook, com que título, e a sincronização idempotente pelo estado local."""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

from concursos.analytics.consolidado import (
    N_MINIMO_TOPICO,
    PASTA_CONSOLIDADO,
    concursos_analisados,
    construir_consolidado,
)
from concursos.analytics.correcao import ARQUIVO_CORRECAO
from concursos.analytics.insights import calcular_achados, notas_finais_em_markdown, respostas_em_markdown
from concursos.arquivos import gravar_se_mudou
from concursos.biblioteca import (
    ARQUIVO_RECOMENDACOES,
    TITULO_NOTA,
    FontesDeEstudo,
    disciplinas_do_concurso,
    indexar_biblioteca,
)
from concursos.erros import avisar
from concursos.integracoes.open_notebook import ClienteOpenNotebook, OpenNotebookIndisponivelError
from concursos.legislacao import (
    citacoes_do_edital,
    conteudo_para_notebook,
    normas_citadas,
    titulo_para_notebook,
)
from concursos.relatorio_html import ARQUIVO_INDICE
from concursos.texto import abreviar
from concursos.topicos import NAO_MAPEADO

logger = logging.getLogger(__name__)

PREFIXO = 'concurso-analise: '
ARQUIVO_ESTADO = 'open_notebook.json'
DESCRICAO = 'gerado por concurso-analise'
TITULO_RESUMO = f'{PREFIXO}resumo executivo'
CHAVE_CONSOLIDADO = '_consolidado'
CHAVE_LEGISLACAO = '_legislacao'
NOME_LEGISLACAO = 'Legislação'
CHAVE_CADERNO_DE_ERROS = '_caderno_de_erros'
PASTA_CADERNO_DE_ERROS = 'caderno de erros'
ARTEFATOS_DO_CONCURSO = (
    'relatorio.md',
    'desempenho_por_disciplina.csv',
    'desempenho_por_topico.csv',
    'questoes.csv',
    'edital_estruturado.json',
    'catalogo_edital.md',
)
ARTEFATOS_DO_CONSOLIDADO = (
    'consolidado/desempenho_geral.csv',
    'consolidado/comparativo_concursos.md',
    'consolidado/relatorio_evolucao.md',
)
_VERSAO_ESTADO = 1


@dataclass(frozen=True)
class Documento:
    """Uma source ou nota: `chave` identifica o documento no estado, `titulo` no open-notebook."""

    chave: str
    titulo: str
    conteudo: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.conteudo.encode('utf-8')).hexdigest()


def titulo_da_source(concurso: str, arquivo: str) -> str:
    return f'{PREFIXO}{concurso}/{arquivo}'


def artefatos_do_concurso(pasta: Path, concurso: str) -> tuple[list[Documento], list[str]]:
    """Os documentos do concurso e os artefatos que faltam (o relatorio.html fica de fora: duplica o .md)."""
    documentos, ausentes = [], []
    for nome in ARTEFATOS_DO_CONCURSO:
        caminho = pasta / nome
        if not caminho.exists():
            ausentes.append(nome)
            continue
        cabecalho = f'Arquivo: {nome}; concurso: {concurso}'
        documentos.append(Documento(nome, titulo_da_source(concurso, nome), _conteudo(caminho, cabecalho)))
    return documentos, ausentes


def artefatos_do_consolidado(pasta_candidato: Path, incluir_nome: bool) -> tuple[list[Documento], list[str]]:
    """O `index.html` traz o nome do candidato e só vai com `incluir_nome`."""
    nomes = [*ARTEFATOS_DO_CONSOLIDADO, *([ARQUIVO_INDICE] if incluir_nome else [])]
    documentos, ausentes = [], []
    for nome in nomes:
        caminho = pasta_candidato / nome
        if not caminho.exists():
            ausentes.append(nome)
            continue
        cabecalho = f'Arquivo: {nome}; visão consolidada de todos os concursos'
        documentos.append(
            Documento(nome, titulo_da_source('consolidado', nome), _conteudo(caminho, cabecalho))
        )
    return documentos, ausentes


def _conteudo(caminho: Path, cabecalho: str) -> str:
    texto = caminho.read_text(encoding='utf-8')
    if caminho.suffix == '.json':
        texto = json.dumps(json.loads(texto), indent=2, ensure_ascii=False)
    elif caminho.suffix == '.html':
        texto = texto_do_html(texto)
    return f'{cabecalho}\n\n{texto.strip()}\n'


class _Texto(HTMLParser):
    _IGNORADAS = {'script', 'style', 'head'}

    def __init__(self) -> None:
        super().__init__()
        self.partes: list[str] = []
        self._ignorando = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._IGNORADAS:
            self._ignorando += 1
        elif tag in {'p', 'br', 'tr', 'li', 'h1', 'h2', 'h3', 'h4', 'div', 'table'}:
            self.partes.append('\n')

    def handle_endtag(self, tag: str) -> None:
        if tag in self._IGNORADAS and self._ignorando:
            self._ignorando -= 1
        elif tag in {'td', 'th'}:
            self.partes.append(' | ')

    def handle_data(self, data: str) -> None:
        if not self._ignorando:
            self.partes.append(data)


def texto_do_html(html: str) -> str:
    leitor = _Texto()
    leitor.feed(html)
    linhas = (' '.join(linha.split()) for linha in ''.join(leitor.partes).splitlines())
    return '\n'.join(linha for linha in linhas if linha)


def resumo_do_concurso(pasta: Path, concurso: str, limiar: float) -> Documento:
    """Nota de resumo montada só com os CSVs locais; nenhum LLM é chamado."""
    linhas = [f'# Resumo executivo: {concurso}', '']
    disciplinas = _csv(pasta / 'desempenho_por_disciplina.csv')
    if disciplinas is not None and not disciplinas.empty:
        total, acertos = int(disciplinas['total'].sum()), int(disciplinas['acertos'].sum())
        nota = float(disciplinas['nota_liquida'].sum())
        maxima = _nota_maxima(pasta)
        linhas += [
            f'- Acertos: {acertos} de {total} questões ({_percentual(acertos, total)}).',
            f'- Nota líquida: {_numero(nota)}' + (f' de {_numero(maxima)}.' if maxima else '.'),
        ]
        ordenadas = disciplinas.sort_values('percentual')
        pior, melhor = ordenadas.iloc[0], ordenadas.iloc[-1]
        linhas += [
            f'- Disciplina mais fraca: {pior["disciplina"]} ({_numero(pior["percentual"])}%, n={int(pior["total"])}).',
            f'- Disciplina mais forte: {melhor["disciplina"]} ({_numero(melhor["percentual"])}%, n={int(melhor["total"])}).',
        ]
    linhas += ['', *_topicos_fracos(_csv(pasta / 'desempenho_por_topico.csv'), limiar)]
    return Documento('resumo', TITULO_RESUMO, '\n'.join(linhas) + '\n')


def _topicos_fracos(topicos: pd.DataFrame | None, limiar: float) -> list[str]:
    titulo = f'## Tópicos abaixo de {_numero(limiar * 100)}% (n ≥ {N_MINIMO_TOPICO})'
    if topicos is None or topicos.empty:
        return [titulo, '', 'Sem desempenho por tópico.']
    mapeados = topicos[topicos['topico'] != NAO_MAPEADO]
    suficientes = mapeados[mapeados['total'] >= N_MINIMO_TOPICO]
    fracos = suficientes[suficientes['percentual'] < limiar * 100].sort_values('percentual')
    itens = [
        f'- {linha.disciplina}: {abreviar(str(linha.topico), 120)} ({_numero(linha.percentual)}%, n={int(linha.total)})'
        for linha in fracos.itertuples()
    ]
    insuficientes = len(mapeados) - len(suficientes)
    rodape = [f'{insuficientes} tópicos com n < {N_MINIMO_TOPICO} ficaram de fora (amostra insuficiente).']
    return [titulo, '', *(itens or ['Nenhum tópico abaixo do limiar.']), '', *rodape]


def resumo_do_consolidado(
    raiz_provas: Path, pasta_candidato: Path, arquivo_taxonomia: Path, limiar: float
) -> Documento:
    """As respostas da análise evolutiva (`insights`), sem gravar o cache do consolidado."""
    linhas = ['# Resumo executivo: todos os concursos', '']
    try:
        consolidado = construir_consolidado(raiz_provas, pasta_candidato, arquivo_taxonomia)
        if consolidado.empty:
            raise ValueError('nenhum concurso analisado')
        linhas += [
            respostas_em_markdown(calcular_achados(consolidado, limiar)),
            '',
            '## Nota final pela regra do edital',
            '',
            notas_finais_em_markdown(consolidado),
        ]
    except Exception as erro:  # noqa: BLE001 - a nota sai sem a evolução, com o motivo
        avisar(
            logger,
            'open-notebook: o resumo de todos os concursos foi sem a evolução.',
            detalhe=f'resumo consolidado sem a evolução: {erro}',
        )
        linhas.append(f'Evolução indisponível: {erro}')
    return Documento('resumo', TITULO_RESUMO, '\n'.join(linhas) + '\n')


def _csv(caminho: Path) -> pd.DataFrame | None:
    return pd.read_csv(caminho, keep_default_na=False) if caminho.exists() else None


def _nota_maxima(pasta: Path) -> float | None:
    caminho = pasta / ARQUIVO_CORRECAO
    if not caminho.exists():
        return None
    regras = json.loads(caminho.read_text(encoding='utf-8'))
    regras = regras if isinstance(regras, list) else [regras]
    maximas = {regra.get('nota_maxima') for regra in regras if regra.get('nota_maxima')}
    return maximas.pop() if len(maximas) == 1 else None


def _percentual(parte: int, total: int) -> str:
    return f'{_numero(100 * parte / total)}%' if total else '-'


def _numero(valor: float) -> str:
    return f'{float(valor):.2f}'.rstrip('0').rstrip('.').replace('.', ',')


@dataclass
class EstadoSincronizacao:
    """`.concurso/open_notebook.json`: por instância, os pseudônimos e o que cada notebook já recebeu."""

    caminho: Path
    dados: dict = field(default_factory=dict)

    @classmethod
    def ler(cls, caminho: Path) -> 'EstadoSincronizacao':
        dados = json.loads(caminho.read_text(encoding='utf-8')) if caminho.exists() else {}
        return cls(caminho, dados if dados.get('versao') == _VERSAO_ESTADO else {'versao': _VERSAO_ESTADO})

    def instancia(self, url: str) -> dict:
        self.dados.setdefault('versao', _VERSAO_ESTADO)
        return self.dados.setdefault('instancias', {}).setdefault(url, {'pseudonimos': {}, 'notebooks': {}})

    def rotulo(self, url: str, candidato: str | None, incluir_nome: bool) -> str:
        if incluir_nome and candidato:
            return candidato
        pseudonimos = self.instancia(url)['pseudonimos']
        chave = candidato or ''
        if chave not in pseudonimos:
            pseudonimos[chave] = f'candidato {len(pseudonimos) + 1}'
        return pseudonimos[chave]

    def notebook(self, url: str, chave: str) -> dict:
        registro = self.instancia(url)['notebooks'].setdefault(chave, {})
        for campo in ('sources', 'notas', 'vinculos'):
            registro.setdefault(campo, {})
        return registro

    def gravar(self) -> bool:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        return gravar_se_mudou(
            self.caminho, json.dumps(self.dados, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
        )


@dataclass
class RelatorioSincronizacao:
    notebooks_criados: list[str] = field(default_factory=list)
    notebooks_reusados: list[str] = field(default_factory=list)
    sources_enviadas: int = 0
    sources_trocadas: int = 0
    sources_puladas: int = 0
    notas_criadas: int = 0
    notas_atualizadas: int = 0
    notas_puladas: int = 0
    vinculos_criados: int = 0
    vinculos_removidos: int = 0
    avisos: list[str] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)

    @property
    def sucesso(self) -> bool:
        return not self.falhas

    def formatar(self) -> str:
        linhas = [
            f'notebooks: {len(self.notebooks_criados)} criados, {len(self.notebooks_reusados)} reusados',
            f'sources: {self.sources_enviadas} enviadas, {self.sources_trocadas} trocadas, '
            f'{self.sources_puladas} sem mudança',
            f'notas: {self.notas_criadas} criadas, {self.notas_atualizadas} atualizadas, '
            f'{self.notas_puladas} sem mudança',
        ]
        if self.vinculos_criados or self.vinculos_removidos:
            linhas.append(f'vínculos: {self.vinculos_criados} criados, {self.vinculos_removidos} removidos')
        linhas += [f'aviso: {aviso}' for aviso in self.avisos]
        linhas += [f'falha: {falha}' for falha in self.falhas]
        return '\n'.join(linhas)


@dataclass
class Sincronizador:
    cliente: ClienteOpenNotebook
    estado: EstadoSincronizacao
    relatorio: RelatorioSincronizacao = field(default_factory=RelatorioSincronizacao)
    embed: bool = False
    instancia: str | None = None
    por_nome: bool = True
    prefixo_nome: str = ''

    @property
    def url(self) -> str:
        """A chave da instância no estado; a gerenciada muda de porta a cada sessão e usa `instancia`."""
        return self.instancia or self.cliente.url

    def notebook(
        self,
        chave: str,
        nome: str,
        documentos: list[Documento],
        notas: list[Documento],
        compartilhado: bool = False,
    ) -> str | None:
        """Garante o notebook, as sources e as notas; uma falha entra no relatório e não para as demais.

        Sem `por_nome`, um notebook do projeto é achado só pelo ID guardado; um `compartilhado` entre os
        projetos (`Legislação`) também pelo nome."""
        registro = self.estado.notebook(self.url, chave)
        if not compartilhado:
            nome = f'{self.prefixo_nome}{nome}'
        try:
            notebook_id = self._garantir_notebook(registro, nome, self.por_nome or compartilhado)
            remotas = self.cliente.listar_sources(notebook_id)
        except OpenNotebookIndisponivelError as erro:
            self.relatorio.falhas.append(f'{nome}: {erro.causa}')
            return None
        for documento in documentos:
            try:
                self._source(notebook_id, registro, remotas, documento)
            except OpenNotebookIndisponivelError as erro:
                self.relatorio.falhas.append(f'{nome} / {documento.chave}: {erro.causa}')
        if notas:
            try:
                existentes = self.cliente.listar_notas(notebook_id)
            except OpenNotebookIndisponivelError as erro:
                self.relatorio.falhas.append(f'{nome} / notas: {erro.causa}')
                existentes = None
            for nota in notas if existentes is not None else []:
                try:
                    self._nota(notebook_id, registro, existentes, nota)
                except OpenNotebookIndisponivelError as erro:
                    self.relatorio.falhas.append(f'{nome} / {nota.titulo}: {erro.causa}')
        return notebook_id

    def vinculos(self, chave: str, desejados: set[str]) -> None:
        """Vincula as sources desejadas ao notebook já sincronizado e desfaz só os vínculos que o app criou."""
        registro = self.estado.notebook(self.url, chave)
        notebook_id = registro.get('id')
        if not notebook_id or (not desejados and not registro['vinculos']):
            return
        try:
            remotas = {s['id'] for s in self.cliente.listar_sources(notebook_id)}
        except OpenNotebookIndisponivelError as erro:
            self.relatorio.falhas.append(f'{registro.get("nome")} / vínculos: {erro.causa}')
            return
        for source_id in sorted(desejados - remotas):
            try:
                self.cliente.vincular_source(notebook_id, source_id)
                registro['vinculos'][source_id] = True
                self.relatorio.vinculos_criados += 1
            except OpenNotebookIndisponivelError as erro:
                self.relatorio.falhas.append(f'{registro.get("nome")} / vínculo {source_id}: {erro.causa}')
        for source_id in sorted(set(registro['vinculos']) - desejados):
            if source_id not in remotas:
                del registro['vinculos'][source_id]
                continue
            try:
                self.cliente.desvincular_source(notebook_id, source_id)
                del registro['vinculos'][source_id]
                self.relatorio.vinculos_removidos += 1
            except OpenNotebookIndisponivelError as erro:
                self.relatorio.falhas.append(f'{registro.get("nome")} / vínculo {source_id}: {erro.causa}')

    def gravar_estado(self) -> bool:
        return self.estado.gravar()

    def _garantir_notebook(self, registro: dict, nome: str, por_nome: bool) -> str:
        notebook_id = registro.get('id')
        if notebook_id and self.cliente.obter_notebook(notebook_id) is not None:
            self.relatorio.notebooks_reusados.append(nome)
        elif por_nome and (existente := self.cliente.buscar_notebook_por_nome(nome)):
            notebook_id = existente['id']
            self.relatorio.notebooks_reusados.append(nome)
        else:
            notebook_id = self.cliente.criar_notebook(nome, DESCRICAO)['id']
            self.relatorio.notebooks_criados.append(nome)
        registro.update(id=notebook_id, nome=nome)
        return notebook_id

    def _source(self, notebook_id: str, registro: dict, remotas: list[dict], documento: Documento) -> None:
        ids_remotos = {s['id'] for s in remotas}
        atual = registro['sources'].get(documento.chave)
        if atual and atual['sha256'] == documento.sha256 and atual['id'] in ids_remotos:
            self.relatorio.sources_puladas += 1
            return
        antigas = [atual['id']] if atual and atual['id'] in ids_remotos else []
        if documento.titulo.startswith(PREFIXO):
            antigas += [s['id'] for s in remotas if s.get('title') == documento.titulo]
        for source_id in dict.fromkeys(antigas):
            self.cliente.apagar_source(source_id)
        nova = self.cliente.adicionar_source_texto(
            notebook_id, documento.titulo, documento.conteudo, self.embed
        )
        registro['sources'][documento.chave] = {'id': nova['id'], 'sha256': documento.sha256}
        if antigas:
            self.relatorio.sources_trocadas += 1
        else:
            self.relatorio.sources_enviadas += 1

    def _nota(self, notebook_id: str, registro: dict, existentes: list[dict], nota: Documento) -> None:
        atual = registro['notas'].get(nota.chave)
        mesma = next((n for n in existentes if atual and n['id'] == atual['id']), None)
        mesma = mesma or next((n for n in existentes if n.get('title') == nota.titulo), None)
        if mesma is not None:
            if atual and atual['id'] == mesma['id'] and atual['sha256'] == nota.sha256:
                self.relatorio.notas_puladas += 1
                return
            self.cliente.atualizar_nota(mesma['id'], nota.conteudo)
            registro['notas'][nota.chave] = {'id': mesma['id'], 'sha256': nota.sha256}
            self.relatorio.notas_atualizadas += 1
            return
        criada = self.cliente.criar_nota(notebook_id, nota.titulo, nota.conteudo)
        registro['notas'][nota.chave] = {'id': criada['id'], 'sha256': nota.sha256}
        self.relatorio.notas_criadas += 1


def sincronizar_candidato(
    sincronizador: Sincronizador,
    raiz_provas: Path,
    pasta_candidato: Path,
    candidato: str | None,
    *,
    limiar: float,
    arquivo_taxonomia: Path,
    incluir_nome: bool = False,
    concurso: str | None = None,
    fontes: FontesDeEstudo | None = None,
    caderno_de_erros: dict[str, str] | None = None,
    livros: dict[str, set[str]] | None = None,
) -> dict[str, str]:
    """Um notebook por concurso analisado e o do consolidado; devolve concurso → id do notebook.

    Com `fontes`, os livros e as normas de cada concurso são vinculados ao notebook dele. Com
    `caderno_de_erros` (disciplina → texto, de `pratica_tec.textos_do_caderno`), vai também o notebook
    "Caderno de erros", com uma source por disciplina. `livros` (concurso → sources) vincula os livros da
    biblioteca associados a cada concurso."""
    rotulo = sincronizador.estado.rotulo(sincronizador.url, candidato, incluir_nome)
    prefixo = f'{candidato or ""}/'
    notebooks: dict[str, str] = {}
    nomes = concursos_analisados(raiz_provas, pasta_candidato)
    if concurso is not None:
        nomes = [nome for nome in nomes if nome == concurso]
        if not nomes:
            sincronizador.relatorio.avisos.append(f'{concurso}: sem análise para sincronizar')
    for nome in nomes:
        pasta = pasta_candidato / nome
        documentos, ausentes = artefatos_do_concurso(pasta, nome)
        sincronizador.relatorio.avisos += [f'{nome}: {arquivo} não encontrado' for arquivo in ausentes]
        nota = resumo_do_concurso(pasta, nome, limiar)
        if notebook_id := sincronizador.notebook(
            f'{prefixo}{nome}', f'{nome} — {rotulo}', documentos, [nota]
        ):
            notebooks[nome] = notebook_id
    pastas = {nome: pasta_candidato / nome for nome in notebooks}
    desejados = _sources_de_estudo(sincronizador, pastas, fontes or FontesDeEstudo(None, None))
    if desejados is not None and livros:
        for nome in desejados:
            desejados[nome] |= livros.get(nome, set())
    for nome in notebooks if desejados is not None else []:
        sincronizador.vinculos(f'{prefixo}{nome}', desejados.get(nome, set()))
    if concurso is None and nomes:
        documentos, _ = artefatos_do_consolidado(pasta_candidato, incluir_nome)
        notas = [resumo_do_consolidado(raiz_provas, pasta_candidato, arquivo_taxonomia, limiar)]
        recomendacoes = pasta_candidato / PASTA_CONSOLIDADO / ARQUIVO_RECOMENDACOES
        if recomendacoes.exists():
            notas.append(Documento('recomendacoes', TITULO_NOTA, recomendacoes.read_text(encoding='utf-8')))
        sincronizador.notebook(f'{prefixo}{CHAVE_CONSOLIDADO}', f'Consolidado — {rotulo}', documentos, notas)
    if concurso is None and caderno_de_erros:
        documentos = [
            Documento(f'erros/{disciplina}', titulo_da_source(PASTA_CADERNO_DE_ERROS, disciplina), texto)
            for disciplina, texto in sorted(caderno_de_erros.items())
        ]
        sincronizador.notebook(
            f'{prefixo}{CHAVE_CADERNO_DE_ERROS}', f'Caderno de erros — {rotulo}', documentos, []
        )
    return notebooks


def _sources_de_estudo(
    sincronizador: Sincronizador, pastas: dict[str, Path], fontes: FontesDeEstudo
) -> dict[str, set[str]] | None:
    """Concurso → sources de livros e de normas que o notebook dele deve ter; None quando uma das camadas
    falhou, porque desvincular com a lista incompleta tiraria vínculos válidos."""
    desejados: dict[str, set[str]] = {nome: set() for nome in pastas}
    if fontes.mapa is not None and pastas:
        try:
            indice = indexar_biblioteca(sincronizador.cliente, fontes.mapa)
        except OpenNotebookIndisponivelError as erro:
            sincronizador.relatorio.falhas.append(f'biblioteca: {erro.causa}')
            return None
        for nome, pasta in pastas.items():
            for disciplina in disciplinas_do_concurso(pasta, fontes.taxonomia):
                desejados[nome] |= indice.ids_das_sources(fontes.mapa.categorias(disciplina))
    if fontes.repositorio is not None and fontes.repositorio.is_dir() and pastas:
        normas = _sources_de_legislacao(sincronizador, pastas, fontes.repositorio)
        if normas is None:
            return None
        for nome, ids in normas.items():
            desejados[nome] |= ids
    return desejados


def _sources_de_legislacao(
    sincronizador: Sincronizador, pastas: dict[str, Path], repositorio: Path
) -> dict[str, set[str]] | None:
    """As normas citadas nos editais vão uma vez ao notebook compartilhado `Legislação`."""
    citadas = {nome: normas_citadas(citacoes_do_edital(pasta), repositorio) for nome, pasta in pastas.items()}
    normas = {chave: norma for por_concurso in citadas.values() for chave, (norma, _) in por_concurso.items()}
    if not normas:
        return {}
    documentos = [
        Documento(chave, titulo_para_notebook(norma), conteudo_para_notebook(norma))
        for chave, norma in sorted(normas.items())
    ]
    if sincronizador.notebook(CHAVE_LEGISLACAO, NOME_LEGISLACAO, documentos, [], compartilhado=True) is None:
        return None
    registradas = sincronizador.estado.notebook(sincronizador.url, CHAVE_LEGISLACAO)['sources']
    if any(chave not in registradas for chave in normas):
        return None
    return {nome: {registradas[chave]['id'] for chave in por} for nome, por in citadas.items()}
