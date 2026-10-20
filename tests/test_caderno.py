from concursos.caderno import faixas_por_cabecalho
from concursos.concurso_config import FaixaDisciplina

LARGURA, ALTURA = 595.0, 842.0
NEGRITO = 'BCDGEE+Calibri-Bold'


def palavra(texto: str, x: float, top: float, tamanho: float = 9.0, negrito: bool = False) -> dict:
    return {
        'text': texto,
        'x0': x,
        'top': top,
        'size': tamanho,
        'fontname': NEGRITO if negrito else 'ArialMT',
    }


def titulo(texto: str, x: float, top: float, tamanho: float = 14.0) -> list[dict]:
    palavras, cursor = [], x
    for token in texto.split():
        palavras.append(palavra(token, cursor, top, tamanho, negrito=True))
        cursor += 8 * len(token)
    return palavras


def questao(numero: str, x: float, top: float, tamanho: float = 9.0) -> dict:
    return palavra(numero, x, top, tamanho, negrito=True)


def pagina(*grupos) -> tuple[float, float, list[dict]]:
    palavras = []
    for grupo in grupos:
        palavras.extend(grupo if isinstance(grupo, list) else [grupo])
    return LARGURA, ALTURA, palavras


def test_faixas_fgv_por_cabecalhos_e_colunas():
    capa = pagina(
        titulo('A G Nalista de Estão', 43, 100, 20.0),
        questao('1', 43, 300),
        palavra('Verifique', 60, 300),
        questao('2', 43, 320),
        questao('3', 43, 340),
    )
    paginas = [
        capa,
        pagina(
            palavra('AGÊNCIA', 43, 37, 7.0),
            titulo('Conhecimentos Gerais', 43, 57),
            titulo('5', 540, 57),
            titulo('Língua Portuguesa', 43, 75),
            questao('1', 43, 90),
            palavra('Assinale', 43, 100),
            questao('2', 43, 400),
            questao('3', 312, 90),
            palavra('2019', 312, 200, negrito=True),
            titulo('Raciocínio Lógico', 312, 400),
            questao('4', 312, 420),
            palavra('9', 300, 810, 11.0, negrito=True),
        ),
        pagina(
            titulo('Conhecimentos Específicos 43', 43, 57),
            titulo('Tecnologia da Informação', 43, 75),
            questao('5', 43, 90),
            questao('6', 43, 400),
            questao('7', 312, 90),
        ),
    ]

    assert faixas_por_cabecalho(paginas, 1) == [
        FaixaDisciplina(1, 3, 'Língua Portuguesa'),
        FaixaDisciplina(4, 4, 'Raciocínio Lógico'),
        FaixaDisciplina(5, 7, 'Tecnologia da Informação'),
    ]


def test_conhecimento_sem_subtitulo_e_titulo_em_duas_linhas():
    paginas = [
        pagina(
            titulo('CONHECIMENTOS GERAIS', 43, 58),
            questao('1', 43, 90),
            questao('2', 43, 422),
            titulo('Eixo Temático 2 - Políticas Públicas de', 312, 58),
            titulo('Ciência, Tecnologia e Inovação (CT&I)', 312, 76),
            questao('3', 312, 312),
        )
    ]

    assert faixas_por_cabecalho(paginas, 1) == [
        FaixaDisciplina(1, 2, 'Conhecimentos Gerais'),
        FaixaDisciplina(
            3, 3, 'Eixo Temático 2 - Políticas Públicas de Ciência, Tecnologia e Inovação (CT&I)'
        ),
    ]


def test_selecon_numeros_com_ponto_e_titulos_do_mesmo_tamanho():
    paginas = [
        pagina(
            titulo('LÍNGUA PORTUGUESA', 86, 65, 11.0),
            questao('1.', 17, 120, 11.0),
            questao('2.', 17, 400, 11.0),
            titulo('ÉTICA NO SERVIÇO PÚBLICO', 358, 65, 11.0),
            questao('3.', 306, 88, 11.0),
        )
    ]

    assert faixas_por_cabecalho(paginas, 1) == [
        FaixaDisciplina(1, 2, 'Língua Portuguesa'),
        FaixaDisciplina(3, 3, 'Ética no Serviço Público'),
    ]


def test_caderno_sem_cabecalhos_nao_gera_faixas():
    paginas = [pagina(questao('1', 43, 90), questao('2', 43, 400))]

    assert faixas_por_cabecalho(paginas, 1) == []
