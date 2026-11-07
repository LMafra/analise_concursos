import json
import logging
import re
from datetime import date
from pathlib import Path

import pytest
import yaml
from conftest import com_edital_minimo
from transporte_pci import TransporteFalso, concurso, payload

from concursos.candidatos import gravar_perfil_global
from concursos.cli import main
from concursos.integracoes import pci_mcp
from concursos.integracoes.pci_mcp import PciMcpIndisponivelError, ler_concurso
from concursos.integracoes.radar_pci import (
    ARQUIVO_RADAR,
    ARQUIVO_RADAR_JSON,
    gravar_radar,
    ler_radar,
    montar_radar,
    no_radar,
)

HOJE = date(2026, 11, 5)


def pci(id: int, **datas) -> pci_mcp.ConcursoPci:
    return ler_concurso(concurso(id, datas=datas), '2026-11-05')


@pytest.mark.parametrize(
    ('datas', 'entra'),
    [
        ({'dias_ate_fim': 15}, True),
        ({'dias_ate_fim': 16}, False),
        ({'dias_ate_fim': 0}, True),
        ({'dias_ate_fim': None}, False),
        ({'aberto': False, 'em_breve': True, 'dias_ate_inicio': 5}, True),
        ({'aberto': False, 'em_breve': True, 'dias_ate_inicio': 62}, False),
        ({'aberto': False, 'em_breve': True, 'dias_ate_inicio': None}, False),
        ({'aberto': False, 'em_breve': False, 'dias_ate_inicio': -30, 'dias_ate_fim': -1}, False),
    ],
)
def test_criterio_do_radar(datas: dict, entra: bool):
    assert no_radar(pci(1, **datas), 15) is entra


def test_interesses_entram_ate_o_fim_e_juntam_pelo_id():
    encontrados = [
        pci(1, dias_ate_fim=3),
        pci(2, dias_ate_fim=40, fim='2026-12-15'),
        pci(3, dias_ate_fim=40),
    ]
    interesses = [
        {'id': 2, 'titulo': 'Interesse Aberto', 'concurso': 'camara_alfa'},
        {'id': 7, 'titulo': 'Só No Arquivo', 'uf': 'SP', 'inicio': '2026-11-01', 'fim': '2026-11-10'},
        {'id': 8, 'titulo': 'Já Fechou', 'inicio': '2026-10-01', 'fim': '2026-11-04'},
        {'id': 9, 'titulo': 'Vai Abrir', 'inicio': '2026-11-20', 'fim': '2026-12-20'},
    ]

    radar = montar_radar(encontrados, interesses, 15, ('analista',), HOJE)

    assert [item.id for item in radar.itens] == [1, 7, 2, 9]
    por_id = {item.id: item for item in radar.itens}
    assert por_id[2].interesse and por_id[2].concurso == 'camara_alfa'
    assert por_id[7].situacao == 'aberto, fecha em 5 dias'
    assert por_id[9].situacao == 'abre em 15 dias'
    assert not por_id[1].interesse
    assert radar.data_referencia == '2026-11-05'


def test_gravar_de_novo_sem_mudanca_preserva_o_mtime(tmp_path: Path):
    radar = montar_radar([pci(1, dias_ate_fim=3)], [], 15, ('analista',), HOJE)
    assert gravar_radar(tmp_path, radar)
    antes = (tmp_path / ARQUIVO_RADAR).stat().st_mtime_ns

    assert not gravar_radar(tmp_path, radar)

    assert (tmp_path / ARQUIVO_RADAR).stat().st_mtime_ns == antes
    assert ler_radar(tmp_path) == radar
    texto = (tmp_path / ARQUIVO_RADAR).read_text(encoding='utf-8')
    assert '# Prazos dos editais' in texto and 'aberto, fecha em 3 dias' in texto


def test_sem_cargos_avisa_que_so_mostra_os_interesses(tmp_path: Path):
    gravar_radar(tmp_path, montar_radar([], [], 15, (), HOJE))
    texto = (tmp_path / ARQUIVO_RADAR).read_text(encoding='utf-8')
    assert 'Sem cargos de interesse' in texto and 'Nenhum edital' in texto


CONCURSO = {
    'nome': 'alfa',
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
}


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, home_isolada: Path) -> Path:
    raiz = tmp_path / 'projeto'
    pasta = raiz / 'provas' / 'alfa'
    pasta.mkdir(parents=True)
    (raiz / '.concurso').mkdir()
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(com_edital_minimo(pasta, CONCURSO)), encoding='utf-8')
    (pasta / 'gabarito.txt').write_text('1 A\n2 B\n3 C\n4 D\n', encoding='utf-8')
    candidata = pasta / 'candidatos' / 'alice'
    candidata.mkdir(parents=True)
    (candidata / 'respostas.txt').write_text('1 A\n2 B\n3 C\n4 E\n', encoding='utf-8')
    (candidata / 'candidato.yaml').write_text(yaml.safe_dump({'respostas': {'arquivo': 'respostas.txt'}}))
    perfil = gravar_perfil_global(home_isolada, 'alice')
    perfil.write_text(
        perfil.read_text(encoding='utf-8') + '\n[pci]\ncargos = ["analista"]\nuf = "mg"\n', encoding='utf-8'
    )
    monkeypatch.chdir(raiz)
    return raiz


