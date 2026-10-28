from concursos.gabarito import Secao, selecionar_secao
from concursos.texto import abreviar, juntar_linhas, normalizar


def test_normalizar_tira_acento_espacos_extras_e_unifica_tracos_em_maiusculas():
    assert normalizar('  Analista –  Tecnologia — da Informação ') == 'ANALISTA - TECNOLOGIA - DA INFORMACAO'


def test_secao_do_gabarito_casa_cargo_com_caixa_acento_e_traco_diferentes():
    secoes = [Secao('CARGO 2: ANALISTA – TI', '1', []), Secao('CARGO 3: TÉCNICO', '1', [])]

    assert selecionar_secao(secoes, 'cargo 3: tecnico', 'Tipo 1', 'g.pdf') is secoes[1]


def test_abreviar_corta_no_ultimo_espaco_antes_do_limite_e_marca_o_corte():
    assert abreviar('Ameaças e vulnerabilidades em aplicações', 20) == 'Ameaças e…'
    assert len(abreviar('Ameaças e vulnerabilidades em aplicações', 20)) <= 20


def test_abreviar_nao_mexe_no_texto_que_cabe_e_corta_palavra_unica_longa():
    assert abreviar('Redes de computadores', 21) == 'Redes de computadores'
    assert abreviar('Desoxirribonucleico', 10) == 'Desoxirri…'


def test_abreviar_nao_deixa_pontuacao_antes_das_reticencias():
    assert abreviar('Segurança: injection, XSS e CSRF', 24) == 'Segurança: injection…'


def test_juntar_linhas_desfaz_hifenizacao_na_quebra_e_colapsa_espacos():
    linhas = ['Modelagem de da-  ', '  dos relacional   e', 'Lei Anti-', 'Corrupção']

    assert juntar_linhas(linhas) == 'Modelagem de dados relacional e Lei Anti- Corrupção'
