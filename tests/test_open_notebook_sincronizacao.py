import json
from pathlib import Path

import pandas as pd
import pytest
from conftest import criar_concurso
from servidor_open_notebook import ServidorOpenNotebook

from concursos.biblioteca import FontesDeEstudo, MapaBiblioteca
from concursos.cli import main
from concursos.integracoes.open_notebook import ClienteOpenNotebook
from concursos.integracoes.sincronizacao_notebook import (
    TITULO_RESUMO,
    Documento,
    EstadoSincronizacao,
    Sincronizador,
    artefatos_do_concurso,
    artefatos_do_consolidado,
    resumo_do_concurso,
    sincronizar_candidato,
    texto_do_html,
    titulo_da_source,
)

CONFIG = {
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 6]}},
}
GABARITO = '1 A\n2 B\n3 C\n4 D\n5 E\n6 A\n'


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    for nome, respostas in (
        ('alfa', '1 A\n2 B\n3 D\n4 D\n5 A\n6 A\n'),
        ('beta', '1 A\n2 B\n3 C\n4 D\n5 E\n6 B\n'),
    ):
        pasta = criar_concurso(raiz / 'provas', nome, CONFIG, {'gabarito.txt': GABARITO})
        (pasta / 'candidatos' / 'zuleica').mkdir(parents=True)
        (pasta / 'candidatos' / 'zuleica' / 'respostas.txt').write_text(respostas, encoding='utf-8')
    monkeypatch.chdir(raiz)
    assert main(['--yes', '--no-open']) == 0
    return raiz


@pytest.fixture
def servidor():
    servidor = ServidorOpenNotebook()
    yield servidor
    servidor.desligar()


def sincronizador(servidor: ServidorOpenNotebook, projeto: Path) -> Sincronizador:
    estado = EstadoSincronizacao.ler(projeto / '.concurso' / 'open_notebook.json')
    return Sincronizador(ClienteOpenNotebook(servidor.url), estado)


def sincronizar(servidor, projeto, **opcoes) -> Sincronizador:
    sinc = sincronizador(servidor, projeto)
    sincronizar_candidato(
        sinc,
        projeto / 'provas',
        projeto / 'analises' / 'zuleica',
        'zuleica',
        limiar=0.6,
        arquivo_taxonomia=projeto / '.concurso' / 'taxonomia.yaml',
        **opcoes,
    )
    sinc.gravar_estado()
    return sinc


def test_artefatos_do_concurso_tem_titulo_deterministico_e_cabecalho(projeto):
    documentos, ausentes = artefatos_do_concurso(projeto / 'analises' / 'zuleica' / 'alfa', 'alfa')

    titulos = {d.chave: d.titulo for d in documentos}
    assert titulos['relatorio.md'] == 'concurso-analise: alfa/relatorio.md'
    assert 'questoes.csv' in titulos and 'relatorio.html' not in titulos
    relatorio = next(d for d in documentos if d.chave == 'relatorio.md')
    assert relatorio.conteudo.startswith('Arquivo: relatorio.md; concurso: alfa\n\n')
    assert set(ausentes) <= {'catalogo_edital.md', 'edital_estruturado.json'}


def test_index_html_so_vai_com_incluir_nome(projeto):
    sem_nome, _ = artefatos_do_consolidado(projeto / 'analises' / 'zuleica', incluir_nome=False)
    com_nome, _ = artefatos_do_consolidado(projeto / 'analises' / 'zuleica', incluir_nome=True)

    assert 'index.html' not in {d.chave for d in sem_nome}
    assert 'index.html' in {d.chave for d in com_nome}
    assert all('zuleica' not in d.titulo for d in sem_nome)


def test_texto_do_html_tira_tags_e_script():
    texto = texto_do_html(
        '<html><head><style>x{}</style></head><body><h1>Título</h1><script>a()</script>'
        '<table><tr><td>A</td><td>1</td></tr></table></body></html>'
    )

    assert texto == 'Título\nA | 1 |'


def test_sha256_muda_com_o_conteudo():
    assert Documento('a', 't', 'x').sha256 != Documento('a', 't', 'y').sha256
    assert titulo_da_source('alfa', 'questoes.csv') == 'concurso-analise: alfa/questoes.csv'


