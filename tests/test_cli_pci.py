import json
from pathlib import Path

import pytest
import yaml
from conftest import criar_concurso
from transporte_pci import TransporteFalso, concurso, payload

from concursos.candidatos import gravar_perfil_global
from concursos.cli import main
from concursos.concurso_config import ler_dados
from concursos.config.contexto import ler_toml
from concursos.integracoes import pci_mcp
from concursos.integracoes.pci_mcp import PciMcpIndisponivelError, PciMcpParametroError

CONFIG = {
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
}


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    (raiz / 'provas').mkdir(parents=True)
    (raiz / '.concurso').mkdir()
    monkeypatch.chdir(raiz)
    return raiz


@pytest.fixture
def transporte(monkeypatch: pytest.MonkeyPatch) -> TransporteFalso:
    falso = TransporteFalso(
        {
            'buscar_por_cargo': lambda a: payload(
                [concurso(1, titulo='Câmara Alfa'), concurso(2, titulo='Prefeitura Beta')]
                if a['cargo'] == 'analista'
                else [concurso(2, titulo='Prefeitura Beta'), concurso(3, titulo='Tribunal Gama')]
            ),
            'listar_concursos': payload([concurso(9, titulo='Lista Geral', uf='SP')]),
        }
    )
    monkeypatch.setattr(pci_mcp, 'abrir_transporte', lambda configuracao: falso)
    return falso


def ligar() -> None:
    assert main(['--yes', 'pci', 'enable']) == 0


def test_enable_mostra_o_que_vai_e_grava(home_isolada, projeto, capsys):
    ligar()
    secao = ler_toml(home_isolada / 'config.toml')['pci_mcp']
    assert secao['enabled'] is True and secao['url'] == pci_mcp.URL_PADRAO
    saida = capsys.readouterr().out
    assert 'só termos de busca' in saida and 'CPF' in saida


def test_enable_sem_terminal_e_sem_yes_recusa(home_isolada, projeto, capsys):
    assert main(['pci', 'enable']) == 1
    assert not (home_isolada / 'config.toml').exists()
    assert '--yes' in capsys.readouterr().err


def test_disable_desliga(home_isolada, projeto):
    ligar()
    assert main(['pci', 'disable']) == 0
    assert ler_toml(home_isolada / 'config.toml')['pci_mcp']['enabled'] is False


def test_discover_desligado_nao_chama_nada(projeto, transporte, capsys):
    assert main(['discover', '--cargo', 'analista']) == 1
    assert transporte.chamadas == []
    assert 'pci enable' in capsys.readouterr().err


def test_discover_junta_cargos_sem_repetir_e_usa_o_cache_na_segunda(projeto, transporte, capsys, caplog):
    ligar()
    assert main(['discover', '--cargo', 'analista', '--cargo', 'auditor', '--uf', 'MG']) == 0
    saida = capsys.readouterr().out
    assert saida.count('Prefeitura Beta') == 1
    assert 'Câmara Alfa' in saida and 'Tribunal Gama' in saida and 'fecha em 15 dias' in saida
    assert '/2026 a ' in saida and '2026-' not in saida
    assert len(transporte.chamadas) == 2
    assert main(['discover', '--cargo', 'analista', '--cargo', 'auditor', '--uf', 'mg']) == 0
    assert len(transporte.chamadas) == 2
    assert 'PCI: 0 consultas, 2 do cache, 0 falhas' in caplog.text


def test_discover_json(projeto, transporte, capsys):
    ligar()
    capsys.readouterr()
    assert main(['discover', '--cargo', 'analista', '--json']) == 0
    dados = json.loads(capsys.readouterr().out)
    assert [c['id'] for c in dados] == [1, 2]
    assert dados[0]['datas']['dias_ate_fim'] == 15


def test_discover_sem_filtro_usa_os_cargos_do_candidato(home_isolada, projeto, transporte):
    ligar()
    perfil = gravar_perfil_global(home_isolada, 'Maria Teste')
    perfil.write_text(
        perfil.read_text(encoding='utf-8') + '[pci]\ncargos = ["auditor"]\nuf = "df"\n', encoding='utf-8'
    )
    assert main(['--candidate', 'Maria Teste', 'discover']) == 0
    assert transporte.chamadas == [('buscar_por_cargo', {'cargo': 'auditor', 'uf': 'df'})]
    assert all('maria' not in json.dumps(a).lower() for _, a in transporte.chamadas)


