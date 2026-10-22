import io
import logging
import time
import tomllib
from pathlib import Path

import pytest
from conftest import criar_concurso

from concursos.cli import main
from concursos.migracao import candidato_padrao

CONFIG = {
    'nome': 'alfa',
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 2]}},
    'respostas': {'arquivo': 'respostas.txt'},
}
ARQUIVOS = {'gabarito.txt': '1 A\n2 B\n', 'respostas.txt': '1 A\n2 C\n'}


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    raiz.mkdir()
    monkeypatch.chdir(raiz)
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.setenv('CONCURSO_DOCTOR', '0')
    return raiz


def roteirizar(monkeypatch: pytest.MonkeyPatch, respostas: str) -> None:
    monkeypatch.setattr('sys.stdin', Terminal(respostas))


def ler(caminho: Path) -> dict:
    return tomllib.loads(caminho.read_text(encoding='utf-8'))


def test_aceitando_os_padroes_grava_as_tres_configuracoes_e_gera_o_indice(
    projeto, home_isolada, monkeypatch, capsys
):
    criar_concurso(projeto / 'provas', 'alfa', CONFIG, ARQUIVOS)
    monkeypatch.delenv('CONCURSO_DOCTOR')
    roteirizar(monkeypatch, '\n' * 10)
    inicio = time.monotonic()

    assert main([]) == 0

    assert time.monotonic() - inicio < 90
    saida = capsys.readouterr().out
    assert '[1/5]' in saida and '[5/5]' in saida
    assert '[provas]' in saida
    assert 'Tesseract' in saida
    candidato = candidato_padrao()
    assert candidato in ler(home_isolada / 'config.toml')['candidatos']['conhecidos']
    assert (home_isolada / 'candidatos' / f'{candidato}.toml').exists()
    projeto_toml = ler(projeto / '.concurso' / 'config.toml')
    assert projeto_toml['pastas'] == {'provas': 'provas', 'analises': 'analises'}
    assert projeto_toml['candidato']['ultimo'] == candidato
    assert (projeto / 'analises' / candidato / 'index.html').exists()


def test_sem_tty_nada_e_perguntado_e_os_padroes_vao_para_o_log(projeto, monkeypatch, caplog):
    criar_concurso(projeto / 'provas', 'alfa', CONFIG, ARQUIVOS)
    monkeypatch.setattr('builtins.input', lambda *_: pytest.fail('perguntou sem TTY'))

    with caplog.at_level(logging.INFO):
        assert main([]) == 0

    assert 'usando os padrões' in caplog.text
    assert (projeto / '.concurso' / 'config.toml').exists()


def test_com_yes_usa_os_padroes_mesmo_com_tty(projeto, monkeypatch):
    criar_concurso(projeto / 'provas', 'alfa', CONFIG, ARQUIVOS)
    roteirizar(monkeypatch, '')

    assert main(['--yes']) == 0
    assert (projeto / '.concurso' / 'config.toml').exists()


def test_segunda_execucao_nao_pergunta_e_init_oferece_as_respostas_atuais(projeto, monkeypatch, capsys):
    criar_concurso(projeto / 'provas', 'alfa', CONFIG, ARQUIVOS)
    roteirizar(monkeypatch, 'Ana Souza\n\n\n\n\n')
    assert main([]) == 0
    capsys.readouterr()

    roteirizar(monkeypatch, '')
    assert main([]) == 0
    assert '[1/' not in capsys.readouterr().out

    roteirizar(monkeypatch, '\n' * 10)
    assert main(['init']) == 0
    saida = capsys.readouterr().out
    assert '[1/5] Seu nome [Ana Souza]' in saida
    assert ler(projeto / '.concurso' / 'config.toml')['candidato']['ultimo'] == 'ana_souza'


def test_pasta_de_provas_inexistente_e_criada_com_leia_me(projeto, monkeypatch, capsys):
    roteirizar(monkeypatch, '\n' * 10)

    assert main([]) == 0

    leia_me = projeto / 'provas' / 'LEIA-ME.txt'
    assert leia_me.exists()
    assert 'concurso.yaml' in leia_me.read_text(encoding='utf-8')
    assert 'LEIA-ME.txt' in capsys.readouterr().out


def test_recusar_o_resumo_nao_grava_nada(projeto, monkeypatch):
    criar_concurso(projeto / 'provas', 'alfa', CONFIG, ARQUIVOS)
    roteirizar(monkeypatch, '\n\n\n\nn\n')

    assert main([]) == 1
    assert not (projeto / '.concurso').exists()


def test_respostas_por_flag_e_variavel_nao_sao_perguntadas(projeto, tmp_path, monkeypatch, capsys):
    outras = tmp_path / 'outras'
    criar_concurso(outras, 'alfa', CONFIG, ARQUIVOS)
    monkeypatch.setenv('CONCURSO_CANDIDATO', 'Bia')
    roteirizar(monkeypatch, '\n' * 10)

    assert main(['--provas', str(outras)]) == 0

    saida = capsys.readouterr().out
    assert 'Seu nome' not in saida and 'Pasta de provas' not in saida
    assert ler(projeto / '.concurso' / 'config.toml')['pastas']['provas'] == str(outras)
