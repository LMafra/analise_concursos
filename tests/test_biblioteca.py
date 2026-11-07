from pathlib import Path

import pandas as pd
import pytest
from servidor_open_notebook import ServidorOpenNotebook

from concursos.analytics.taxonomia import DisciplinaCanonica
from concursos.biblioteca import (
    BuscaBiblioteca,
    MapaBiblioteca,
    consultas_do_topico,
    disciplinas_do_concurso,
    gravar_recomendacoes,
    indexar_biblioteca,
    ler_catalogo,
    ler_mapa,
    recomendar,
    recomendar_por_catalogo,
)
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.integracoes.open_notebook import ClienteOpenNotebook
from concursos.modelo import Bloco, FonteRecomendacao

CATALOGO = """\
# Catálogo de livros

## Índice

- [Banco de Dados › SQL e Teoria](#ti---banco-de-dados--sql-e-teoria) (3)

## TI - Banco de Dados › SQL e Teoria

| Título | Autor | Arquivo |
|--------|-------|---------|
| Designing Data-Intensive Applications | Martin Kleppmann | `Designing Data-Intensive Applications - Martin Kleppmann.pdf` |
| Projeto de Banco de Dados | Carlos Alberto Heuser | `Projeto de Banco de Dados - Carlos Alberto Heuser.pdf` |
| SQL Cookbook | Anthony Molinaro; Robert de Graaf | `SQL Cookbook - Anthony Molinaro; Robert de Graaf.pdf` |
| SQL \\| Teoria | — | `SQL Teoria.pdf` |

## TI - Banco de Dados › MongoDB

| Título | Autor | Arquivo |
|--------|-------|---------|
| MongoDB in Action | — | `MongoDB in Action.pdf` |

## Sem categoria

Total de livros: 5 | Subcategorias: 2
"""
TOPICO_BD = (
    'Banco de dados relacionais: modelagem conceitual, lógica e física; normalização; '
    'linguagem SQL (DDL, DML, DCL); projeto de banco de dados.'
)
TAXONOMIA = {
    'Banco de Dados': DisciplinaCanonica('Banco de Dados', Bloco.ESPECIFICO),
    'BD': DisciplinaCanonica('Banco de Dados', Bloco.ESPECIFICO),
    'Direito Administrativo': DisciplinaCanonica('Direito Administrativo', Bloco.ESPECIFICO),
    'Língua Portuguesa': DisciplinaCanonica('Língua Portuguesa', Bloco.GERAL),
}


@pytest.fixture
def catalogo(tmp_path: Path) -> Path:
    caminho = tmp_path / 'books' / 'Bookshelf' / 'README.md'
    caminho.parent.mkdir(parents=True)
    caminho.write_text(CATALOGO, encoding='utf-8')
    return caminho


def mapa(catalogo: Path | None = None) -> MapaBiblioteca:
    return MapaBiblioteca({'Banco de Dados': ('TI - Banco de Dados › SQL e Teoria',)}, catalogo)


def fracos(*linhas: tuple[str, str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {'disciplina': d, 'topico': t, 'n': 8, 'percentual': 25.0, 'concursos_abaixo': ['alfa', 'beta']}
            for d, t in linhas
        ]
    )


def test_ler_mapa_resolve_o_catalogo_pela_raiz(tmp_path):
    arquivo = tmp_path / 'projeto' / '.concurso' / 'biblioteca.yaml'
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(
        'catalogo: ../books/Bookshelf/README.md\ndisciplinas:\n  Banco de Dados: "TI - Banco de Dados › SQL e Teoria"\n',
        encoding='utf-8',
    )

    lido = ler_mapa(arquivo, TAXONOMIA, tmp_path / 'projeto')

    assert lido.disciplinas == {'Banco de Dados': ('TI - Banco de Dados › SQL e Teoria',)}
    assert lido.catalogo == (tmp_path / 'books' / 'Bookshelf' / 'README.md').resolve()


def test_sem_arquivo_nao_ha_mapa(tmp_path):
    assert ler_mapa(tmp_path / 'biblioteca.yaml', TAXONOMIA, tmp_path) is None


def test_disciplina_fora_da_taxonomia_e_erro_com_as_opcoes(tmp_path):
    arquivo = tmp_path / 'biblioteca.yaml'
    arquivo.write_text('disciplinas:\n  Banco de dados: ["X › Y"]\n', encoding='utf-8')

    with pytest.raises(ConfiguracaoInvalidaError, match="'Banco de dados' fora da taxonomia.*Banco de Dados"):
        ler_mapa(arquivo, TAXONOMIA, tmp_path)


