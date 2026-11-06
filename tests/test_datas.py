import pytest

from concursos.datas import data_br


@pytest.mark.parametrize(
    ('entrada', 'esperado'),
    [
        ('2026-11-06', '06/11/2026'),
        ('2026-11-06T19:23:00', '06/11/2026'),
        ('2026-11-06 08:00', '06/11/2026'),
        ('20/11/2026', '20/11/2026'),
        ('a definir', 'a definir'),
        (None, ''),
        ('', ''),
    ],
)
def test_data_br(entrada, esperado):
    assert data_br(entrada) == esperado
