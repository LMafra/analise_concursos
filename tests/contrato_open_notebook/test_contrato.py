import socket
import time

import pytest

from concursos.estudo import embeddings
from concursos.integracoes.open_notebook import ClienteOpenNotebook, OpenNotebookIndisponivelError

TEXTO = (
    '[p. 1]\nIntrodução ao direito administrativo.\n'
    '[p. 2]\nA licitação é dispensável quando o valor da contratação for pequeno, nos termos da Lei 14.133.\n'
)


def esperar_pronto(cliente, source_id, limite=180):
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        status = cliente.status_source(source_id).get('status')
        if status == 'completed':
            return
        if status == 'failed':
            pytest.fail(f'source {source_id} falhou')
        time.sleep(1)
    pytest.fail(f'source {source_id} não ficou pronto em {limite} s')


@pytest.fixture(scope='module')
def livro(aberto):
    _, _, cliente, _ = aberto
    notebook = cliente.criar_notebook('Biblioteca — Direito Administrativo')
    source = cliente.adicionar_source_texto(notebook['id'], 'Manual.pdf', TEXTO, embed=True)
    esperar_pronto(cliente, source['id'])
    return notebook, source


def test_sem_senha_a_api_recusa(aberto):
    _, sessao, _, _ = aberto
    with pytest.raises(OpenNotebookIndisponivelError) as erro:
        ClienteOpenNotebook(sessao.url, None).listar_notebooks()
    assert erro.value.status == 401


def test_nada_escuta_fora_de_127_0_0_1(aberto):
    _, sessao, _, _ = aberto
    ip_da_rede = socket.gethostbyname(socket.gethostname())
    if ip_da_rede.startswith('127.'):
        pytest.skip('a máquina não tem outro endereço')
    for porta in (sessao.porta_api, sessao.porta_surreal, sessao.porta_embeddings):
        with socket.socket() as s:
            s.settimeout(1)
            assert s.connect_ex((ip_da_rede, porta)) != 0


def test_registro_dos_embeddings_e_idempotente(aberto):
    _, _, cliente, _ = aberto
    primeiro = embeddings.registrar(cliente)

    assert embeddings.registrar(cliente) == primeiro
    assert cliente.modelos_padrao()['default_embedding_model'] == primeiro


def test_texto_completo_volta_com_as_marcas_de_pagina(aberto, livro):
    _, _, cliente, _ = aberto
    _, source = livro

    assert '[p. 2]' in cliente.obter_source(source['id'])['full_text']


def test_busca_de_texto_e_vetorial(aberto, livro):
    _, _, cliente, _ = aberto
    notebook, source = livro

    texto = cliente.buscar_texto('licitação', [notebook['id']])
    vetorial = cliente.buscar_vetorial('quando posso contratar sem licitar?', [notebook['id']])

    assert source['id'] in {r.get('parent_id') or r.get('id') for r in texto}
    assert source['id'] in {r.get('parent_id') or r.get('id') for r in vetorial}


def test_ask_com_o_mesmo_modelo_nas_tres_funcoes(aberto, livro, llm_falso):
    _, _, cliente, _ = aberto
    modelo = cliente.criar_modelo('falso', 'openai_compatible', 'language')

    resposta = cliente.perguntar('quando a licitação é dispensável?', modelo['id'])

    assert 'dispensável' in resposta['answer']
    assert '[source:' in resposta['answer']
    assert len(llm_falso.chamadas) >= 3


def test_reprocessar_e_remover(aberto, livro):
    _, _, cliente, _ = aberto
    notebook, _ = livro
    source = cliente.adicionar_source_texto(notebook['id'], 'Outro.txt', '[p. 1]\nCrase.', embed=True)
    esperar_pronto(cliente, source['id'])

    assert cliente.reprocessar_source(source['id'])['success']
    cliente.apagar_source(source['id'])

    assert source['id'] not in {s['id'] for s in cliente.listar_sources(notebook['id'])}


def test_reiniciar_mantem_os_livros(aberto, livro):
    supervisor, _, _, _ = aberto
    notebook, source = livro
    supervisor.parar()

    sessao = supervisor.garantir()
    cliente = ClienteOpenNotebook(sessao.url, sessao.senha, timeout=300)

    assert source['id'] in {s['id'] for s in cliente.listar_sources(notebook['id'])}


def test_envio_de_livro_assincrono_fica_pronto(aberto, tmp_path):
    from concursos.livros import envio, fila
    from concursos.modelo import EstadoLivro

    supervisor, _, _, _ = aberto
    sessao = supervisor.garantir()
    cliente = ClienteOpenNotebook(sessao.url, sessao.senha, timeout=300)
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    arquivo = tmp_path / 'Apostila.txt'
    arquivo.write_text('Crase antes de palavra feminina.\fRegência verbal.', encoding='utf-8')
    livro = fila.adicionar(pastas, arquivo, disciplina='Português').livro
    fila.ler_livro(pastas.banco, livro.arquivo(pastas), livro.sha)

    fim = time.monotonic() + 180
    while time.monotonic() < fim:
        envio.processar_envios(cliente, pastas)
        conexao = fila.conectar(pastas)
        estado = fila.obter(conexao, livro.sha).estado
        conexao.close()
        if estado is EstadoLivro.PRONTO:
            break
        time.sleep(1)

    assert estado is EstadoLivro.PRONTO
    resultados = cliente.buscar_vetorial('uso da crase', limite=5)
    assert any(
        (r.get('parent_id') or r.get('id')) == fila.obter(fila.conectar(pastas), livro.sha).source_id
        for r in resultados
    )
