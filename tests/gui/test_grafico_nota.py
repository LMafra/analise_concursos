from concursos.aplicacao.resultados import PontoDeNota
from concursos.gui.componentes.resumo_visual import (
    _escala,
    _faixa_acima_do_corte,
    _frase_da_serie,
    _xs_do_grafico,
    svg_nota_corte,
)
from concursos.gui.paginas import configuracoes as pagina_config
from concursos.gui.paginas.encontrar import prazo, selo_do_prazo
from concursos.gui.tema import Tom
from concursos.integracoes.pci_mcp import DatasInscricao


def _serie() -> tuple[PontoDeNota, ...]:
    return (
        PontoDeNota('alfa', 1, 60.0, 70.0, False),
        PontoDeNota('beta', 2, 75.0, 68.0, True),
    )


def test_grafico_liga_a_nota_e_o_corte() -> None:
    svg = svg_nota_corte(_serie(), atual='beta')

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


def test_grafico_de_uma_prova_centraliza_o_ponto() -> None:
    svg = svg_nota_corte((PontoDeNota('unica', 1, 80.0, None, None),))

    assert '<polyline' in svg
    assert _xs_do_grafico(1, 0, 100) == [50.0]


def test_faixa_some_sem_corte() -> None:
    assert _faixa_acima_do_corte(0, 10, 100, None, lambda v: v) == ''


def test_escala_respeita_o_intervalo() -> None:
    minimo, maximo, marcas = _escala([40.0, 60.0])
    assert minimo <= 40
    assert maximo >= 60
    assert marcas


def test_selo_do_prazo_por_dias() -> None:
    assert selo_do_prazo(DatasInscricao(fim='01/01/2027', dias_ate_fim=20))[1] is Tom.SUCESSO
    assert selo_do_prazo(DatasInscricao(fim='01/01/2027', dias_ate_fim=3))[1] is Tom.ALERTA
    assert selo_do_prazo(DatasInscricao(fim='01/01/2020', dias_ate_fim=-1))[1] is Tom.INFO
    assert selo_do_prazo(DatasInscricao(em_breve=True))[0] == 'Edital em breve'


def test_frase_da_serie_reflete_a_tendencia() -> None:
    subiu = (PontoDeNota('a', 1, 50.0, 60.0, False), PontoDeNota('b', 2, 70.0, 60.0, True))
    caiu = (PontoDeNota('a', 1, 70.0, 60.0, True), PontoDeNota('b', 2, 50.0, 60.0, False))
    estavel = (PontoDeNota('a', 1, 60.0, 60.0, True), PontoDeNota('b', 2, 60.2, 60.0, True))
    assert 'subiu' in _frase_da_serie(subiu)
    assert 'caiu' in _frase_da_serie(caiu)
    assert 'estável' in _frase_da_serie(estavel)


def test_prazo_e_meta_em_pontos() -> None:
    assert 'dia' in prazo(DatasInscricao(fim='01/01/2027', dias_ate_fim=1))
    assert 'encerradas' in prazo(DatasInscricao(fim='01/01/2020', dias_ate_fim=-2))
    assert pagina_config._pontos(0.8) == 80.0
    assert pagina_config._fmt_pontos(80.5) == '80,5'