def test_discover_sem_cargo_nenhum_usa_a_lista_geral(projeto, transporte, capsys):
    ligar()
    assert main(['discover']) == 0
    assert transporte.chamadas == [('listar_concursos', {})]
    assert 'Lista Geral' in capsys.readouterr().out


def test_discover_offline_sem_cache_nao_chama(projeto, transporte, capsys):
    ligar()
    assert main(['--offline', 'discover', '--cargo', 'analista']) == 0
    assert transporte.chamadas == []
    assert 'nenhum concurso encontrado' in capsys.readouterr().out


def test_discover_dry_run_nao_chama_nem_grava(projeto, transporte):
    ligar()
    assert main(['--dry-run', 'discover', '--cargo', 'analista', '--register', '1']) == 1
    assert transporte.chamadas == []
    assert not (projeto / '.concurso' / 'cache').exists()


def test_falha_do_servidor_e_erro_do_ambiente(projeto, monkeypatch, capsys):
    ligar()
    falso = TransporteFalso({'buscar_por_cargo': PciMcpIndisponivelError('timeout', 'tente mais tarde')})
    monkeypatch.setattr(pci_mcp, 'abrir_transporte', lambda configuracao: falso)
    assert main(['discover', '--cargo', 'analista']) == 2
    erro = capsys.readouterr().err
    assert 'erro: timeout' in erro and 'dica: tente mais tarde' in erro


def test_parametro_recusado_e_erro_do_usuario(projeto, monkeypatch):
    ligar()
    falso = TransporteFalso({'buscar_por_cargo': PciMcpParametroError('UF inválida')})
    monkeypatch.setattr(pci_mcp, 'abrir_transporte', lambda configuracao: falso)
    assert main(['discover', '--cargo', 'analista']) == 1
    assert main(['discover', '--uf', 'minas']) == 1


def test_register_e_forget_mexem_so_nos_interesses(projeto, transporte, capsys):
    ligar()
    assert main(['discover', '--cargo', 'analista', '--register', '2']) == 0
    arquivo = projeto / '.concurso' / 'interesses_pci.yaml'
    itens = yaml.safe_load(arquivo.read_text(encoding='utf-8'))['interesses']
    assert [(i['id'], i['titulo'], i['fim']) for i in itens] == [(2, 'Prefeitura Beta', '2026-11-20')]
    assert sorted(p.name for p in (projeto / 'provas').iterdir()) == []
    assert main(['discover', '--cargo', 'analista', '--register', '77']) == 1
    assert main(['discover', '--forget', '2']) == 0
    assert yaml.safe_load(arquivo.read_text(encoding='utf-8'))['interesses'] == []
    assert main(['discover', '--forget', '2']) == 1


def test_discover_add_cria_a_pasta_a_espera_do_edital(projeto, transporte, capsys):
    ligar()
    assert main(['discover', '--cargo', 'analista', '--add', '2']) == 0
    (pasta,) = (projeto / 'provas').iterdir()
    assert ler_dados(pasta)['pci']['id'] == 2
    assert 'falta o edital' in capsys.readouterr().out
    assert main(['discover', '--cargo', 'analista', '--add', '2']) == 0
    assert len(list((projeto / 'provas').iterdir())) == 1


def test_add_pci_vincula_a_pasta_ao_interesse(projeto, transporte):
    ligar()
    assert main(['discover', '--cargo', 'analista', '--register', '1']) == 0
    pasta = criar_concurso(
        projeto / 'provas', 'camara_alfa', CONFIG, {'gabarito.txt': '1 A\n2 B\n3 C\n4 D\n'}
    )
    assert main(['--yes', 'add', str(pasta), '--pci', '1']) == 0
    assert ler_dados(pasta)['pci'] == {
        'id': 1,
        'titulo': 'Câmara Alfa',
        'link': 'https://www.pciconcursos.com.br/noticias/1',
    }
    itens = yaml.safe_load((projeto / '.concurso' / 'interesses_pci.yaml').read_text(encoding='utf-8'))
    assert itens['interesses'][0]['concurso'] == 'camara_alfa'
    assert main(['--yes', 'add', str(pasta)]) == 0
    assert ler_dados(pasta)['pci']['id'] == 1


def test_add_pci_sem_interesse_recusa(projeto):
    pasta = criar_concurso(projeto / 'provas', 'x', CONFIG, {'gabarito.txt': '1 A\n'})
    assert main(['--yes', 'add', str(pasta), '--pci', '5']) == 1
