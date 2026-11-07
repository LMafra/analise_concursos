import logging
from datetime import datetime, timedelta
from pathlib import Path

from conftest import log_completo

from concursos.integracoes.cache_pci import CachePci, argumentos_normalizados, chave

AGORA = datetime(2026, 11, 5, 10, 0)


def test_chave_ignora_acento_caixa_espacos_e_vazios():
    assert chave('buscar_por_cargo', {'cargo': ' Técnico ', 'uf': ''}) == chave(
        'buscar_por_cargo', {'cargo': 'tecnico'}
    )
    assert chave('buscar_por_cargo', {'cargo': 'analista'}) != chave(
        'pesquisar_concursos', {'termo': 'analista'}
    )
    assert chave('listar_concursos', {'professores': False}) == chave('listar_concursos', {})


def test_argumentos_normalizados_tira_vazios_e_ordena():
    assert argumentos_normalizados({'uf': '', 'cargo': ' analista ', 'professores': False}) == {
        'cargo': 'analista'
    }


def test_entrada_vence_depois_do_ttl(tmp_path: Path):
    agora = [AGORA]
    cache = CachePci(tmp_path / 'pci.json', ttl_horas=24, agora=lambda: agora[0])
    cache.guardar(
        'pesquisar_provas', {'termo': 'auditor'}, {'meta': {'data_atual': '2026-11-05'}, 'data': []}
    )
    assert not cache.obter('pesquisar_provas', {'termo': 'Auditor'}).vencida
    agora[0] += timedelta(hours=24, seconds=1)
    assert cache.obter('pesquisar_provas', {'termo': 'auditor'}).vencida


def test_sem_gravar_nao_cria_arquivo(tmp_path: Path):
    cache = CachePci(tmp_path / 'pci.json', ttl_horas=24, gravar=False)
    cache.guardar('pesquisar_provas', {'termo': 'auditor'}, {'meta': {}, 'data': []})
    assert not cache.salvar()
    assert not (tmp_path / 'pci.json').exists()


def test_cache_ilegivel_comeca_vazio_com_aviso(tmp_path: Path, caplog):
    caminho = tmp_path / 'pci.json'
    caminho.write_text('{quebrado', encoding='utf-8')
    with caplog.at_level(logging.WARNING):
        assert CachePci(caminho, ttl_horas=24).obter('pesquisar_provas', {'termo': 'x'}) is None
    assert 'buscas guardadas' in caplog.text
    assert 'cache ilegível' in log_completo(caplog)