def test_ler_catalogo_por_secao_com_barra_escapada_e_aviso(catalogo):
    livros, avisos = ler_catalogo(catalogo)

    sql = livros['TI - Banco de Dados › SQL e Teoria']
    assert [livro.titulo for livro in sql][-1] == 'SQL | Teoria'
    assert sql[0].autor == 'Martin Kleppmann' and sql[-1].autor == ''
    assert sql[2].arquivo == 'SQL Cookbook - Anthony Molinaro; Robert de Graaf.pdf'
    assert len(livros['TI - Banco de Dados › MongoDB']) == 1
    assert avisos == [f'{catalogo}: seção sem categoria ignorada: Sem categoria']


def test_consultas_quebram_o_topico_longo():
    consultas = consultas_do_topico(TOPICO_BD)

    assert consultas[0] == 'Banco de dados relacionais'
    assert 'linguagem SQL' in consultas
    assert len(consultas) <= 4
    assert consultas_do_topico('SQL') == ['SQL']


def test_catalogo_ordena_pelo_que_divide_palavras_com_o_topico(catalogo):
    livros, _ = ler_catalogo(catalogo)

    recomendacoes = recomendar_por_catalogo(('TI - Banco de Dados › SQL e Teoria',), TOPICO_BD, livros)

    assert recomendacoes[0].titulo == 'Projeto de Banco de Dados — Carlos Alberto Heuser'
    assert len(recomendacoes) == 3
    assert {r.fonte for r in recomendacoes} == {FonteRecomendacao.CATALOGO}


def test_recomendar_sem_rede_usa_o_catalogo_e_lista_disciplinas_sem_mapa(catalogo):
    resultado = recomendar(
        fracos(('Banco de Dados', TOPICO_BD), ('Língua Portuguesa', 'Crase')), 0.6, mapa(catalogo), None
    )

    assert resultado.fontes == {FonteRecomendacao.CATALOGO}
    assert '[catálogo] Projeto de Banco de Dados' in resultado.texto
    assert '8 questões; descontado o chute, 25,0% (abaixo do esperado em: alfa, beta).' in resultado.texto
    assert '## Disciplinas sem livro escolhido\n\n- Língua Portuguesa' in resultado.texto
    assert '- Sem livro na estante nem norma citada.' in resultado.texto


def test_categoria_desconhecida_e_so_aviso(catalogo):
    resultado = recomendar(
        fracos(), 0.6, MapaBiblioteca({'Banco de Dados': ('Nada › Aqui',)}, catalogo), None
    )

    assert any("'Nada › Aqui'" in aviso for aviso in resultado.avisos)
    assert 'Nenhum tópico ficou abaixo do esperado em mais de um concurso.' in resultado.texto


@pytest.fixture
def servidor():
    servidor = ServidorOpenNotebook()
    yield servidor
    servidor.desligar()


def biblioteca_no_servidor(servidor: ServidorOpenNotebook) -> ClienteOpenNotebook:
    cliente = ClienteOpenNotebook(servidor.url)
    notebook = cliente.criar_notebook('Biblioteca — TI - Banco de Dados › SQL e Teoria', '')['id']
    cliente.adicionar_source_texto(
        notebook, 'SQL Cookbook - Anthony Molinaro', 'linguagem SQL, DDL e DML, SQL SQL'
    )
    cliente.adicionar_source_texto(
        notebook, 'Projeto de Banco de Dados - Heuser', 'modelagem conceitual e normalização'
    )
    outro = cliente.criar_notebook('Meu caderno', '')['id']
    cliente.adicionar_source_texto(outro, 'anotações', 'linguagem SQL')
    return cliente


def test_busca_no_open_notebook_vem_antes_do_catalogo(catalogo, servidor):
    cliente = biblioteca_no_servidor(servidor)
    busca = BuscaBiblioteca(cliente, indexar_biblioteca(cliente, mapa(catalogo)))

    resultado = recomendar(fracos(('Banco de Dados', TOPICO_BD)), 0.6, mapa(catalogo), None, busca)

    assert resultado.fontes == {FonteRecomendacao.OPEN_NOTEBOOK}
    assert (
        '[open-notebook] SQL Cookbook - Anthony Molinaro (Biblioteca — TI - Banco de Dados › SQL e Teoria)'
        in (resultado.texto)
    )
    assert 'anotações' not in resultado.texto
    buscas = [p for p in servidor.pedidos if p.caminho == '/api/search']
    assert buscas and all(b'"type": "text"' in p.corpo for p in buscas)


