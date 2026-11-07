import json
import re
from pathlib import Path

import pytest
from servidor_open_notebook import ServidorOpenNotebook

from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.integracoes.open_notebook import (
    ClienteOpenNotebook,
    ConfiguracaoOpenNotebook,
    OpenNotebookIndisponivelError,
    gravar_configuracao,
    ler_configuracao,
    obter_senha,
)


@pytest.fixture
def servidor():
    servidor = ServidorOpenNotebook()
    yield servidor
    servidor.desligar()


@pytest.fixture
def cliente(servidor: ServidorOpenNotebook) -> ClienteOpenNotebook:
    return ClienteOpenNotebook(servidor.url, timeout=5)


def test_sem_secao_a_integracao_fica_desligada(tmp_path: Path):
    configuracao = ler_configuracao(tmp_path / 'config.toml')
    assert configuracao == ConfiguracaoOpenNotebook()
    assert not configuracao.ativa
    assert configuracao.url == 'http://localhost:5055'


def test_ligada_sem_consentimento_nao_fica_ativa(tmp_path: Path):
    caminho = tmp_path / 'config.toml'
    caminho.write_text('[open_notebook]\nenabled = true\n', encoding='utf-8')
    assert not ler_configuracao(caminho).ativa


def test_campo_desconhecido_ou_invalido_reprova(tmp_path: Path):
    caminho = tmp_path / 'config.toml'
    caminho.write_text('[open_notebook]\napi_key = "segredo"\n', encoding='utf-8')
    with pytest.raises(ConfiguracaoInvalidaError, match='api_key'):
        ler_configuracao(caminho)
    caminho.write_text('[open_notebook]\ntimeout = 0\n', encoding='utf-8')
    with pytest.raises(ConfiguracaoInvalidaError, match='timeout'):
        ler_configuracao(caminho)


def test_gravar_preserva_outras_secoes_e_nao_grava_senha(tmp_path: Path):
    caminho = tmp_path / 'config.toml'
    caminho.write_text('[llm]\nprovedor = "nenhum"\n', encoding='utf-8')
    gravada = gravar_configuracao(caminho, enabled=True, consentimento=True, url='http://outra:5055')
    assert gravada.ativa and gravada.url == 'http://outra:5055'
    texto = caminho.read_text(encoding='utf-8')
    assert '[llm]' in texto and 'OPEN_NOTEBOOK_PASSWORD' in texto
    assert 'senha' not in texto


def test_senha_vem_da_variavel_e_falta_nao_e_erro(tmp_path: Path):
    configuracao = ConfiguracaoOpenNotebook()
    assert obter_senha(configuracao, tmp_path, {'OPEN_NOTEBOOK_PASSWORD': 'abc'}) == 'abc'
    assert obter_senha(configuracao, tmp_path, {}) is None


def test_bearer_so_com_senha(servidor: ServidorOpenNotebook):
    ClienteOpenNotebook(servidor.url, timeout=5).listar_notebooks()
    ClienteOpenNotebook(servidor.url, 'abc', timeout=5).listar_notebooks()
    assert 'Authorization' not in servidor.pedidos[0].cabecalhos
    assert servidor.pedidos[1].cabecalhos['Authorization'] == 'Bearer abc'


def test_401_vira_erro_com_dica_da_senha(servidor: ServidorOpenNotebook, cliente: ClienteOpenNotebook):
    servidor.senha = 'certa'
    with pytest.raises(OpenNotebookIndisponivelError) as erro:
        cliente.listar_notebooks()
    assert erro.value.status == 401
    assert 'OPEN_NOTEBOOK_PASSWORD' in erro.value.dica
    assert 'Missing authorization header' in erro.value.detalhe


def test_500_traz_o_detail(servidor: ServidorOpenNotebook, cliente: ClienteOpenNotebook):
    servidor.falhas[('POST', '/api/notebooks')] = 500
    with pytest.raises(OpenNotebookIndisponivelError, match='recusou') as erro:
        cliente.criar_notebook('x')
    assert re.search('HTTP 500.*falha simulada', erro.value.detalhe)


def test_422_sugere_versao_incompativel(servidor: ServidorOpenNotebook, cliente: ClienteOpenNotebook):
    servidor.falhas[('POST', '/api/sources')] = 422
    with pytest.raises(OpenNotebookIndisponivelError) as erro:
        cliente.adicionar_source_texto('notebook:1', 't', 'c')
    assert '1.15' in erro.value.dica


def test_instancia_fora_do_ar_da_dica_de_subir():
    with pytest.raises(OpenNotebookIndisponivelError) as erro:
        ClienteOpenNotebook('http://127.0.0.1:1', timeout=2).saude()
    assert erro.value.status is None
    assert 'docker compose' in erro.value.dica


