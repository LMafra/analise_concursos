import importlib.util
from pathlib import Path

import pytest

from concursos.estudo import manifesto

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def montar():
    especificacao = importlib.util.spec_from_file_location(
        'montar_estudo', RAIZ / 'empacotamento' / 'estudo' / 'montar.py'
    )
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


def test_versao_toml_tem_o_que_o_pacote_precisa(montar):
    config = montar.ler_versao()

    assert manifesto.PADRAO_VERSAO.match(montar.versao_do_pacote(config))
    for secao in ('python', 'surreal'):
        for sistema in montar.SISTEMAS:
            assert len(config[secao][sistema]['sha256']) == 64
    assert all(len(item['sha256']) == 64 for item in config['modelo']['arquivos'])
    assert config['modelo']['licenca'] == 'Apache-2.0'


def test_nome_do_cache_do_tiktoken_e_o_sha1_da_url(montar):
    url = 'https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken'

    assert montar.nome_cache_tiktoken(url) == 'fb374d419588a4632f3f557e76b4b70aebbca790'


def test_export_exclui_node_e_ffmpeg_salvo_completo(montar, tmp_path):
    config = montar.ler_versao()

    enxuto = montar.comando_export(config, False, tmp_path / 'r.txt')
    completo = montar.comando_export(config, True, tmp_path / 'r.txt')

    assert enxuto[-4:-2] == ['--no-emit-package', 'nodejs-wheel-binaries']
    assert '--no-emit-package' not in completo
    assert '--frozen' in enxuto and '--no-dev' in enxuto


def test_nome_do_arquivo_bate_com_o_manifesto(montar):
    for sistema in montar.SISTEMAS:
        assert manifesto.PADRAO_ARQUIVO.match(montar.nome_do_arquivo('1.15.1-1', sistema))


def test_manifesto_a_partir_da_pasta(montar, tmp_path):
    config = montar.ler_versao()
    versao = montar.versao_do_pacote(config)
    for sistema in montar.SISTEMAS:
        nome = montar.nome_do_arquivo(versao, sistema)
        (tmp_path / nome).write_bytes(sistema.encode())
        (tmp_path / f'{nome}.extraido').write_text('123')

    destino = montar.gerar_manifesto(tmp_path, config, '2026-11-06')

    lido = manifesto.ler_manifesto(destino.read_bytes())
    assert set(lido.artefatos) == set(montar.SISTEMAS)
    assert lido.artefatos['windows-x64'].tamanho_extraido == 123


def test_tag_nova_do_upstream_ignora_pre_release_e_a_atual(montar):
    config = {'open_notebook': {'tag': 'v1.15.1'}}

    assert montar.tag_upstream_nova(config, ['v1.15.1', 'v1.14.0']) is None
    assert montar.tag_upstream_nova(config, ['v1.16.0rc1', 'v1.15.1']) is None
    assert montar.tag_upstream_nova(config, ['v1.16.0', 'v1.15.2', 'lixo']) == 'v1.16.0'


def test_trocar_upstream_volta_a_revisao_para_1(montar):
    texto = 'revisao = 3\napp_minimo = "0.7.0"\n\n[open_notebook]\ntag = "v1.15.1"\ncommit = "abc"\n\n[python]\nversao = "3.12"\n'

    novo = montar.trocar_upstream(texto, 'v1.16.0', 'def')

    assert 'revisao = 1\n' in novo
    assert 'tag = "v1.16.0"' in novo and 'commit = "def"' in novo
    assert 'versao = "3.12"' in novo