def test_busca_fora_do_ar_cai_para_o_catalogo_com_aviso(catalogo, servidor):
    cliente = biblioteca_no_servidor(servidor)
    busca = BuscaBiblioteca(cliente, indexar_biblioteca(cliente, mapa(catalogo)))
    servidor.falhas[('POST', r'/api/search$')] = 500

    resultado = recomendar(fracos(('Banco de Dados', TOPICO_BD)), 0.6, mapa(catalogo), None, busca)

    assert resultado.fontes == {FonteRecomendacao.CATALOGO}
    assert any('busca nos livros não respondeu' in aviso for aviso in resultado.avisos)


def test_lei_citada_no_topico_entra_antes_dos_livros(tmp_path, catalogo):
    repositorio = tmp_path / 'leis'
    lei = repositorio / 'federal/leis-ordinarias/1999/lei-9784-1999-01-29.md'
    lei.parent.mkdir(parents=True)
    lei.write_text(
        '---\ntitulo: "Lei nº 9.784, de 29 de janeiro de 1999"\nementa: "Regula o processo administrativo."\n'
        'versao_texto: "compilada (texto vigente)"\nfonte: "https://www.planalto.gov.br/l9784.htm"\n---\n'
        + 'Art. 1º\n'
        * 2000,
        encoding='utf-8',
    )

    resultado = recomendar(
        fracos(('Direito Administrativo', 'Processo administrativo (Lei nº 9.784/1999).')),
        0.6,
        mapa(catalogo),
        repositorio,
    )

    assert resultado.fontes == {FonteRecomendacao.LEGISLACAO}
    assert (
        '[legislação] Lei nº 9.784, de 29 de janeiro de 1999 — Regula o processo administrativo.'
        in resultado.texto
    )
    assert 'fonte: https://www.planalto.gov.br/l9784.htm' in resultado.texto


def test_lei_nao_compilada_sai_com_o_aviso(tmp_path):
    lei = tmp_path / 'leis/federal/leis-ordinarias/2021/lei-14133-2021-04-01.md'
    lei.parent.mkdir(parents=True)
    lei.write_text(
        '---\ntitulo: "Lei nº 14.133, de 1º de abril de 2021"\nversao_texto: "republicação/retificação"\n---\nx\n',
        encoding='utf-8',
    )

    resultado = recomendar(
        fracos(('Direito Administrativo', 'Licitações (Lei nº 14.133/2021).')), 0.6, None, tmp_path / 'leis'
    )

    assert 'aviso: texto não compilado (republicação/retificação)' in resultado.texto
    assert 'aviso: arquivo de 0 KB' in resultado.texto


def test_norma_citada_nos_erros_do_tec_ganha_secao_propria(tmp_path):
    lei = tmp_path / 'leis/federal/leis-ordinarias/1999/lei-9784-1999-01-29.md'
    lei.parent.mkdir(parents=True)
    lei.write_text(
        '---\ntitulo: "Lei nº 9.784, de 29 de janeiro de 1999"\nversao_texto: "compilada (texto vigente)"\n---\n'
        + 'Art. 1º\n' * 2000,
        encoding='utf-8',
    )
    textos = ['Segundo a Lei nº 9.784/1999, o prazo...', 'A Lei 9.784/99 prevê...', 'Sem norma.']

    resultado = recomendar(fracos(), 0.6, None, tmp_path / 'leis', textos_pratica=textos)

    assert '## Normas que aparecem nos seus erros do TEC' in resultado.texto
    assert (
        '- [legislação] Lei nº 9.784, de 29 de janeiro de 1999 (clone do ctresb/leis). citada em 2 erros'
        in (resultado.texto)
    )


def test_gravar_recomendacoes_preserva_o_mtime(tmp_path, catalogo):
    resultado = recomendar(fracos(('Banco de Dados', TOPICO_BD)), 0.6, mapa(catalogo), None)

    assert gravar_recomendacoes(tmp_path, resultado) is True
    assert gravar_recomendacoes(tmp_path, resultado) is False
    assert (tmp_path / 'consolidado' / 'recomendacoes_estudo.md').read_text(
        encoding='utf-8'
    ) == resultado.texto


def test_disciplinas_do_concurso_pela_taxonomia(tmp_path):
    (tmp_path / 'questoes.csv').write_text(
        'questao,disciplina\n1,BD\n2,Língua Portuguesa\n3,Outra\n', encoding='utf-8'
    )

    assert disciplinas_do_concurso(tmp_path, TAXONOMIA) == {'Banco de Dados', 'Língua Portuguesa', 'Outra'}
