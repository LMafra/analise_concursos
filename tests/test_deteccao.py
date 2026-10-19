import pytest

from concursos.deteccao import Papel, classificar_texto, detectar_banca, detectar_tipo_caderno, eh_anexo
from concursos.gabarito import detectar_status

EDITAL_CEBRASPE = """ORGAO EXEMPLO
CONCURSO PÚBLICO PARA PROVIMENTO DE VAGAS E FORMAÇÃO DE CADASTRO DE RESERVA EM
CARGOS DE NÍVEL SUPERIOR
EDITAL Nº 1 – ORGAO EXEMPLO, DE 30 DE DEZEMBRO DE 2025
O Órgão Exemplo torna pública a realização de concurso público para provimento de vagas.
1 DAS DISPOSIÇÕES PRELIMINARES
1.1 O concurso público será regido por este edital e executado pelo Cebraspe.
2.1 As provas objetivas e discursiva serão aplicadas na data provável.
"""

ANEXO_CPNU = """1
ESCOLA NACIONAL DE ADMINISTRAÇÃO PÚBLICA
CONCURSO PÚBLICO NACIONAL UNIFICADO 2
EDITAL ENAP Nº 114/2025 – CONCURSO PÚBLICO NACIONAL UNIFICADO, 30 DE JUNHO DE 2025
ANEXO III
BLOCO TEMÁTICO 3 – CIÊNCIAS, DADOS E TECNOLOGIA
Neste anexo estão reunidas as disposições específicas que regem o bloco temático 3.
"""

EDITAL_CITANDO_ANEXO = """1
ESCOLA NACIONAL DE ADMINISTRAÇÃO PÚBLICA
EDITAL ENAP Nº 114/2025 – CONCURSO PÚBLICO NACIONAL UNIFICADO, 30 DE JUNHO DE 2025
A PRESIDENTA DA ESCOLA NACIONAL DE ADMINISTRAÇÃO PÚBLICA, no uso da atribuição que lhe confere o
art. 19, Anexo I, do Decreto n.º 10.369, torna pública a realização de concurso público.
"""

FOLHA_IMPRESSA_DO_NAVEGADOR = """19/10/2026, 19:17 Texto.aspx (2480×2864)
https://security.cebraspe.org.br/ORGAO/Recursos/Objetiva/GabaritoDefinitivo_F94/Texto.aspx?im=35a… 1/1"""

CADERNO_CEBRASPE = """CEBRASPE – ORGAO EXEMPLO – Edital: 2025
-- CONHECIMENTOS ESPECÍFICOS --
Acerca do poder constituinte, julgue os itens a seguir.
91 O poder constituinte originário é qualificado como incondicionado.
"""

CADERNO_SENAPPEN = """501 PROVA
A
PROCESSO SELETIVO SIMPLIFICADO
SECRETARIA EXEMPLO
EDITAL N.º 01/2024
ANALISTA TÉCNICO EM DIREITO
Leia atentamente as instruções abaixo:
a) Este caderno, com 60 (sessenta) questões da prova objetiva
"""

GABARITO_CEBRASPE = """ORGAO EXEMPLO
EDITAL Nº 1 – ORGAO EXEMPLO, DE 30 DE DEZEMBRO DE 2025
Aplicação: 08/03/2026
CARGO 2: TÉCNICO LEGISLATIVO – ESPECIALIDADE: ASSISTENTE
GABARITOS OFICIAIS DEFINITIVOS
Item 91 92 93
Gabarito E C X
"""

GABARITO_PRELIMINAR_COM_RECURSO = """CONSELHO EXEMPLO
GABARITO PRELIMINAR
101 - PAS - ANALISTA DE TI
01: A 02: B
Os recursos serão analisados e o gabarito oficial definitivo será divulgado.
"""

RESULTADO = """CONSELHO EXEMPLO
EDITAL Nº 14 - CONSELHO, DE 15 DE ABRIL DE 2026
RESULTADO FINAL DO CONCURSO (RETIFICADO)
O Presidente, no uso de suas atribuições legais, torna publica a retificação do resultado final.
"""


@pytest.mark.parametrize(
    ('texto', 'paginas', 'tem_imagem', 'papel'),
    [
        (EDITAL_CEBRASPE, 48, False, Papel.EDITAL),
        (ANEXO_CPNU, 94, False, Papel.EDITAL),
        (CADERNO_CEBRASPE, 4, True, Papel.PROVA),
        (CADERNO_SENAPPEN, 77, True, Papel.PROVA),
        (GABARITO_CEBRASPE, 1, True, Papel.GABARITO),
        (GABARITO_PRELIMINAR_COM_RECURSO, 3, False, Papel.GABARITO),
        (RESULTADO, 45, True, Papel.RESULTADO),
        ('Nome: ____ CPF: ____', 1, True, Papel.FOLHA),
        (FOLHA_IMPRESSA_DO_NAVEGADOR, 1, True, Papel.FOLHA),
        ('Lista de compras: pão, leite', 1, False, Papel.DESCONHECIDO),
        (EDITAL_CITANDO_ANEXO, 120, False, Papel.EDITAL),
    ],
    ids=[
        'edital',
        'anexo',
        'caderno_cebraspe',
        'caderno_com_edital_no_cabecalho',
        'gabarito',
        'gabarito_preliminar',
        'resultado',
        'folha',
        'folha_com_url_de_gabarito',
        'desconhecido',
        'edital_que_cita_anexo',
    ],
)
def test_classifica_papel_pelo_conteudo(texto, paginas, tem_imagem, papel):
    assert classificar_texto('qualquer.pdf', texto, paginas, tem_imagem) is papel


def test_anexo_do_edital_e_reconhecido():
    assert eh_anexo(ANEXO_CPNU)
    assert not eh_anexo(EDITAL_CEBRASPE)
    assert not eh_anexo(EDITAL_CITANDO_ANEXO)


@pytest.mark.parametrize(
    ('texto', 'banca'),
    [
        ('O concurso será executado pelo Cebraspe.', 'cebraspe'),
        ('FUNDAÇÃO GETULIO VARGAS - Analista', 'fgv'),
        ('Instituto SELECON', 'selecon'),
        ('Instituto Quadrix', 'quadrix'),
        ('Nenhuma banca citada', None),
    ],
)
def test_detecta_banca(texto, banca):
    assert detectar_banca(texto) == banca


@pytest.mark.parametrize(
    ('texto', 'tipo'),
    [
        ('ANALISTA - TIPO 2 - VERDE', '2'),
        ('Caderno TIPO 01', '1'),
        (CADERNO_SENAPPEN, 'A'),
        ('501 PPRROOVVAA\nBB\nPROCESSO SELETIVO', 'B'),
        (CADERNO_CEBRASPE, None),
    ],
)
def test_detecta_tipo_do_caderno(texto, tipo):
    assert detectar_tipo_caderno(texto) == tipo


def test_status_vem_do_titulo_e_nao_do_texto_de_recurso():
    assert detectar_status(GABARITO_PRELIMINAR_COM_RECURSO) == 'preliminar'
    assert detectar_status(GABARITO_CEBRASPE) == 'definitivo'
