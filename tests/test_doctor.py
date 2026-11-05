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


def test_open_notebook_desligado_aparece_sem_rede(ambiente, capsys):
    _, saida = rodar(capsys)

    assert '✓ open-notebook: desligado' in saida


def test_open_notebook_ligado_mostra_a_url_sem_consultar_a_instancia(
    ambiente, capsys, home_isolada, monkeypatch
):
    home_isolada.mkdir(parents=True, exist_ok=True)
    (home_isolada / 'config.toml').write_text(
        '[open_notebook]\nenabled = true\nconsentimento = true\nurl = "http://127.0.0.1:1"\n',
        encoding='utf-8',
    )
    monkeypatch.setattr('urllib.request.urlopen', lambda *_a, **_k: pytest.fail('o doctor não usa a rede'))

    codigo, saida = rodar(capsys)

    assert codigo == 0
    assert '✓ open-notebook: http://127.0.0.1:1, sem senha' in saida


def test_open_notebook_sem_consentimento_e_aviso(ambiente, capsys, home_isolada):
    home_isolada.mkdir(parents=True, exist_ok=True)
    (home_isolada / 'config.toml').write_text('[open_notebook]\nenabled = true\n', encoding='utf-8')

    _, saida = rodar(capsys)

    assert '! open-notebook' in saida
    assert 'concurso-analise notebook enable' in saida


def test_open_notebook_com_configuracao_invalida_e_erro(ambiente, capsys, home_isolada):
    home_isolada.mkdir(parents=True, exist_ok=True)
    (home_isolada / 'config.toml').write_text('[open_notebook]\nenabled = "sim"\n', encoding='utf-8')

    codigo, saida = rodar(capsys)

    assert codigo != 0
    assert '✗ open-notebook' in saida


def test_legislacao_sem_secao_e_ok(ambiente, capsys):
    _, saida = rodar(capsys)

    assert '✓ legislação: sem [legislacao]' in saida


def test_legislacao_confere_o_clone_sem_rede(ambiente, capsys, home_isolada, tmp_path):
    home_isolada.mkdir(parents=True, exist_ok=True)
    clone = tmp_path / 'leis'
    (home_isolada / 'config.toml').write_text(
        f'[legislacao]\nrepositorio = "{clone.as_posix()}"\n', encoding='utf-8'
    )

    _, sem_clone = rodar(capsys)
    clone.mkdir()
    _, sem_pasta = rodar(capsys)
    (clone / 'federal' / 'leis-ordinarias').mkdir(parents=True)
    codigo, com_clone = rodar(capsys)

    assert f'! legislação: {clone} não existe' in sem_clone and 'git clone --filter=blob:none' in sem_clone
    assert 'git sparse-checkout add federal/leis-ordinarias' in sem_pasta
    assert f'✓ legislação: {clone}' in com_clone and codigo == 0


def test_pouco_espaco_em_disco_e_erro(ambiente, capsys, monkeypatch):
    monkeypatch.setattr(
        'concursos.doctor.shutil.disk_usage', lambda _: shutil._ntuple_diskusage(10**9, 10**9, 50 * 2**20)
    )

    codigo, saida = rodar(capsys)

    assert codigo != 0
    assert '✗ espaço em disco' in saida
