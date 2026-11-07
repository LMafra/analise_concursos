import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml
from transporte_pci import concurso

from concursos.aplicacao import integracoes, nomes
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import ler_toml, resolver_contexto
from concursos.erros import ErroDoUsuario
from concursos.integracoes.pci_mcp import ler_concurso
from concursos.status import Situacao, avaliar


@pytest.fixture
def contexto(tmp_path: Path):
    (tmp_path / 'provas').mkdir()
    return resolver_contexto(cwd=tmp_path, data_dir=tmp_path / '.concurso')


def pci(id: int, **campos):
    return ler_concurso(concurso(id, **campos), '2026-11-05')


def test_regiao_do_concurso_pela_regiao_do_pci_pela_uf_e_nacional():
    assert integracoes.regiao_do_concurso(pci(1, regiao='SUDESTE', uf='MG')) == 'Sudeste · MG'
    assert integracoes.regiao_do_concurso(pci(2, regiao='', uf='RS')) == 'Sul · RS'
    assert integracoes.regiao_do_concurso(pci(3, regiao='', uf='BR')) == 'Nacional — todas as regiões'


def test_filtros_lembrados_vao_para_o_pci_mcp_com_o_nome_oficial_da_cidade(contexto):
    integracoes.gravar_filtros_pci(contexto, ['analista', ' auditor '], 'mg', 'belo horizonte', 'sudeste')

    secao = ler_toml(contexto.config_global)['pci_mcp']
    assert (secao['cargos'], secao['uf'], secao['cidade'], secao['regiao']) == (
        ['analista', 'auditor'],
        'mg',
        'Belo Horizonte',
        'sudeste',
    )
    assert integracoes.configuracao_pci(contexto).cidade == 'Belo Horizonte'


def test_busca_sem_filtro_usa_a_cidade_lembrada_so_na_uf_dela(contexto):
    configuracao = integracoes.gravar_filtros_pci(contexto, ['analista'], 'mg', 'Belo Horizonte', None)

    filtros = integracoes.filtros_pci(contexto, configuracao, [], None, None, None, None)
    assert (filtros['uf'], filtros['cidade']) == ('mg', 'Belo Horizonte')
    assert integracoes.filtros_pci(contexto, configuracao, [], 'sp', None, None, None)['cidade'] == ''


def test_cidade_fora_da_uf_ou_sem_uf_e_recusada(contexto):
    with pytest.raises(ErroDoUsuario, match='Belo Horizonte'):
        integracoes.gravar_filtros_pci(contexto, [], 'sp', 'Belo Horizonte', None)
    with pytest.raises(ErroDoUsuario):
        integracoes.gravar_filtros_pci(contexto, [], None, 'Belo Horizonte', None)
    assert not contexto.config_global.exists()


def test_situacao_do_cache_diz_ha_quanto_tempo_foi_atualizado(contexto):
    assert integracoes.situacao_do_cache(contexto) is None
    agora = datetime(2026, 11, 6, 15, 0)
    cache = contexto.projeto / 'cache' / 'pci_mcp.json'
    cache.parent.mkdir(parents=True)
    entradas = {
        'a': {'obtido_em': (agora - timedelta(hours=5)).isoformat(timespec='seconds'), 'resposta': {}},
        'b': {
            'obtido_em': (agora - timedelta(hours=3, minutes=10)).isoformat(timespec='seconds'),
            'resposta': {},
        },
    }
    cache.write_text(json.dumps(entradas), encoding='utf-8')

    assert integracoes.situacao_do_cache(contexto, agora=agora) == 'Atualizado há 3 horas'
    assert (
        integracoes.situacao_do_cache(contexto, agora=agora - timedelta(hours=3))
        == 'Atualizado agora há pouco'
    )


def test_adicionar_ao_projeto_cria_o_concurso_incompleto_com_o_vinculo_e_acompanha(contexto):
    achado = pci(42, titulo='TRE-MG 2026 - Analista Judiciário')
    mensagens: list[str] = []

    pasta = integracoes.adicionar_ao_projeto(Opcoes(contexto, saida=mensagens.append), [achado], 42)

    assert pasta == contexto.provas / 'tre_mg_2026'
    dados = yaml.safe_load((pasta / 'concurso.yaml').read_text(encoding='utf-8'))
    assert dados['pci'] == {
        'id': 42,
        'titulo': 'TRE-MG 2026 - Analista Judiciário',
        'link': 'https://www.pciconcursos.com.br/noticias/42',
    }
    assert integracoes.interesses(contexto).obter(42) is not None
    situacao = avaliar(pasta)
    assert situacao.situacao is Situacao.INCOMPLETO
    assert 'edital' in situacao.motivos[0]
    nome = nomes.nome_sem_cadastro(pasta)
    assert (nome.titulo, nome.a_confirmar) == ('TRE-MG 2026 - Analista Judiciário', True)


def test_adicionar_de_novo_devolve_a_mesma_pasta(contexto):
    achado = pci(42, titulo='TRE-MG 2026 - Analista Judiciário')
    primeira = integracoes.adicionar_ao_projeto(Opcoes(contexto), [achado], 42)

    assert integracoes.adicionar_ao_projeto(Opcoes(contexto), [achado], 42) == primeira
    assert [p.name for p in contexto.provas.iterdir()] == ['tre_mg_2026']


def test_adicionar_id_fora_do_resultado_e_erro_do_usuario(contexto):
    with pytest.raises(ErroDoUsuario):
        integracoes.adicionar_ao_projeto(Opcoes(contexto), [pci(1)], 99)
