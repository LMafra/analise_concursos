import pytest
from servidor_open_notebook import ServidorOpenNotebook

from concursos.integracoes.open_notebook import ClienteOpenNotebook
from concursos.livros import envio, fila
from concursos.modelo import EstadoLivro


@pytest.fixture
def servidor():
    servidor = ServidorOpenNotebook(senha='s')
    yield servidor
    servidor.desligar()


@pytest.fixture
def cliente(servidor):
    return ClienteOpenNotebook(servidor.url, 's')


def livro_lido(tmp_path, pastas, nome='Manual', conteudo='pregão\fcontrato', **campos):
    caminho = tmp_path / f'{nome}.txt'
    caminho.write_text(conteudo, encoding='utf-8')
    livro = fila.adicionar(pastas, caminho, **campos).livro
    fila.ler_livro(pastas.banco, livro.arquivo(pastas), livro.sha)
    conexao = fila.conectar(pastas)
    try:
        return fila.obter(conexao, livro.sha)
    finally:
        conexao.close()


def test_texto_com_marcas_de_pagina():
    assert envio.texto_com_paginas([(1, 'um'), (2, ''), (3, 'três')]) == '[p. 1]\num\n\n[p. 3]\ntrês'


def test_envia_ao_notebook_da_disciplina_e_fica_pronto(tmp_path, servidor, cliente):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro_lido(tmp_path, pastas, disciplina='Direito Administrativo')

    relatorio = envio.processar_envios(cliente, pastas)

    assert relatorio.enviados == ['Manual'] and relatorio.prontos == ['Manual']
    (notebook,) = servidor.notebooks.values()
    assert notebook['name'] == 'Biblioteca — Direito Administrativo'
    (source,) = servidor.sources.values()
    assert source['full_text'] == '[p. 1]\npregão\n\n[p. 2]\ncontrato'
    assert source['campos']['embed'] == 'true' and source['campos']['async_processing'] == 'true'
    conexao = fila.conectar(pastas)
    assert fila.listar(conexao)[0].estado is EstadoLivro.PRONTO


def test_mesmo_livro_nao_e_enviado_duas_vezes(tmp_path, servidor, cliente):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro_lido(tmp_path, pastas)
    envio.processar_envios(cliente, pastas)
    livro_lido(tmp_path, pastas, nome='copia')

    envio.processar_envios(cliente, pastas)

    assert len(servidor.sources) == 1


def test_disciplina_compartilhada_reusa_o_notebook_pelo_nome(tmp_path, servidor, cliente):
    servidor.criar_notebook('Biblioteca — Geral')
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro_lido(tmp_path, pastas)

    envio.processar_envios(cliente, pastas)

    assert len(servidor.notebooks) == 1


def test_mudar_disciplina_move_o_vinculo(tmp_path, servidor, cliente):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro = livro_lido(tmp_path, pastas)
    envio.processar_envios(cliente, pastas)

    movido = envio.mudar_disciplina(cliente, pastas, livro.sha, 'Português')

    novo = next(n for n in servidor.notebooks.values() if n['name'] == 'Biblioteca — Português')
    assert servidor.vinculos == {(movido.source_id, novo['id'])}
    assert len(servidor.sources) == 1


def test_instancia_fora_deixa_o_livro_esperando(tmp_path, servidor, cliente):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro_lido(tmp_path, pastas)
    servidor.falhas[('POST', '/api/notebooks')] = 503

    relatorio = envio.processar_envios(cliente, pastas)

    assert relatorio.falhas == ['Manual']
    conexao = fila.conectar(pastas)
    assert fila.listar(conexao)[0].estado is EstadoLivro.LIDO


def test_source_com_falha_vira_erro_leigo(tmp_path, servidor, cliente):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro = livro_lido(tmp_path, pastas)
    enviado = envio.enviar_livro(cliente, pastas, livro)
    servidor.status_sources[enviado.source_id] = 'failed'

    conferido = envio.conferir_envio(cliente, pastas, enviado)

    assert conferido.estado is EstadoLivro.ERRO and conferido.erro == envio.MENSAGEM_FALHA


def test_remover_apaga_no_open_notebook_e_na_biblioteca(tmp_path, servidor, cliente):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro = livro_lido(tmp_path, pastas)
    envio.processar_envios(cliente, pastas)

    envio.remover_livro(cliente, pastas, livro.sha)

    assert servidor.sources == {}
    assert not livro.arquivo(pastas).exists()


def test_sources_por_concurso(tmp_path, cliente):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro_lido(tmp_path, pastas, concursos=['tcu_2025', 'tce_2024'])
    envio.processar_envios(cliente, pastas)

    mapa = envio.sources_por_concurso(pastas)

    assert set(mapa) == {'tcu_2025', 'tce_2024'}
    assert len(mapa['tcu_2025']) == 1
