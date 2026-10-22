import logging
from pathlib import Path

import pytest
from conftest import criar_concurso

from concursos.cli import executar_legado, main
from concursos.config.contexto import resolver_contexto
from concursos.migracao import candidato_padrao


def config(nome: str) -> dict:
    return {
        'nome': nome,
        'banca': 'fgv',
        'formato': 'multipla_escolha',
        'pontuacao': 'simples',
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 2]}},
        'respostas': {'arquivo': 'respostas.txt'},
    }


ARQUIVOS = {'gabarito.txt': '1 A\n2 B\n', 'respostas.txt': '1 A\n2 C\n'}


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    raiz.mkdir()
    monkeypatch.chdir(raiz)
    return raiz


def test_sem_subcomando_analisa_as_provas_da_pasta_atual(projeto, caplog):
    criar_concurso(projeto / 'provas', 'alfa', config('alfa'), ARQUIVOS)

    assert main([]) == 0
    assert (projeto / 'analises' / candidato_padrao() / 'alfa' / 'relatorio.md').exists()

    with caplog.at_level(logging.INFO):
        assert main([]) == 0
    assert 'sem mudanças' in caplog.text


def test_sem_pasta_de_provas_explica_onde_e_da_a_dica_sem_traceback(projeto, capsys):
    assert main([]) == 1

    erro = capsys.readouterr().err
    linhas = [linha for linha in erro.splitlines() if linha.strip()]
    assert len(linhas) <= 2
    assert str(projeto / 'provas') in linhas[0]
    assert linhas[1].startswith('dica:')
    assert 'Traceback' not in erro


def test_excecao_inesperada_mostra_o_caminho_do_log(projeto, home_isolada, capsys, monkeypatch):
    criar_concurso(projeto / 'provas', 'alfa', config('alfa'), ARQUIVOS)

    def quebrar(*_args, **_kwargs):
        raise KeyError('inesperado')

    monkeypatch.setattr('concursos.cli.comandos.analisar_todos', quebrar)

    assert main([]) != 0

    erro = capsys.readouterr().err
    assert 'Traceback' not in erro
    pasta_logs = home_isolada / 'logs'
    assert str(pasta_logs) in erro
    log = next(pasta_logs.glob('*.log')).read_text(encoding='utf-8')
    assert 'Traceback' in log and 'inesperado' in log


def test_dry_run_lista_os_concursos_e_nao_grava_nada(projeto, home_isolada, capsys):
    criar_concurso(projeto / 'provas', 'alfa', config('alfa'), ARQUIVOS)
    criar_concurso(projeto / 'provas', 'beta', config('beta'), {'gabarito.txt': '1 A\n2 B\n'})

    assert main(['--dry-run']) == 0

    saida = capsys.readouterr().out
    assert 'alfa' in saida and 'analisaria' in saida
    assert 'beta' in saida and 'pularia' in saida
    assert not (projeto / 'analises').exists()
    assert not (projeto / '.concurso').exists()


def _pasta_sem_cadastro(projeto: Path) -> Path:
    pasta = projeto / 'provas' / 'novo'
    pasta.mkdir(parents=True)
    (pasta / 'gab.txt').write_text('# FGV - Gabarito definitivo\n1 A\n2 B\n', encoding='utf-8')
    (pasta / 'respostas.txt').write_text('1 A\n2 C\n', encoding='utf-8')
    return pasta


def test_add_de_pasta_com_dry_run_nao_grava(projeto, capsys):
    pasta = _pasta_sem_cadastro(projeto)

    assert main(['--dry-run', 'add', str(pasta)]) == 0

    assert not (pasta / 'concurso.yaml').exists()
    assert 'cadastraria' in capsys.readouterr().out


def test_add_de_pasta_sem_tty_nao_pergunta(projeto, monkeypatch):
    pasta = _pasta_sem_cadastro(projeto)
    monkeypatch.setattr('builtins.input', lambda *_: pytest.fail('perguntou sem TTY'))

    assert main(['add', str(pasta)]) == 0

    assert (pasta / 'concurso.yaml').exists()


def test_subcomando_analyze_aceita_o_concurso_e_force(projeto, caplog):
    criar_concurso(projeto / 'provas', 'alfa', config('alfa'), ARQUIVOS)
    criar_concurso(projeto / 'provas', 'beta', config('beta'), ARQUIVOS)
    assert main(['analyze']) == 0
    caplog.clear()

    with caplog.at_level(logging.INFO):
        assert main(['analyze', 'beta', '--force']) == 0

    analisados = {r.args[0] for r in caplog.records if r.msg == 'Analisando %s'}
    assert analisados == {'beta'}


def test_provas_e_analises_por_flag(tmp_path, projeto):
    provas, analises = tmp_path / 'outras_provas', tmp_path / 'saida'
    criar_concurso(provas, 'alfa', config('alfa'), ARQUIVOS)

    assert main(['--provas', str(provas), '--analises', str(analises)]) == 0
    assert (analises / candidato_padrao() / 'alfa' / 'relatorio.md').exists()


def test_status_novo_lista_os_concursos(projeto, capsys):
    criar_concurso(projeto / 'provas', 'alfa', config('alfa'), ARQUIVOS)

    assert main(['status']) == 0
    assert 'alfa' in capsys.readouterr().out


def test_opcao_desconhecida_e_erro_de_uso_sem_traceback(projeto, capsys):
    assert main(['--nao-existe']) == 2
    assert 'Traceback' not in capsys.readouterr().err


def test_contexto_usa_concurso_home_e_a_pasta_atual(tmp_path):
    contexto = resolver_contexto(cwd=tmp_path, ambiente={'CONCURSO_HOME': str(tmp_path / 'h')})

    assert contexto.home == tmp_path / 'h'
    assert contexto.logs == tmp_path / 'h' / 'logs'
    assert contexto.projeto == tmp_path / '.concurso'
    assert contexto.provas == tmp_path / 'provas'
    assert contexto.analises == tmp_path / 'analises'


def test_contexto_sem_variavel_usa_a_pasta_do_usuario(tmp_path):
    contexto = resolver_contexto(cwd=tmp_path, ambiente={}, data_dir=tmp_path / 'dados')

    assert contexto.home == Path.home() / '.concurso'
    assert contexto.projeto == tmp_path / 'dados'


def test_comando_legado_continua_e_avisa_que_esta_obsoleto(projeto, caplog):
    criar_concurso(projeto / 'provas', 'alfa', config('alfa'), ARQUIVOS)

    with caplog.at_level(logging.WARNING):
        assert main(['status', '--provas', str(projeto / 'provas')]) == 0
        assert main(['analisar', '--provas', 'provas', '--analises', 'analises']) == 0

    avisos = [r.getMessage() for r in caplog.records if 'obsoleto' in r.getMessage()]
    assert any('analyze' in aviso for aviso in avisos)
    assert (projeto / 'analises' / 'alfa' / 'relatorio.md').exists()


def test_executavel_concursos_avisa_uma_vez(projeto, capsys, monkeypatch):
    criar_concurso(projeto / 'provas', 'alfa', config('alfa'), ARQUIVOS)
    monkeypatch.setattr('sys.argv', ['concursos', 'status'])

    with pytest.raises(SystemExit) as saida:
        executar_legado()

    assert saida.value.code == 0
    assert capsys.readouterr().err.count('obsoleto') == 1
