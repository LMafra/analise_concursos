import sys

from concursos.cli import main


def test_gui_sem_o_extra_explica_como_instalar(monkeypatch, capsys):
    for nome in [m for m in sys.modules if m == 'concursos.gui' or m.startswith('concursos.gui.')]:
        monkeypatch.delitem(sys.modules, nome)
    monkeypatch.setitem(sys.modules, 'nicegui', None)

    assert main(['gui']) == 1

    erro = capsys.readouterr().err
    assert 'erro: A janela do app (interface gráfica) não está instalada.' in erro
    assert 'concurso-analise[gui]' in erro
    assert 'Traceback' not in erro


def test_gui_repassa_pasta_e_navegador(monkeypatch, tmp_path):
    chamadas: list[tuple] = []

    class AppFalso:
        @staticmethod
        def executar(pasta, *, navegador):
            chamadas.append((pasta, navegador))

    monkeypatch.setitem(sys.modules, 'concursos.gui.app', AppFalso)

    assert main(['gui', '--project', str(tmp_path), '--browser']) == 0
    assert chamadas == [(tmp_path, True)]
