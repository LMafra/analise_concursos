from concursos.aplicacao.resultados import PontoDeNota
from concursos.gui.componentes.resumo_visual import svg_nota_corte


def _pontos() -> tuple[PontoDeNota, ...]:
    return (
        PontoDeNota('alfa', 1, 60.0, 70.0, False),
        PontoDeNota('beta', 2, 75.0, 68.0, True),
    )


def test_grafico_liga_a_nota_e_o_corte() -> None:
    svg = svg_nota_corte(_pontos(), atual='beta')

    assert svg.count('<polyline') == 2
    assert '60,0' in svg
    assert '75,0' in svg
    assert 'Corte 70,0' in svg
    assert 'fill="var(--ca-sucesso-icone)"' in svg
    assert 'fill="var(--ca-erro-icone)"' in svg


def test_nome_com_sinal_nao_quebra_o_svg() -> None:
    pontos = (
        PontoDeNota('a<b', 1, 50.0, 40.0, True),
        PontoDeNota('c', 2, 55.0, 40.0, True),
    )

    svg = svg_nota_corte(pontos)

    assert 'a&lt;b' in svg
    assert 'a<b' not in svg
