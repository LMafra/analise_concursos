import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def paridade():
    especificacao = importlib.util.spec_from_file_location('paridade', RAIZ / 'scripts' / 'paridade.py')
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def analises(tmp_path: Path) -> Path:
    raiz = tmp_path / 'ana'
    (raiz / 'alfa').mkdir(parents=True)
    (raiz / 'consolidado').mkdir()
    (raiz / 'alfa' / 'relatorio.md').write_text('antes', encoding='utf-8')
    (raiz / 'alfa' / 'questoes.csv').write_text('q,1', encoding='utf-8')
    (raiz / 'consolidado' / 'heatmap_topicos.png').write_bytes(b'png')
    return raiz


ESPERADAS = """\
versao = 1

[[esperada]]
padrao = '*/relatorio.md'
motivo = 'relatório reescrito em linguagem leiga'
versao = '0.7.0'
"""


def _retrato(paridade, analises: Path, tmp_path: Path) -> Path:
    arquivo = tmp_path / 'retrato.json'
    assert paridade.main(['retrato', str(analises), str(arquivo)]) == 0
    return arquivo


def test_sem_esperadas_toda_diferenca_reprova(paridade, analises, tmp_path, capsys):
    retrato = _retrato(paridade, analises, tmp_path)
    (analises / 'alfa' / 'relatorio.md').write_text('depois', encoding='utf-8')

    assert paridade.main(['comparar', str(analises), str(retrato)]) == 1
    assert 'mudou: alfa/relatorio.md' in capsys.readouterr().out


def test_diferenca_esperada_passa_com_o_motivo(paridade, analises, tmp_path, capsys):
    retrato = _retrato(paridade, analises, tmp_path)
    esperadas = tmp_path / 'esperadas.toml'
    esperadas.write_text(ESPERADAS, encoding='utf-8')
    (analises / 'alfa' / 'relatorio.md').write_text('depois', encoding='utf-8')

    codigo = paridade.main(['comparar', str(analises), str(retrato), '--esperadas', str(esperadas)])

    saida = capsys.readouterr().out
    assert codigo == 0
    assert 'mudou: alfa/relatorio.md (esperado: relatório reescrito em linguagem leiga)' in saida


def test_diferenca_fora_das_esperadas_reprova_mesmo_com_a_flag(paridade, analises, tmp_path, capsys):
    retrato = _retrato(paridade, analises, tmp_path)
    esperadas = tmp_path / 'esperadas.toml'
    esperadas.write_text(ESPERADAS, encoding='utf-8')
    (analises / 'alfa' / 'relatorio.md').write_text('depois', encoding='utf-8')
    (analises / 'alfa' / 'questoes.csv').write_text('q,2', encoding='utf-8')

    codigo = paridade.main(['comparar', str(analises), str(retrato), '--esperadas', str(esperadas)])

    saida = capsys.readouterr().out
    assert codigo == 1
    assert 'mudou: alfa/questoes.csv\n' in saida
    assert '(esperado:' in saida


def test_esperadas_do_repositorio_tem_padrao_motivo_e_versao(paridade):
    esperadas = paridade.ler_esperadas(RAIZ / 'scripts' / 'paridade_esperadas.toml')
    assert esperadas
    assert all(e.padrao and e.motivo and e.versao for e in esperadas)
    assert paridade.motivo_esperado('alfa/relatorio.md', esperadas)
    dados = ('alfa/questoes.csv', 'alfa/correcao.json', 'consolidado/questoes.parquet')
    assert not any(paridade.motivo_esperado(chave, esperadas) for chave in dados)
