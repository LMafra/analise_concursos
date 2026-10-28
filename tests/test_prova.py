from concursos.prova import blocos_cebraspe, segmentar

CADERNO_CEBRASPE = """CEBRASPE – CONCURSO TESTE – Edital: 2025
-- CONHECIMENTOS ESPECÍFICOS --
Acerca do poder constituinte e de aspectos atinentes à
Constituição Federal de 1988 (CF), julgue os itens a seguir.
91 O poder constituinte originário é qualificado como
incondicionado e ilimitado.
92 O processo constituinte que culminou na promulgação da CF
foi marcado por intensa participação popular.
CEBRASPE – TCU/AUFC – Edital: 2025
Em relação aos direitos e às garantias fundamentais previstos na
CF, considerada a jurisprudência do STF, julgue os itens que se
seguem.
93 A licença-paternidade é direito social previsto expressamente
no texto constitucional.
94 O direito de greve é vedado aos servidores da segurança pública.
Texto CE1A1
Bancos de dados orientados a documentos armazenam registros
flexíveis.
Considerando o texto CE1A1, julgue o item a seguir.
95 O MongoDB é um banco de dados NoSQL orientado a documentos.
"""

CADERNO_FGV = """Conhecimentos Gerais 5
Língua Portuguesa
1
Assinale a opção em que o gerúndio está adequado.
(A) Ele rolou pela escada.
(B) O carro se chocou.
2
Observe o seguinte raciocínio.
(A) a premissa não ser verdadeira.
2019 foi um ano atípico.
3
Assinale a frase correta.
"""

CADERNO_SELECON = """LÍNGUA PORTUGUESA
1. “O primeiro-ministro fez campanha a favor desta lei” (4º parágrafo).
A) “esta lei”
2. Segundo o Manual de Redação, a redação oficial é:
A) o modo de redigir atos normativos
"""


def test_cebraspe_agrupa_itens_por_bloco_de_comando():
    blocos = blocos_cebraspe(CADERNO_CEBRASPE, range(91, 96))

    assert [sorted(b.itens) for b in blocos] == [[91, 92], [93, 94], [95]]
    assert blocos[0].comando.startswith('Acerca do poder constituinte')
    assert blocos[1].comando.startswith('Em relação aos direitos')
    assert blocos[1].comando.endswith('julgue os itens que se seguem.')
    assert blocos[2].comando == 'Considerando o texto CE1A1, julgue o item a seguir.'
    assert (
        blocos[0].itens[92]
        == 'O processo constituinte que culminou na promulgação da CF foi marcado por intensa participação popular.'
    )
    assert 'Texto CE1A1' not in blocos[1].itens[94]


def test_texto_do_item_cebraspe_inclui_o_comando_do_bloco():
    textos = segmentar(CADERNO_CEBRASPE, range(91, 96), por_itens=True)

    assert textos[93].startswith('Em relação aos direitos')
    assert textos[93].endswith('previsto expressamente no texto constitucional.')


def test_fgv_numero_isolado_na_linha():
    textos = segmentar(CADERNO_FGV, range(1, 4), por_itens=False)

    assert sorted(textos) == [1, 2, 3]
    assert textos[1].startswith('Assinale a opção em que o gerúndio')
    assert '2019 foi um ano atípico.' in textos[2]


def test_selecon_numero_com_ponto():
    textos = segmentar(CADERNO_SELECON, range(1, 3), por_itens=False)

    assert textos[2].startswith('Segundo o Manual de Redação')
