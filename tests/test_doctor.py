import os
import shutil
from pathlib import Path

import pytest

from concursos.cli import main

TESSERACT = '/usr/bin/tesseract'


@pytest.fixture
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Tudo instalado, com o português no Tesseract; cada teste tira o que precisa."""
    estado = {'programas': {'uv': '/usr/bin/uv', 'tesseract': TESSERACT}, 'idiomas': ['eng', 'osd', 'por']}
    monkeypatch.setattr('concursos.doctor.shutil.which', lambda nome: estado['programas'].get(nome))
    monkeypatch.setattr('concursos.doctor._idiomas_do_tesseract', lambda _: estado['idiomas'])
    monkeypatch.setattr('concursos.doctor.platform.system', lambda: 'Linux')
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'provas').mkdir()
    return estado


def rodar(capsys) -> tuple[int, str]:
    codigo = main(['doctor'])
    return codigo, capsys.readouterr().out


def test_com_tudo_certo_sai_com_zero(ambiente, capsys):
    codigo, saida = rodar(capsys)

    assert codigo == 0
    assert '✓ Tesseract' in saida
    assert '✗' not in saida


def test_sem_tesseract_marca_erro_com_o_comando_do_sistema(ambiente, capsys):
    del ambiente['programas']['tesseract']

    codigo, saida = rodar(capsys)

    assert codigo != 0
    assert '✗ Tesseract' in saida
    assert 'sudo apt install tesseract-ocr tesseract-ocr-por' in saida


def test_comando_de_instalacao_segue_o_sistema(ambiente, capsys, monkeypatch):
    del ambiente['programas']['tesseract']
    monkeypatch.setattr('concursos.doctor.platform.system', lambda: 'Darwin')

    _, saida = rodar(capsys)

    assert 'brew install tesseract tesseract-lang' in saida


def test_tesseract_sem_portugues_e_aviso_com_o_pacote_de_idioma(ambiente, capsys):
    ambiente['idiomas'] = ['eng', 'osd']

    codigo, saida = rodar(capsys)

    assert codigo == 0
    assert '! Tesseract' in saida
    assert 'sudo apt install tesseract-ocr-por' in saida


@pytest.mark.skipif(os.name == 'nt' or os.geteuid() == 0, reason='permissão de pasta POSIX, sem root')
def test_pasta_sem_permissao_de_escrita_e_erro_com_a_pasta(ambiente, capsys, tmp_path):
    provas = tmp_path / 'provas'
    provas.chmod(0o500)
    try:
        codigo, saida = rodar(capsys)
    finally:
        provas.chmod(0o700)

    assert codigo != 0
    assert f'✗ escrita em {provas}' in saida


def test_poppler_aparece_como_nao_necessario(ambiente, capsys):
    _, saida = rodar(capsys)

    assert 'poppler: não necessário' in saida


def test_pouco_espaco_em_disco_e_erro(ambiente, capsys, monkeypatch):
    monkeypatch.setattr(
        'concursos.doctor.shutil.disk_usage', lambda _: shutil._ntuple_diskusage(10**9, 10**9, 50 * 2**20)
    )

    codigo, saida = rodar(capsys)

    assert codigo != 0
    assert '✗ espaço em disco' in saida
