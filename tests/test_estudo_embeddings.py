import pytest
from servidor_open_notebook import ServidorOpenNotebook

from concursos.estudo import embeddings
from concursos.integracoes.open_notebook import ClienteOpenNotebook, OpenNotebookIndisponivelError


@pytest.fixture
def servidor():
    servidor = ServidorOpenNotebook(senha='s')
    yield servidor
    servidor.desligar()


def test_registra_o_modelo_e_o_marca_como_padrao(servidor):
    cliente = ClienteOpenNotebook(servidor.url, 's')

    modelo_id = embeddings.registrar(cliente)

    modelo = servidor.modelos[modelo_id]
    assert (modelo['provider'], modelo['type'], modelo['credential']) == (
        'openai_compatible',
        'embedding',
        None,
    )
    assert servidor.padroes['default_embedding_model'] == modelo_id


def test_registrar_de_novo_nao_duplica_nem_regrava(servidor):
    cliente = ClienteOpenNotebook(servidor.url, 's')
    primeiro = embeddings.registrar(cliente)
    escritas = len(servidor.escritas)

    assert embeddings.registrar(cliente) == primeiro
    assert len(servidor.modelos) == 1
    assert len(servidor.escritas) == escritas


def test_busca_vetorial_so_depois_do_registro(servidor):
    cliente = ClienteOpenNotebook(servidor.url, 's')
    with pytest.raises(OpenNotebookIndisponivelError) as erro:
        cliente.buscar_vetorial('licitação')
    assert erro.value.status == 400

    embeddings.registrar(cliente)

    assert cliente.buscar_vetorial('licitação') == []
