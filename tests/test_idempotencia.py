from pathlib import Path

import pytest
from conftest import criar_concurso

from concursos.cli import main

CONFIG = {
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
}


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    for nome in ('alfa', 'beta'):
        pasta = criar_concurso(raiz / 'provas', nome, CONFIG, {'gabarito.txt': '1 A\n2 B\n3 C\n4 D\n'})
        (pasta / 'candidatos' / 'ana').mkdir(parents=True)
        (pasta / 'candidatos' / 'ana' / 'respostas.txt').write_text('1 A\n2 B\n3 D\n4 D\n', encoding='utf-8')
    monkeypatch.chdir(raiz)
    return raiz


def mtimes(pasta: Path) -> dict[str, int]:
    return {str(p.relative_to(pasta)): p.stat().st_mtime_ns for p in sorted(pasta.rglob('*')) if p.is_file()}


def test_duas_execucoes_seguidas_nao_alteram_nenhum_mtime(projeto):
    assert main(['--yes', '--no-open']) == 0
    antes = mtimes(projeto / 'analises')

    assert main(['--yes', '--no-open']) == 0

    assert mtimes(projeto / 'analises') == antes


def test_dry_run_duas_vezes_nao_altera_nenhum_mtime(projeto):
    assert main(['--yes', '--no-open']) == 0
    antes = mtimes(projeto / 'analises')

    assert main(['--dry-run', '--yes']) == 0
    assert main(['--dry-run', '--yes']) == 0

    assert mtimes(projeto / 'analises') == antes


def test_dry_run_num_projeto_novo_nao_cria_nada(projeto):
    assert main(['--dry-run', '--yes']) == 0

    assert not (projeto / 'analises').exists()
    assert not (projeto / '.concurso').exists()
