import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from transporte_pci import TransporteFalso, concurso, fixture, payload, resposta

from concursos.candidatos import alvos_pci, gravar_perfil_global
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.integracoes.cache_pci import CachePci
from concursos.integracoes.pci_mcp import (
    FERRAMENTAS,
    URL_PADRAO,
    ClientePciMcp,
    ConfiguracaoPciMcp,
    PciMcpFormatoError,
    PciMcpIndisponivelError,
    PciMcpParametroError,
    TransporteSdk,
    gravar_configuracao,
    interpretar,
    ler_configuracao,
)

AGORA = datetime(2026, 11, 5, 10, 0)


class Relogio:
    def __init__(self) -> None:
        self.agora = AGORA

    def __call__(self) -> datetime:
        return self.agora


@pytest.fixture
def relogio() -> Relogio:
    return Relogio()


@pytest.fixture
def cache(tmp_path: Path, relogio: Relogio) -> CachePci:
    return CachePci(tmp_path / 'cache' / 'pci_mcp.json', ttl_horas=24, agora=relogio)


def test_fixtures_gravadas_tem_as_cinco_ferramentas_e_o_formato_esperado():
    nomes = [f['name'] for f in fixture('tools_list')]
    assert sorted(nomes) == sorted(FERRAMENTAS)
    assert 'buscar_apostilas' not in nomes
    for ferramenta in FERRAMENTAS:
        dados = resposta(ferramenta)
        assert dados['meta']['data_atual']


def test_message_vira_lista_vazia(cache):
    transporte = TransporteFalso({'pesquisar_provas': resposta('pesquisar_provas_vazio')})
    assert ClientePciMcp(transporte, cache).pesquisar_provas_anteriores('xyzw inexistente') == []


def test_is_error_vira_erro_de_parametro():
    gravada = fixture('buscar_por_cargo_uf_invalida')
    with pytest.raises(PciMcpParametroError, match='UF inválida'):
        interpretar(gravada['ferramenta'], gravada['is_error'], gravada['texto'])


@pytest.mark.parametrize('texto', ['não é json', '{"meta": {}}', '[]', '{"data": [], "meta": []}'])
def test_resposta_sem_meta_e_data_vira_erro_de_formato(texto: str):
    with pytest.raises(PciMcpFormatoError):
        interpretar('buscar_por_cargo', False, texto)


def test_item_sem_id_vira_erro_de_formato(cache):
    transporte = TransporteFalso({'buscar_por_cargo': payload([{'titulo': 'sem id'}])})
    with pytest.raises(PciMcpFormatoError, match='id'):
        ClientePciMcp(transporte, cache).buscar_concursos(cargos=['analista'])


def test_busca_por_cargo_le_os_campos_da_fixture_real(cache):
    concursos = ClientePciMcp(TransporteFalso(), cache).buscar_concursos(cargos=['analista'], uf='MG')
    bruto = resposta('buscar_por_cargo')['data'][0]
    primeiro = concursos[0]
    assert primeiro.id == bruto['id'] and primeiro.titulo == bruto['titulo']
    assert primeiro.datas.dias_ate_fim == bruto['datas']['dias_ate_fim']
    assert primeiro.link == bruto['noticia']['link']
    assert primeiro.data_referencia == resposta('buscar_por_cargo')['meta']['data_atual']


def test_uma_consulta_por_cargo_juntando_pelo_id(cache):
    por_cargo = {
        'analista': payload([concurso(1), concurso(2)]),
        'auditor': payload([concurso(2), concurso(3)]),
    }
    transporte = TransporteFalso({'buscar_por_cargo': lambda argumentos: por_cargo[argumentos['cargo']]})
    concursos = ClientePciMcp(transporte, cache).buscar_concursos(cargos=['analista', 'auditor'], uf='mg')
    assert [c.id for c in concursos] == [1, 2, 3]
    assert transporte.chamadas == [
        ('buscar_por_cargo', {'cargo': 'analista', 'uf': 'mg'}),
        ('buscar_por_cargo', {'cargo': 'auditor', 'uf': 'mg'}),
    ]


def test_sem_filtro_usa_a_lista_geral_e_filtra_a_uf(cache):
    transporte = TransporteFalso({'listar_concursos': payload([concurso(1, uf='MG'), concurso(2, uf='SP')])})
    concursos = ClientePciMcp(transporte, cache).buscar_concursos(uf='sp', regiao='sudeste')
    assert [c.id for c in concursos] == [2]
    assert transporte.chamadas == [('listar_concursos', {'regiao': 'sudeste'})]


def test_cidade_sem_uf_reprova_sem_chamar(cache):
    transporte = TransporteFalso()
    with pytest.raises(PciMcpParametroError, match='UF'):
        ClientePciMcp(transporte, cache).buscar_concursos(cidade='campinas')
    assert transporte.chamadas == []