def test_resumo_do_concurso_traz_acertos_e_disciplinas_sem_llm(projeto):
    nota = resumo_do_concurso(projeto / 'analises' / 'zuleica' / 'alfa', 'alfa', 0.6)

    assert nota.titulo == TITULO_RESUMO
    assert 'Acertos: 4 de 6 questões (66,67%)' in nota.conteudo
    assert 'n ≥ 5' in nota.conteudo


def test_pseudonimo_estavel_por_instancia(tmp_path):
    estado = EstadoSincronizacao.ler(tmp_path / 'estado.json')

    assert estado.rotulo('http://a', 'zuleica', incluir_nome=False) == 'candidato 1'
    assert estado.rotulo('http://a', 'bia', incluir_nome=False) == 'candidato 2'
    assert estado.rotulo('http://a', 'zuleica', incluir_nome=False) == 'candidato 1'
    assert estado.rotulo('http://b', 'bia', incluir_nome=False) == 'candidato 1'
    assert estado.rotulo('http://a', 'zuleica', incluir_nome=True) == 'zuleica'


def test_estado_grava_so_quando_muda(tmp_path):
    estado = EstadoSincronizacao.ler(tmp_path / '.concurso' / 'estado.json')
    estado.rotulo('http://a', 'zuleica', incluir_nome=False)

    assert estado.gravar() is True
    assert EstadoSincronizacao.ler(estado.caminho).gravar() is False


def test_primeira_sincronizacao_cria_notebooks_sources_e_notas_sem_nome(projeto, servidor):
    sinc = sincronizar(servidor, projeto)

    nomes = sorted(n['name'] for n in servidor.notebooks.values())
    assert nomes == ['Consolidado — candidato 1', 'alfa — candidato 1', 'beta — candidato 1']
    alfa = next(i for i, n in servidor.notebooks.items() if n['name'].startswith('alfa'))
    titulos = {s['title'] for s in servidor.sources_do_notebook(alfa)}
    assert 'concurso-analise: alfa/relatorio.md' in titulos
    assert [n['title'] for n in servidor.notas_do_notebook(alfa)] == [TITULO_RESUMO]
    assert sinc.relatorio.sucesso and len(sinc.relatorio.notebooks_criados) == 3
    enviado = json.dumps([*servidor.sources.values(), *servidor.notas.values(), *servidor.notebooks.values()])
    assert 'zuleica' not in enviado
    estado = json.loads((projeto / '.concurso' / 'open_notebook.json').read_text(encoding='utf-8'))
    assert estado['instancias'][servidor.url]['pseudonimos'] == {'zuleica': 'candidato 1'}


def test_segunda_sincronizacao_sem_mudanca_nao_escreve_nada(projeto, servidor):
    sincronizar(servidor, projeto)
    estado = projeto / '.concurso' / 'open_notebook.json'
    mtime = estado.stat().st_mtime_ns
    escritas = len(servidor.escritas)

    sinc = sincronizar(servidor, projeto)

    assert len(servidor.escritas) == escritas
    assert sinc.relatorio.sources_enviadas == sinc.relatorio.sources_trocadas == 0
    assert sinc.relatorio.notas_criadas == sinc.relatorio.notas_atualizadas == 0
    assert estado.stat().st_mtime_ns == mtime


def test_artefato_alterado_apaga_e_recria_so_aquela_source(projeto, servidor):
    sincronizar(servidor, projeto)
    relatorio = projeto / 'analises' / 'zuleica' / 'alfa' / 'relatorio.md'
    relatorio.write_text(relatorio.read_text(encoding='utf-8') + '\nnovo\n', encoding='utf-8')

    sinc = sincronizar(servidor, projeto)

    assert sinc.relatorio.sources_trocadas == 1 and sinc.relatorio.sources_enviadas == 0
    titulos = [s['title'] for s in servidor.sources.values()]
    assert titulos.count('concurso-analise: alfa/relatorio.md') == 1


def test_estado_perdido_reusa_notebook_e_troca_source_pelo_titulo(projeto, servidor):
    sincronizar(servidor, projeto)
    (projeto / '.concurso' / 'open_notebook.json').unlink()

    sinc = sincronizar(servidor, projeto)

    assert len(servidor.notebooks) == 3 and not sinc.relatorio.notebooks_criados
    titulos = [s['title'] for s in servidor.sources.values()]
    assert len(titulos) == len(set(titulos))
    assert sum(n['title'] == TITULO_RESUMO for n in servidor.notas.values()) == 3


