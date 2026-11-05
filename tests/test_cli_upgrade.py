import subprocess

import pytest

from concursos.cli import main
from concursos.cli.erros import CODIGO_AMBIENTE


@pytest.fixture
def chamadas(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    feitas: list[list[str]] = []

    def executar(comando, check=False):
        feitas.append(comando)
        return subprocess.CompletedProcess(comando, 0)

    monkeypatch.setattr('concursos.cli.comandos.subprocess.run', executar)
    monkeypatch.setattr('concursos.cli.comandos.shutil.which', lambda nome: f'/usr/bin/{nome}')
    return feitas


def test_sem_run_so_imprime_o_comando(chamadas, capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert main(['upgrade']) == 0

    assert 'uv tool upgrade concurso-analise' in capsys.readouterr().out
    assert chamadas == []


def test_com_run_executa_o_uv(chamadas, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert main(['upgrade', '--run']) == 0

    assert chamadas == [['/usr/bin/uv', 'tool', 'upgrade', 'concurso-analise']]


def test_com_run_e_dry_run_nao_executa(chamadas, capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert main(['--dry-run', 'upgrade', '--run']) == 0

    assert chamadas == []
    assert 'uv tool upgrade concurso-analise' in capsys.readouterr().out


def test_sem_uv_e_erro_de_ambiente_com_dica(chamadas, capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('concursos.cli.comandos.shutil.which', lambda nome: None)

    assert main(['upgrade', '--run']) == CODIGO_AMBIENTE

    assert 'uv' in capsys.readouterr().err
    assert chamadas == []


@pytest.fixture
def no_executavel(monkeypatch: pytest.MonkeyPatch, home_isolada) -> list[dict]:
    """O `upgrade` como no executável, com a consulta ao GitHub trocada por um registro dos pedidos."""
    from concursos.aplicacao import atualizador as aplicacao

    pedidos: list[dict] = []

    def atualizar(opcoes, *, canal, executar):
        pedidos.append({'canal': canal, 'executar': executar, 'dry_run': opcoes.dry_run, 'rede': opcoes.rede})
        return 0

    monkeypatch.setattr(aplicacao, 'no_executavel', lambda: True)
    monkeypatch.setattr(aplicacao, 'atualizar_executavel', atualizar)
    return pedidos


def test_no_executavel_upgrade_usa_o_atualizador_e_nao_o_uv(no_executavel, chamadas, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert main(['upgrade', '--run', '--canal', 'beta']) == 0

    assert chamadas == []
    assert no_executavel[0]['canal'] == 'beta'
    assert no_executavel[0]['executar'] is True


def test_no_executavel_offline_e_dry_run_chegam_ao_atualizador(no_executavel, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    main(['--offline', 'upgrade'])
    main(['--dry-run', 'upgrade'])

    assert no_executavel[0]['rede'] is False
    assert no_executavel[1]['dry_run'] is True
