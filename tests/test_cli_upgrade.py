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
