import importlib.util
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def modulo():
    especificacao = importlib.util.spec_from_file_location(
        'servidor_embeddings', RAIZ / 'empacotamento' / 'estudo' / 'servidor_embeddings.py'
    )
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def servidor(modulo):
    def codificar(textos):
        return [[float(len(t)), 0.0] for t in textos]

    servidor = modulo.criar_servidor(0, 'segredo', codificar)
    linha = threading.Thread(target=servidor.serve_forever, daemon=True)
    linha.start()
    yield f'http://127.0.0.1:{servidor.server_address[1]}'
    servidor.shutdown()
    servidor.server_close()


def chamar(url, corpo=None, token='segredo'):
    dados = None if corpo is None else json.dumps(corpo).encode()
    pedido = urllib.request.Request(url, data=dados, method='POST' if dados else 'GET')
    if token:
        pedido.add_header('Authorization', f'Bearer {token}')
    pedido.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(pedido, timeout=5) as resposta:
        return resposta.status, json.loads(resposta.read())


def test_media_normalizada_ignora_padding(modulo):
    saida = np.array([[[3.0, 4.0], [100.0, 100.0]]])
    mascara = np.array([[1, 0]])

    vetor = modulo.media_normalizada(saida, mascara)

    assert np.allclose(vetor, [[0.6, 0.8]])


def test_responde_no_formato_da_openai(servidor):
    status, corpo = chamar(f'{servidor}/v1/embeddings', {'input': ['abc', 'de'], 'model': 'x'})

    assert status == 200
    assert [d['index'] for d in corpo['data']] == [0, 1]
    assert corpo['data'][0]['embedding'] == [3.0, 0.0]


def test_aceita_texto_sozinho(servidor):
    _, corpo = chamar(f'{servidor}/v1/embeddings', {'input': 'abcd'})

    assert corpo['data'][0]['embedding'] == [4.0, 0.0]


def test_recusa_sem_token_ou_com_token_errado(servidor):
    for token in (None, 'outro'):
        with pytest.raises(urllib.error.HTTPError) as erro:
            chamar(f'{servidor}/v1/embeddings', {'input': 'a'}, token=token)
        assert erro.value.code == 401


def test_health_sem_token(servidor):
    assert chamar(f'{servidor}/health', token=None) == (200, {'status': 'ok'})


def test_recusa_entrada_invalida(servidor):
    with pytest.raises(urllib.error.HTTPError) as erro:
        chamar(f'{servidor}/v1/embeddings', {'input': [1, 2]})
    assert erro.value.code == 400


def test_escuta_so_em_127_0_0_1(modulo):
    servidor = modulo.criar_servidor(0, 'segredo', lambda textos: [])
    try:
        assert servidor.server_address[0] == '127.0.0.1'
    finally:
        servidor.server_close()


def test_nao_sobe_sem_token(modulo):
    with pytest.raises(SystemExit):
        modulo.criar_servidor(0, '', lambda textos: [])
