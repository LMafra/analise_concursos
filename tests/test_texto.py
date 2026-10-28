from concursos.gabarito import Secao, selecionar_secao
from concursos.texto import normalizar


def test_normalizar_tira_acento_espacos_extras_e_unifica_tracos_em_maiusculas():
    assert normalizar('  Analista –  Tecnologia — da Informação ') == 'ANALISTA - TECNOLOGIA - DA INFORMACAO'


def test_secao_do_gabarito_casa_cargo_com_caixa_acento_e_traco_diferentes():
    secoes = [Secao('CARGO 2: ANALISTA – TI', '1', []), Secao('CARGO 3: TÉCNICO', '1', [])]

    assert selecionar_secao(secoes, 'cargo 3: tecnico', 'Tipo 1', 'g.pdf') is secoes[1]
