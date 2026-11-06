import json
import tomllib

import pandas as pd
import pytest

from concursos import manifesto
from concursos.aplicacao import estudo, pratica
from concursos.biblioteca import BuscaLocal, MapaBiblioteca, recomendar
from concursos.config.contexto import Contexto
from concursos.livros import fila
from concursos.migracao import SECAO_MIGRACAO_BIBLIOTECA, migrar_biblioteca_yaml
from concursos.modelo import FonteRecomendacao

MAPA = 'disciplinas:\n  Direito Administrativo:\n    - Direito › Administrativo\n'


@pytest.fixture
def contexto(tmp_path) -> Contexto:
    return Contexto(
        raiz=tmp_path,
        home=tmp_path / 'home',
        projeto=tmp_path / '.concurso',
        provas=tmp_path / 'provas',
        analises=tmp_path / 'analises',
    )


def livro(contexto, tmp_path, nome, conteudo, disciplina):
    pastas = estudo.biblioteca(contexto)
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding='utf-8')
    adicionado = fila.adicionar(pastas, caminho, disciplina=disciplina).livro
    fila.ler_livro(pastas.banco, adicionado.arquivo(pastas), adicionado.sha)
    return adicionado


def test_categoria_do_mapa_vira_a_disciplina_com_backup(contexto, tmp_path):
    contexto.projeto.mkdir()
    (contexto.projeto / 'biblioteca.yaml').write_text(MAPA, encoding='utf-8')
    adm = livro(contexto, tmp_path, 'adm.txt', 'Licitação dispensável.', 'Direito › Administrativo')
    port = livro(contexto, tmp_path, 'port.txt', 'Crase.', 'Língua Portuguesa')

    backup = migrar_biblioteca_yaml(contexto)

    disciplinas = {item.sha: item.disciplina for item in estudo.listar_livros(contexto)}
    assert disciplinas == {adm.sha: 'Direito Administrativo', port.sha: 'Língua Portuguesa'}
    hashes = json.loads((backup / 'hashes.json').read_text(encoding='utf-8'))
    assert set(hashes) == {'biblioteca.yaml', 'biblioteca.sqlite'}
    assert hashes['biblioteca.yaml'] == manifesto.hash_arquivo(contexto.projeto / 'biblioteca.yaml')
    assert (contexto.projeto / 'biblioteca.yaml').exists()
    registro = tomllib.loads(contexto.config_projeto.read_text(encoding='utf-8'))
    assert registro[SECAO_MIGRACAO_BIBLIOTECA]['livros'] == 1

    assert migrar_biblioteca_yaml(contexto) is None


def test_sem_biblioteca_yaml_nao_faz_nada(contexto):
    assert migrar_biblioteca_yaml(contexto) is None
    assert not contexto.config_projeto.exists()


def test_livros_do_app_recomendam_pelo_indice_local(contexto, tmp_path):
    livro(
        contexto,
        tmp_path,
        'Manual de Adm.txt',
        'Intro.\fA licitação dispensável e a inexigível.',
        'Direito Administrativo',
    )
    livro(contexto, tmp_path, 'Gramática.txt', 'Crase antes de palavra feminina.', 'Língua Portuguesa')

    fontes = pratica.fontes_de_estudo(contexto)
    busca = pratica.busca_na_biblioteca(pratica.Opcoes(contexto, rede=False), fontes)

    assert fontes.mapa == MapaBiblioteca({}, None, por_disciplina=True)
    assert isinstance(busca, BuscaLocal)
    fracos = pd.DataFrame(
        [
            {
                'disciplina': 'Direito Administrativo',
                'topico': 'Licitação dispensável e inexigível',
                'n': 6,
                'percentual': 20.0,
                'concursos_abaixo': ['tcu'],
            }
        ]
    )
    resultado = recomendar(fracos, 0.5, fontes.mapa, None, busca)
    assert FonteRecomendacao.LIVROS in resultado.fontes
    assert '- [meus livros] Manual de Adm (Meus livros). p. 2' in resultado.texto
    assert 'Gramática' not in resultado.texto


def test_sem_livros_do_app_as_fontes_nao_mudam(contexto):
    assert pratica.fontes_de_estudo(contexto).vazias
