import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def script():
    especificacao = importlib.util.spec_from_file_location(
        'relatorio_smoke', RAIZ / 'scripts' / 'relatorio_smoke.py'
    )
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


def gravar_relatorios(pasta: Path, nomes: list[str]) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in nomes:
        sistema = nome.removeprefix('smoke-').removesuffix('.md')
        (pasta / nome).write_text(f'## {sistema}\n\n- smoke ok\n', encoding='utf-8')


TODOS = ['smoke-linux-ubuntu-22-04.md', 'smoke-windows.md', 'smoke-linux-debian-12.md']


def test_junta_windows_e_depois_linux_com_cabecalho(script, tmp_path):
    gravar_relatorios(tmp_path, TODOS)

    texto = script.montar('0.6.0', 'abc1234', tmp_path)

    assert texto.startswith('# Relatório de smoke: concurso-analise 0.6.0\n')
    assert 'commit `abc1234`' in texto
    posicoes = [texto.index(f'## {s}') for s in ('windows', 'linux-debian-12', 'linux-ubuntu-22-04')]
    assert posicoes == sorted(posicoes)
    assert 'checklist manual' in texto


def test_bom_do_powershell_nao_entra_no_relatorio(script, tmp_path):
    gravar_relatorios(tmp_path, TODOS)
    (tmp_path / 'smoke-windows.md').write_text('## windows\n', encoding='utf-8-sig')

    assert '\ufeff' not in script.montar('0.6.0', 'abc1234', tmp_path)


def test_falta_de_um_relatorio_obrigatorio_falha(script, tmp_path):
    gravar_relatorios(tmp_path, ['smoke-windows.md', 'smoke-linux-debian-12.md'])

    with pytest.raises(SystemExit, match='smoke-linux-ubuntu-22-04.md'):
        script.montar('0.6.0', 'abc1234', tmp_path)


def test_linha_de_comando_grava_o_destino(script, tmp_path):
    gravar_relatorios(tmp_path / 'relatorios', TODOS)
    destino = tmp_path / 'dist' / 'RELATORIO-SMOKE.md'
    destino.parent.mkdir()

    script.main(['0.6.0', 'abc1234', str(tmp_path / 'relatorios'), str(destino)])

    assert destino.read_text(encoding='utf-8') == script.montar('0.6.0', 'abc1234', tmp_path / 'relatorios')