@pytest.fixture
def transporte(monkeypatch: pytest.MonkeyPatch) -> TransporteFalso:
    falso = TransporteFalso(
        {
            'buscar_por_cargo': payload(
                [
                    concurso(1, titulo='Câmara Alfa', datas={'dias_ate_fim': 4, 'fim': '2026-11-09'}),
                    concurso(2, titulo='Prefeitura Longe', datas={'dias_ate_fim': 90}),
                ]
            )
        }
    )
    monkeypatch.setattr(pci_mcp, 'abrir_transporte', lambda configuracao: falso)
    return falso


def ligar() -> None:
    assert main(['--yes', 'pci', 'enable']) == 0


def test_desligado_nao_gera_radar_nem_chama_o_pci(projeto: Path):
    assert main(['--candidate', 'alice']) == 0
    assert not (projeto / 'analises' / 'alice' / ARQUIVO_RADAR).exists()
    assert 'id="prazos"' not in (projeto / 'analises' / 'alice' / 'index.html').read_text()


def test_radar_depois_da_analise_no_indice_status_e_doctor(
    projeto: Path, transporte, capsys, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr('concursos.doctor._sdk_mcp_instalado', lambda: True)
    ligar()
    assert main(['--candidate', 'alice']) == 0

    destino = projeto / 'analises' / 'alice'
    assert transporte.chamadas == [('buscar_por_cargo', {'cargo': 'analista', 'uf': 'mg'})]
    radar = json.loads((destino / ARQUIVO_RADAR_JSON).read_text(encoding='utf-8'))
    assert [item['id'] for item in radar['itens']] == [1]
    indice = (destino / 'index.html').read_text(encoding='utf-8')
    assert '<section id="prazos">\n<h2>Prazos dos editais</h2>' in indice and 'Câmara Alfa' in indice
    markdown = (destino / ARQUIVO_RADAR).read_text(encoding='utf-8')
    assert re.search(r'\d{2}/\d{2}/\d{4}', markdown) and not re.search(r'\d{4}-\d{2}-\d{2}', markdown)
    assert not re.search(
        r'\d{4}-\d{2}-\d{2}', indice.split('<section id="prazos">')[1].split('</section>')[0]
    )
    assert re.match(r'\d{4}-\d{2}-\d{2}$', radar['data_referencia'])
    capsys.readouterr()

    transporte.chamadas.clear()
    assert main(['status']) == 0
    assert main(['doctor']) in (0, 2)
    saida = capsys.readouterr().out
    assert transporte.chamadas == []
    assert 'radar PCI (alice): 1 edital(is) no radar' in saida
    assert 'PCI Concursos: ' in saida and 'Câmara Alfa (aberto, fecha em 4 dias)' in saida


def test_segunda_analise_usa_o_cache_e_nao_regrava(projeto: Path, transporte):
    ligar()
    assert main(['--candidate', 'alice']) == 0
    arquivo = projeto / 'analises' / 'alice' / ARQUIVO_RADAR
    antes = arquivo.stat().st_mtime_ns
    indice = (projeto / 'analises' / 'alice' / 'index.html').stat().st_mtime_ns

    assert main(['--candidate', 'alice']) == 0

    assert len(transporte.chamadas) == 1
    assert arquivo.stat().st_mtime_ns == antes
    assert (projeto / 'analises' / 'alice' / 'index.html').stat().st_mtime_ns == indice


def test_falha_do_pci_vira_aviso_e_a_analise_segue(projeto: Path, monkeypatch: pytest.MonkeyPatch, caplog):
    falso = TransporteFalso({'buscar_por_cargo': PciMcpIndisponivelError('timeout')})
    monkeypatch.setattr(pci_mcp, 'abrir_transporte', lambda configuracao: falso)
    ligar()

    with caplog.at_level(logging.WARNING):
        assert main(['--candidate', 'alice']) == 0

    assert (projeto / 'analises' / 'alice' / 'alfa' / 'relatorio.md').exists()
    assert 'radar não atualizado' in caplog.text


def test_offline_usa_so_o_cache(projeto: Path, transporte, monkeypatch: pytest.MonkeyPatch):
    ligar()
    assert main(['--candidate', 'alice']) == 0
    (projeto / 'analises' / 'alice' / ARQUIVO_RADAR).unlink()
    monkeypatch.setattr(
        pci_mcp, 'abrir_transporte', lambda configuracao: pytest.fail('abriu o transporte com --offline')
    )

    assert main(['--offline', '--candidate', 'alice', '--force']) == 0

    assert (projeto / 'analises' / 'alice' / ARQUIVO_RADAR).exists()


def test_dry_run_nao_gera_radar(projeto: Path, transporte):
    ligar()
    assert main(['--dry-run', '--candidate', 'alice']) == 0
    assert transporte.chamadas == []
    assert not (projeto / 'analises' / 'alice' / ARQUIVO_RADAR).exists()


def test_doctor_sem_o_extra_avisa_como_instalar(projeto: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setattr('concursos.doctor._sdk_mcp_instalado', lambda: False)
    ligar()
    main(['doctor'])
    assert "uv tool install 'concurso-analise[pci]'" in capsys.readouterr().out