def test_dentro_do_ttl_nao_chama_de_novo_e_o_cache_nao_muda(cache, relogio):
    transporte = TransporteFalso()
    cliente = ClientePciMcp(transporte, cache)
    cliente.buscar_concursos(cargos=['Analista'], uf='mg')
    assert cache.salvar()
    mtime = cache.caminho.stat().st_mtime_ns
    relogio.agora += timedelta(hours=23)
    novo = ClientePciMcp(transporte, CachePci(cache.caminho, 24, agora=relogio))
    novo.buscar_concursos(cargos=['analista'], uf='MG')
    assert len(transporte.chamadas) == 1
    assert novo.resumo() == 'PCI: 0 consultas, 1 do cache, 0 falhas'
    assert not novo.cache.salvar()
    assert cache.caminho.stat().st_mtime_ns == mtime


def test_cache_guarda_ferramenta_argumentos_e_data_atual(cache):
    ClientePciMcp(TransporteFalso(), cache).buscar_concursos(cargos=['analista'], uf='mg')
    cache.salvar()
    entrada = next(iter(json.loads(cache.caminho.read_text(encoding='utf-8')).values()))
    assert entrada['ferramenta'] == 'buscar_por_cargo'
    assert entrada['argumentos'] == {'cargo': 'analista', 'uf': 'mg'}
    assert entrada['obtido_em'] == AGORA.isoformat(timespec='seconds')
    assert entrada['data_atual'] == resposta('buscar_por_cargo')['meta']['data_atual']


def test_vencido_ou_refresh_chama_de_novo(cache, relogio):
    transporte = TransporteFalso()
    ClientePciMcp(transporte, cache).buscar_concursos(cargos=['analista'])
    ClientePciMcp(transporte, cache, refresh=True).buscar_concursos(cargos=['analista'])
    relogio.agora += timedelta(hours=25)
    ClientePciMcp(transporte, cache).buscar_concursos(cargos=['analista'])
    assert len(transporte.chamadas) == 3


def test_erro_de_parametro_nao_entra_no_cache(cache):
    transporte = TransporteFalso({'buscar_por_cargo': PciMcpParametroError('UF inválida')})
    with pytest.raises(PciMcpParametroError):
        ClientePciMcp(transporte, cache).buscar_concursos(cargos=['analista'], uf='xx')
    assert cache.entradas == {}


def test_offline_usa_o_cache_vencido_com_aviso_e_nunca_chama(cache, relogio, caplog):
    ClientePciMcp(TransporteFalso(), cache).buscar_concursos(cargos=['analista'])
    relogio.agora += timedelta(days=3)
    offline = ClientePciMcp(None, cache)
    with caplog.at_level(logging.WARNING):
        concursos = offline.buscar_concursos(cargos=['analista', 'auditor'])
    assert concursos
    assert 'cache de 2026-11-05T10:00:00' in caplog.text
    assert 'sem rede e sem cache' in caplog.text


def test_falha_de_rede_usa_o_cache_vencido_ou_propaga(cache, relogio, caplog):
    ClientePciMcp(TransporteFalso(), cache).buscar_concursos(cargos=['analista'])
    relogio.agora += timedelta(days=3)
    fora = TransporteFalso({'buscar_por_cargo': PciMcpIndisponivelError('timeout')})
    cliente = ClientePciMcp(fora, cache)
    with caplog.at_level(logging.WARNING):
        assert cliente.buscar_concursos(cargos=['analista'])
    assert 'usando o cache vencido' in caplog.text
    assert cliente.falhas == 1
    with pytest.raises(PciMcpIndisponivelError):
        cliente.buscar_concursos(cargos=['sem cache'])


def test_ferramenta_ausente_avisa_e_pula(cache, caplog):
    transporte = TransporteFalso(ferramentas=('listar_concursos',))
    with caplog.at_level(logging.WARNING):
        assert ClientePciMcp(transporte, cache).pesquisar_provas_anteriores('auditor') == []
    assert 'não tem mais a ferramenta pesquisar_provas' in caplog.text
    assert transporte.chamadas == []


def test_limite_de_consultas_corta_e_avisa(cache, caplog):
    transporte = TransporteFalso({'buscar_por_cargo': lambda a: payload([concurso(len(a['cargo']))])})
    cliente = ClientePciMcp(transporte, cache, maximo=2)
    with caplog.at_level(logging.WARNING):
        cliente.buscar_concursos(cargos=['a', 'bb', 'ccc', 'dddd'])
    assert len(transporte.chamadas) == 2
    assert caplog.text.count('limite de 2 consultas') == 1


def test_argumentos_so_tem_termos_de_busca(cache):
    transporte = TransporteFalso()
    cliente = ClientePciMcp(transporte, cache)
    cliente.buscar_concursos(cargos=['analista'], uf='mg', cidade='campinas', termo='receita')
    cliente.pesquisar_provas_anteriores('auditor fiscal')
    permitidos = {'cargo', 'uf', 'cidade', 'termo', 'regiao', 'professores'}
    assert all(set(argumentos) <= permitidos for _, argumentos in transporte.chamadas)