def test_notebook_criar_obter_e_buscar_por_nome(servidor: ServidorOpenNotebook, cliente: ClienteOpenNotebook):
    criado = cliente.criar_notebook('agsus — candidato 1', 'gerado por concurso-analise')
    assert cliente.obter_notebook(criado['id'])['name'] == 'agsus — candidato 1'
    assert cliente.obter_notebook('notebook:9999') is None
    assert cliente.buscar_notebook_por_nome('agsus — candidato 1')['id'] == criado['id']
    assert cliente.buscar_notebook_por_nome('outro') is None


def test_nome_repetido_usa_o_mais_antigo(
    servidor: ServidorOpenNotebook, cliente: ClienteOpenNotebook, caplog
):
    novo = servidor.criar_notebook('dup', criado='2026-11-02')
    antigo = servidor.criar_notebook('dup', criado='2026-01-01')
    assert novo['id'] != antigo['id']
    assert cliente.buscar_notebook_por_nome('dup')['id'] == antigo['id']
    assert 'mais antigo' in caplog.text


def test_source_de_texto_vai_em_multipart(servidor: ServidorOpenNotebook, cliente: ClienteOpenNotebook):
    notebook = cliente.criar_notebook('n')
    source = cliente.adicionar_source_texto(notebook['id'], 'título', 'conteúdo com acento')
    campos = servidor.sources[source['id']]['campos']
    assert campos['type'] == 'text'
    assert json.loads(campos['notebooks']) == [notebook['id']]
    assert campos['embed'] == 'false' and campos['async_processing'] == 'false'
    assert servidor.sources[source['id']]['full_text'] == 'conteúdo com acento'


def test_source_de_arquivo_envia_o_arquivo(servidor, cliente, tmp_path: Path):
    notebook = cliente.criar_notebook('n')
    pdf = tmp_path / 'Livro - Autor.pdf'
    pdf.write_bytes(b'%PDF conteudo')
    source = cliente.adicionar_source_arquivo(notebook['id'], pdf, 'Livro - Autor', assincrono=True)
    assert servidor.sources[source['id']]['campos']['type'] == 'upload'
    assert servidor.sources[source['id']]['campos']['async_processing'] == 'true'
    assert servidor.sources[source['id']]['full_text'] == '%PDF conteudo'
    assert cliente.status_source(source['id'])['status'] == 'completed'


def test_listar_sources_pagina_de_100_em_100(servidor: ServidorOpenNotebook, cliente: ClienteOpenNotebook):
    notebook = cliente.criar_notebook('n')
    for indice in range(203):
        source = servidor._novo('source', {'title': f's{indice}', 'full_text': ''})
        servidor.sources[source['id']] = source
        servidor.vinculos.add((source['id'], notebook['id']))
    assert len(cliente.listar_sources(notebook['id'])) == 203
    paginas = [p for p in servidor.pedidos if p.caminho == '/api/sources' and p.metodo == 'GET']
    assert len(paginas) == 3


def test_apagar_renomear_vincular_e_desvincular(servidor: ServidorOpenNotebook, cliente: ClienteOpenNotebook):
    um, outro = cliente.criar_notebook('um'), cliente.criar_notebook('outro')
    source = cliente.adicionar_source_texto(um['id'], 't', 'c')
    cliente.renomear_source(source['id'], 'novo título')
    cliente.vincular_source(outro['id'], source['id'])
    assert [s['title'] for s in cliente.listar_sources(outro['id'])] == ['novo título']
    cliente.desvincular_source(outro['id'], source['id'])
    assert cliente.listar_sources(outro['id']) == []
    cliente.apagar_source(source['id'])
    assert source['id'] not in servidor.sources


def test_notas_criar_listar_atualizar(servidor: ServidorOpenNotebook, cliente: ClienteOpenNotebook):
    notebook = cliente.criar_notebook('n')
    nota = cliente.criar_nota(notebook['id'], 'resumo', 'v1')
    assert servidor.notas[nota['id']]['note_type'] == 'human'
    cliente.atualizar_nota(nota['id'], 'v2')
    assert [n['content'] for n in cliente.listar_notas(notebook['id'])] == ['v2']


def test_busca_de_texto_no_escopo(servidor: ServidorOpenNotebook, cliente: ClienteOpenNotebook):
    biblioteca, outro = cliente.criar_notebook('Biblioteca'), cliente.criar_notebook('outro')
    cliente.adicionar_source_texto(biblioteca['id'], 'SQL Antipatterns', 'normalização e índices')
    cliente.adicionar_source_texto(outro['id'], 'Fora', 'normalização')
    resultados = cliente.buscar_texto('normalização', [biblioteca['id']])
    assert [r['title'] for r in resultados] == ['SQL Antipatterns']
    pedido = json.loads(servidor.pedidos[-1].corpo)
    assert pedido['type'] == 'text' and pedido['search_notes'] is False