def test_source_de_outro_titulo_nunca_e_apagada(projeto, servidor):
    sincronizar(servidor, projeto)
    alfa = next(i for i, n in servidor.notebooks.items() if n['name'].startswith('alfa'))
    ClienteOpenNotebook(servidor.url).adicionar_source_texto(alfa, 'minhas anotações', 'texto meu')
    (projeto / '.concurso' / 'open_notebook.json').unlink()

    sincronizar(servidor, projeto)

    assert any(s['title'] == 'minhas anotações' for s in servidor.sources.values())


def test_falha_numa_source_vira_falha_e_as_outras_seguem(projeto, servidor):
    servidor.falhas[('POST', r'/api/sources$')] = 500

    sinc = sincronizar(servidor, projeto)

    assert not sinc.relatorio.sucesso
    assert any('relatorio.md' in falha for falha in sinc.relatorio.falhas)
    assert sinc.relatorio.notas_criadas == 3


def test_filtro_por_concurso_sincroniza_so_ele(projeto, servidor):
    sincronizar(servidor, projeto, concurso='beta')

    assert [n['name'] for n in servidor.notebooks.values()] == ['beta — candidato 1']


def test_incluir_nome_usa_o_slug(projeto, servidor):
    sincronizar(servidor, projeto, incluir_nome=True)

    assert 'alfa — zuleica' in {n['name'] for n in servidor.notebooks.values()}


def test_resumo_consolidado_traz_as_respostas_da_evolucao(projeto, servidor):
    sincronizar(servidor, projeto)

    consolidado = next(i for i, n in servidor.notebooks.items() if n['name'].startswith('Consolidado'))
    nota = servidor.notas_do_notebook(consolidado)[0]
    assert nota['content'].startswith('# Resumo executivo: todos os concursos')
    assert '## 1.' in nota['content']


def test_vinculos_so_desfaz_o_que_o_app_criou(projeto, servidor):
    sinc = sincronizar(servidor, projeto)
    cliente = ClienteOpenNotebook(servidor.url)
    biblioteca = cliente.criar_notebook('Biblioteca', '')['id']
    livro = cliente.adicionar_source_texto(biblioteca, 'livro', 'x')['id']
    manual = cliente.adicionar_source_texto(biblioteca, 'manual', 'y')['id']
    chave = 'zuleica/alfa'
    alfa = sinc.estado.notebook(servidor.url, chave)['id']
    cliente.vincular_source(alfa, manual)

    sinc = sincronizar(servidor, projeto)
    sinc.vinculos(chave, {livro, manual})
    sinc.gravar_estado()
    sinc = sincronizar(servidor, projeto)
    sinc.vinculos(chave, set())

    assert (manual, alfa) in servidor.vinculos and (livro, alfa) not in servidor.vinculos
    assert sinc.relatorio.vinculos_removidos == 1


def disciplina_de(projeto: Path, concurso: str) -> str:
    questoes = pd.read_csv(projeto / 'analises' / 'zuleica' / concurso / 'questoes.csv')
    return str(questoes['disciplina'].iloc[0])


def test_livros_das_disciplinas_presentes_sao_vinculados_e_saem_com_o_mapa(projeto, servidor):
    cliente = ClienteOpenNotebook(servidor.url)
    estante = cliente.criar_notebook('Biblioteca — TI › Banco de Dados', '')['id']
    livro = cliente.adicionar_source_texto(estante, 'SQL Cookbook', 'x')['id']
    outra = cliente.criar_notebook('Biblioteca — TI › Redes', '')['id']
    redes = cliente.adicionar_source_texto(outra, 'Redes', 'y')['id']
    mapa = MapaBiblioteca(
        {disciplina_de(projeto, 'alfa'): ('TI › Banco de Dados',), 'Outra': ('TI › Redes',)}
    )

    sinc = sincronizar(servidor, projeto, fontes=FontesDeEstudo(mapa, None))

    alfa = sinc.estado.notebook(servidor.url, 'zuleica/alfa')['id']
    assert (livro, alfa) in servidor.vinculos
    assert [notebook for source, notebook in servidor.vinculos if source == redes] == [outra]
    escritas = len(servidor.escritas)
    sincronizar(servidor, projeto, fontes=FontesDeEstudo(mapa, None))
    assert len(servidor.escritas) == escritas

    sinc = sincronizar(servidor, projeto, fontes=FontesDeEstudo(None, None))

    assert (livro, alfa) not in servidor.vinculos and livro in servidor.sources
    assert sinc.relatorio.vinculos_removidos == 2


