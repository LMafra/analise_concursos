from pathlib import Path

import pytest

from concursos.aplicacao import dicionario
from concursos.config.contexto import resolver_contexto
from concursos.erros import ErroDoUsuario


@pytest.fixture
def contexto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raiz = tmp_path / 'projeto'
    (raiz / '.concurso').mkdir(parents=True)
    monkeypatch.chdir(raiz)
    return resolver_contexto()


def test_inicial_e_valido_e_cobre_as_quatro_disciplinas():
    disciplinas = {e.disciplina for e in dicionario.inicial().entradas}
    assert disciplinas == {
        'direito_administrativo',
        'direito_constitucional',
        'lingua_portuguesa',
        'raciocinio_logico',
    }


def test_sem_arquivo_ou_desligado_a_analise_nao_usa(contexto):
    assert dicionario.dicionario_do_projeto(contexto) is None
    dicionario.iniciar(contexto)
    assert dicionario.dicionario_do_projeto(contexto) is not None
    dicionario.ligar(contexto, False)
    assert dicionario.dicionario_do_projeto(contexto) is None
    assert dicionario.situacao(contexto).existe


def test_gravar_topico_cria_troca_e_tira(contexto):
    assert dicionario.gravar_topico(contexto, 'Língua Portuguesa', 'Emprego da crase', ['acento grave'], [])
    [entrada] = dicionario.temas(contexto)
    assert (entrada.disciplina, entrada.topico, entrada.nomes) == (
        'lingua_portuguesa',
        'emprego_da_crase',
        ('Emprego da crase',),
    )
    assert dicionario.rotulo_do_tema(entrada) == 'Emprego da crase'

    dicionario.gravar_topico(contexto, entrada.disciplina, entrada.topico, ['fusão'], ['às vezes'])
    [entrada] = dicionario.temas(contexto)
    assert (entrada.termos, entrada.expressoes, entrada.nomes) == (
        ('fusão',),
        ('às vezes',),
        ('Emprego da crase',),
    )

    assert not dicionario.gravar_topico(contexto, entrada.disciplina, entrada.topico, ['fusão'], ['às vezes'])
    dicionario.gravar_topico(contexto, entrada.disciplina, entrada.topico, [], [])
    assert dicionario.temas(contexto) == []


def test_termo_longo_demais_nao_grava(contexto):
    with pytest.raises(ErroDoUsuario):
        dicionario.gravar_topico(contexto, 'portugues', 'crase', ['um dois tres quatro cinco seis sete'], [])
    assert not contexto.dicionario.exists()


def test_termos_do_texto():
    assert dicionario.termos_do_texto(' acento grave; fusão,, crase ') == ['acento grave', 'fusão', 'crase']
