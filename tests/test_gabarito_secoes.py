import pytest

from concursos.gabarito import (
    GabaritoInvalidoError,
    Secao,
    ler_secoes_fgv,
    ler_secoes_lista,
    selecionar_secao,
)

LINHAS_70 = """1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20
B C C D A E E D B A C C C C D D D B B E
21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40
C C E A B B E C E A B B A B C D A C A B
41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60
E A C B D A C B C D D A E A D D C E E B
61 62 63 64 65 66 67 68 69 70
A A E B C E C D A B"""

TRECHO_FGV = f"""Agência Brasileira de Apoio à Gestão do SUS
PROCESSO SELETIVO SIMPLIFICADO
Gabaritos Definitivos da prova aplicada no dia 12/10/2025
Auxiliar de Gestão - 1 - Turno Tarde
{LINHAS_70}
Analista de Gestão Tecnologia da Informação - 1 - Turno Tarde
1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20
B E A C D C E A C A D A B B E A D C E B
21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40
A E B E A D E B C A E A A B E B B E B C
Página 1 de 13
Agência Brasileira de Apoio à Gestão do SUS
PROCESSO SELETIVO SIMPLIFICADO
Gabaritos Definitivos da prova aplicada no dia 12/10/2025
41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60
E A C B D A C B C D D A E A D D C E E B
61 62 63 64 65 66 67 68 69 70
A A E B C E C D * B
* Questão anulada
"""

TRECHO_CPNU = """Bloco Temático 3 - Ciências, Dados e Tecnologia - TIPO 2
1 2 3 4 5
B C D B A
* Questão anulada
Bloco Temático 3 - Ciências, Dados e Tecnologia - TIPO 3
1 2 3 4 5
C * E D E
"""

TRECHO_CRECI = """GABARITO OFICIAL DEFINITIVO
APLICAÇÃO: 1º/2/2026
100 - PAS - AGENTE FISCAL
01: A 02: E 03: B 04: A 05: C
101 - PAS - ANALISTA DE TI
01: A 02: E 03: B 04: A 05: *
"""

TRECHO_SENAPPEN = """GABARITO OFICIAL DEFINITIVO
501 - ANALISTA TÉCNICO EM DIREITO
PROVA A
01: D 02: A 03: A 04: C 05: X
PROVA B
01: A 02: D 03: D 04: A 05: X
502 - ANALISTA TÉCNICO EM ADMINISTRAÇÃO
PROVA A
01: D 02: A 03: A 04: C 05: D
"""


def resumo(secoes: list[Secao]) -> list[tuple[str, str | None, int]]:
    return [(s.cargo, s.tipo, len(s.itens)) for s in secoes]


def test_fgv_secoes_por_cargo_e_tipo_continuam_apos_quebra_de_pagina():
    secoes = ler_secoes_fgv(TRECHO_FGV, 'gabarito.pdf')
    assert resumo(secoes) == [
        ('Auxiliar de Gestão', '1', 70),
        ('Analista de Gestão Tecnologia da Informação', '1', 70),
    ]
    ultima = secoes[1].itens
    assert ultima[0].resposta == 'B'
    assert ultima[68].anulada
    assert ultima[69].resposta == 'B'


def test_fgv_cabecalho_com_tipo_explicito_do_cpnu():
    secoes = ler_secoes_fgv(TRECHO_CPNU, 'gabarito.pdf')
    assert resumo(secoes) == [
        ('Bloco Temático 3 - Ciências, Dados e Tecnologia', '2', 5),
        ('Bloco Temático 3 - Ciências, Dados e Tecnologia', '3', 5),
    ]
    assert secoes[1].itens[1].anulada


def test_lista_dois_pontos_por_cargo_sem_tipo():
    secoes = ler_secoes_lista(TRECHO_CRECI, 'gabarito.pdf')
    assert resumo(secoes) == [('100 - PAS - AGENTE FISCAL', None, 5), ('101 - PAS - ANALISTA DE TI', None, 5)]
    assert secoes[1].itens[4].anulada


def test_lista_dois_pontos_por_cargo_e_prova():
    secoes = ler_secoes_lista(TRECHO_SENAPPEN, 'gabarito.pdf')
    assert resumo(secoes) == [
        ('501 - ANALISTA TÉCNICO EM DIREITO', 'A', 5),
        ('501 - ANALISTA TÉCNICO EM DIREITO', 'B', 5),
        ('502 - ANALISTA TÉCNICO EM ADMINISTRAÇÃO', 'A', 5),
    ]
    assert secoes[1].itens[0].resposta == 'A'


def test_seleciona_secao_ignorando_caixa_acentos_e_espacos():
    secoes = ler_secoes_lista(TRECHO_SENAPPEN, 'gabarito.pdf')
    secao = selecionar_secao(secoes, '501 - analista tecnico  em direito', 'b', 'gabarito.pdf')
    assert secao.itens[1].resposta == 'D'


def test_secao_inexistente_lista_as_disponiveis():
    secoes = ler_secoes_fgv(TRECHO_CPNU, 'gabarito.pdf')
    with pytest.raises(GabaritoInvalidoError, match=r'TIPO 4.*disponíveis.*Tecnologia \(tipo 2\)'):
        selecionar_secao(secoes, 'Bloco Temático 3 - Ciências, Dados e Tecnologia', 'TIPO 4', 'gabarito.pdf')
