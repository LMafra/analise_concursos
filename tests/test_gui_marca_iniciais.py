from concursos.gui.componentes.marca import _iniciais


def test_iniciais_de_nome_composto() -> None:
    assert _iniciais('Ana Maria Silva') == 'AS'


def test_iniciais_de_um_so_nome() -> None:
    assert _iniciais('lucas') == 'LU'


def test_iniciais_vazias() -> None:
    assert _iniciais('') == '?'
    assert _iniciais('   ') == '?'