def citar(projeto: Path, concurso: str, topico: str) -> None:
    edital = {'conhecimentos': [{'disciplinas': [{'nome': 'Direito', 'topicos': [{'nome': topico}]}]}]}
    caminho = projeto / 'analises' / 'zuleica' / concurso / 'edital_estruturado.json'
    caminho.write_text(json.dumps(edital, ensure_ascii=False), encoding='utf-8')


def clone_de_leis(tmp_path: Path) -> Path:
    repositorio = tmp_path / 'leis'
    for relativo, titulo in (
        ('federal/leis-ordinarias/2018/lei-13709-2018-08-14.md', 'Lei nº 13.709, de 14 de agosto de 2018'),
        ('federal/leis-ordinarias/1999/lei-9784-1999-01-29.md', 'Lei nº 9.784, de 29 de janeiro de 1999'),
    ):
        arquivo = repositorio / relativo
        arquivo.parent.mkdir(parents=True)
        arquivo.write_text(
            f'---\ntitulo: "{titulo}"\nurn: "urn:{arquivo.stem}"\nversao_texto: "compilada (texto vigente)"\n'
            '---\n' + 'Art. 1º texto.\n' * 800,
            encoding='utf-8',
        )
    return repositorio


def test_norma_citada_por_dois_concursos_sobe_uma_vez_e_vincula_aos_dois(projeto, servidor, tmp_path):
    citar(projeto, 'alfa', 'Proteção de dados (Lei nº 13.709/2018). Processo (Lei nº 9.784/1999).')
    citar(projeto, 'beta', 'LGPD: Lei nº 13.709, de 14 de agosto de 2018.')
    fontes = FontesDeEstudo(None, clone_de_leis(tmp_path))

    sinc = sincronizar(servidor, projeto, fontes=fontes)

    legislacao = next(i for i, n in servidor.notebooks.items() if n['name'] == 'Legislação')
    titulos = sorted(s['title'] for s in servidor.sources_do_notebook(legislacao))
    assert titulos == ['Lei nº 13.709, de 14 de agosto de 2018', 'Lei nº 9.784, de 29 de janeiro de 1999']
    lgpd = sinc.estado.notebook(servidor.url, '_legislacao')['sources']['urn:lei-13709-2018-08-14']['id']
    for concurso in ('alfa', 'beta'):
        assert (lgpd, sinc.estado.notebook(servidor.url, f'zuleica/{concurso}')['id']) in servidor.vinculos
    escritas = len(servidor.escritas)
    sincronizar(servidor, projeto, fontes=fontes)
    assert len(servidor.escritas) == escritas


def test_recomendacoes_vao_como_nota_do_consolidado(projeto, servidor):
    destino = projeto / 'analises' / 'zuleica' / 'consolidado' / 'recomendacoes_estudo.md'
    destino.write_text('# Recomendações de estudo\n\nNenhum tópico fraco persistente.\n', encoding='utf-8')

    sincronizar(servidor, projeto)

    consolidado = next(i for i, n in servidor.notebooks.items() if n['name'].startswith('Consolidado'))
    notas = {n['title']: n['content'] for n in servidor.notas_do_notebook(consolidado)}
    assert notas['concurso-analise: recomendações de estudo'].startswith('# Recomendações de estudo')


def test_caderno_de_erros_vira_notebook_com_uma_source_por_disciplina(projeto, servidor):
    caderno = {
        'Legislação Tributária': '# Caderno de erros — Legislação Tributária\n',
        'Sem disciplina': '# x\n',
    }

    sincronizar(servidor, projeto, caderno_de_erros=caderno)

    notebook = next(i for i, n in servidor.notebooks.items() if n['name'].startswith('Caderno de erros'))
    assert servidor.notebooks[notebook]['name'] == 'Caderno de erros — candidato 1'
    titulos = sorted(s['title'] for s in servidor.sources_do_notebook(notebook))
    assert titulos == [
        'concurso-analise: caderno de erros/Legislação Tributária',
        'concurso-analise: caderno de erros/Sem disciplina',
    ]
    escritas = len(servidor.escritas)
    sincronizar(servidor, projeto, caderno_de_erros=caderno)
    assert len(servidor.escritas) == escritas


def test_sem_caderno_de_erros_nao_ha_notebook(projeto, servidor):
    sincronizar(servidor, projeto)

    assert not any(n['name'].startswith('Caderno de erros') for n in servidor.notebooks.values())