def test_transporte_sdk_fala_com_servidor_mcp_em_memoria():
    pytest.importorskip('mcp')
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError

    servidor = MCPServer('falso')
    recebidos: list[dict] = []

    @servidor.tool()
    def pesquisar_provas(termo: str) -> str:
        recebidos.append({'termo': termo})
        return json.dumps(payload([{'id': 7, 'descricao': 'Auditor', 'orgao': 'X', 'ano': 2020}]))

    @servidor.tool()
    def buscar_por_cargo(cargo: str, uf: str = '') -> str:
        raise ToolError('UF inválida. Use 2 letras minúsculas, ex: sp.')

    with TransporteSdk(servidor, timeout=5) as transporte:
        assert {'pesquisar_provas', 'buscar_por_cargo'} <= transporte.ferramentas()
        dados = transporte.chamar('pesquisar_provas', {'termo': 'auditor'})
        assert dados['data'][0]['id'] == 7
        with pytest.raises(PciMcpParametroError, match='UF inválida'):
            transporte.chamar('buscar_por_cargo', {'cargo': 'x', 'uf': 'xyz'})
    assert recebidos == [{'termo': 'auditor'}]


def test_transporte_sdk_sem_servidor_vira_indisponivel():
    pytest.importorskip('mcp')
    with (
        TransporteSdk('http://127.0.0.1:9/mcp', timeout=2) as transporte,
        pytest.raises(PciMcpIndisponivelError) as erro,
    ):
        transporte.ferramentas()
    assert erro.value.dica


def test_sem_secao_a_integracao_fica_desligada(tmp_path: Path):
    configuracao = ler_configuracao(tmp_path / 'config.toml')
    assert configuracao == ConfiguracaoPciMcp()
    assert not configuracao.enabled
    assert configuracao.url == URL_PADRAO == 'https://mcp.pciconcursos.com.br/mcp'
    assert (configuracao.timeout, configuracao.ttl_horas, configuracao.dias_alerta) == (30, 24, 15)


def test_le_cargos_uf_e_regiao(tmp_path: Path):
    caminho = tmp_path / 'config.toml'
    caminho.write_text(
        '[pci_mcp]\nenabled = true\ncargos = ["analista", "auditor fiscal"]\nuf = "MG"\nregiao = "sudeste"\n',
        encoding='utf-8',
    )
    configuracao = ler_configuracao(caminho)
    assert configuracao.enabled
    assert configuracao.cargos == ('analista', 'auditor fiscal')
    assert configuracao.uf == 'mg'
    assert configuracao.regiao == 'sudeste'


@pytest.mark.parametrize(
    'linha',
    [
        'chave = "x"',
        'timeout = 0',
        'ttl_horas = -1',
        'dias_alerta = 1.5',
        'cargos = "analista"',
        'cargos = [""]',
        'uf = "minas"',
        'regiao = "litoral"',
        'enabled = "sim"',
    ],
)
def test_campo_desconhecido_ou_invalido_reprova(tmp_path: Path, linha: str):
    caminho = tmp_path / 'config.toml'
    caminho.write_text(f'[pci_mcp]\n{linha}\n', encoding='utf-8')
    with pytest.raises(ConfiguracaoInvalidaError, match=linha.split(' ')[0]):
        ler_configuracao(caminho)


def test_gravar_preserva_outras_secoes(tmp_path: Path):
    caminho = tmp_path / 'config.toml'
    caminho.write_text('[llm]\nprovedor = "nenhum"\n', encoding='utf-8')
    gravada = gravar_configuracao(caminho, enabled=True, cargos=('analista',))
    assert gravada.enabled and gravada.cargos == ('analista',)
    texto = caminho.read_text(encoding='utf-8')
    assert '[llm]' in texto and '[pci_mcp]' in texto


def test_alvos_vem_do_perfil_global_do_candidato(tmp_path: Path):
    perfil = gravar_perfil_global(tmp_path, 'Maria Teste')
    perfil.write_text(
        perfil.read_text(encoding='utf-8') + '\n[pci]\ncargos = ["auditor fiscal"]\nuf = "DF"\n',
        encoding='utf-8',
    )
    assert alvos_pci(tmp_path, 'maria_teste') == (('auditor fiscal',), 'df')
    assert alvos_pci(tmp_path, 'outro') == ((), '')


def test_alvos_invalidos_no_perfil_reprovam(tmp_path: Path):
    perfil = gravar_perfil_global(tmp_path, 'Maria Teste')
    perfil.write_text('nome = "Maria Teste"\n[pci]\ncargos = "auditor"\n', encoding='utf-8')
    with pytest.raises(ConfiguracaoInvalidaError, match='cargos'):
        alvos_pci(tmp_path, 'maria_teste')


def test_atualizar_perfil_global_preserva_a_secao_pci(tmp_path: Path):
    perfil = gravar_perfil_global(tmp_path, 'Maria Teste')
    perfil.write_text(
        perfil.read_text(encoding='utf-8') + '\n[pci]\ncargos = ["analista"]\n', encoding='utf-8'
    )
    gravar_perfil_global(tmp_path, 'Maria Teste', atualizar=True)
    assert alvos_pci(tmp_path, 'maria_teste') == (('analista',), '')
