import pytest

from concursos.edital import EditalNaoEstruturadoError, estruturar_edital

RODAPE = 'Edital nº 1 – Concurso Teste – página'

PAGINAS = [
    f"""EDITAL Nº 1 – CONCURSO PÚBLICO
14 DOS OBJETOS DE AVALIAÇÃO (HABILIDADES E CONHECIMENTOS)
14.1 HABILIDADES
14.1.1 Os itens das provas poderão avaliar habilidades além do conhecimento memorizado.
14.2 CONHECIMENTOS
14.2.1 Nas provas, serão avaliados conhecimentos conforme descritos a seguir.
14.2.2 CONHECIMENTOS GERAIS
LÍNGUA PORTUGUESA: 1 Compreensão e interpretação de textos. 2 Domínio da ortografia. 2.1 Emprego
da crase. 3 Reescrita de frases.
{RODAPE}
1""",
    f"""RACIOCÍNIO LÓGICO MATEMÁTICO Proposições e conectivos. Equivalências lógicas. Problemas de contagem.
NOÇÕES DE INFORMÁTICA (EXCETO PARA O CARGO 2 – ANALISTA DE TI): 1 Sistema operacional Windows. 2 Planilhas.
LÍNGUA INGLESA (SOMENTE PARA O CARGO 2 – ANALISTA DE TI): 1 Compreensão de textos.
14.2.3 CONHECIMENTOS ESPECÍFICOS
CARGO 1: ANALISTA LEGISLATIVO – ATRIBUIÇÃO: PROCESSO LEGISLATIVO
REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS E
CÓDIGO DE ÉTICA: 1 Regimento Interno. 2 Código de Ética e Decoro Parlamentar.
{RODAPE}
2""",
    f"""CARGO 2: ANALISTA DE TI – ATRIBUIÇÃO: CIÊNCIA DE DADOS
BANCO DE DADOS: 1 Modelagem relacional. 2 Bancos de dados NoSQL. 3 Lei nº 13.709/2018 aplicada a
dados. 5 Data warehouse. SAN, NAS, DAS: armazenamento em rede.
(Retificado por meio do Edital nº 2, disponível em http://www.exemplo.org.br/concurso)
ENGENHARIA DE SOFTWARE: 1. Ciclo de vida do software. 2. Metodologias ágeis. 2.1 Scrum. 2.2 Kanban.
DIREITO CIVIL: 1 Pessoas naturais. 2 Contratos.
FULANO DE TAL
Presidente da Comissão Organizadora
{RODAPE}
3""",
    f"""ANEXO I
CRONOGRAMA PREVISTO
Atividade Datas previstas
{RODAPE}
4""",
]

ANEXO_POR_EIXOS = [
    """ANEXO III
BLOCO TEMÁTICO 3 – CIÊNCIAS, DADOS E TECNOLOGIA
CONTEÚDO PROGRAMÁTICO PARA AS PROVAS
CONHECIMENTOS GERAIS
1. Desafios do estado de direito: democracia e cidadania. 1.1. Formação histórica do Estado. 2. Políticas
públicas. 2.1. Fundamentos de políticas públicas.
CONHECIMENTOS ESPECÍFICOS
EIXO TEMÁTICO 1 – CIÊNCIA, TECNOLOGIA E SOCIEDADE (CTS)
1. Fundamentos da abordagem CTS. 1.1. Paradigmas, conceitos, origens e evolução.
EIXO TEMÁTICO 4 – TECNOLOGIAS DA INFORMAÇÃO E COMUNICAÇÃO (TICs) & CIÊNCIA DE DADOS
1. Fundamentos e aplicações de TICs e ciência de dados. 2. Conceitos de Big Data e Internet das Coisas (IoT).
"""
]


EDITAL_POR_MODULOS_E_AREAS = [
    """ANEXO I - CONTEÚDO PROGRAMÁTICO
PESQUISADOR EM GEOCIÊNCIAS
Módulo I - Conhecimentos básicos
LÍNGUA INGLESA: 1. Compreensão de textos. 2. Vocabulário.
ANALISTA EM GEOCIÊNCIAS
Módulo I - Conhecimentos básicos
LÍNGUA PORTUGUESA: 1. Interpretação de texto. 2. Ortografia.
ÁREA: Administração
Módulo II - Conhecimentos Específicos
ADMINISTRAÇÃO - 1. Evolução da administração. 2. Processo administrativo.
ÁREA: Análise e Desenvolvimento de Sistemas
Módulo II - Conhecimentos Específicos:
ANÁLISE E DESENVOLVIMENTO DE SISTEMAS - I - SUPORTE TÉCNICO: 1 Sistemas operacionais. 2 Redes.
II - BANCO DE DADOS: 1 Modelagem relacional. 2 Linguagem SQL.
TÉCNICO EM GEOCIÊNCIAS
Módulo I - Conhecimentos básicos
LÍNGUA PORTUGUESA: 1. Ortografia. 2. Crase.
"""
]


def disciplinas(edital, conhecimento: int) -> list[str]:
    return [d.nome for d in edital.conhecimentos[conhecimento].disciplinas]


def test_somente_o_cargo_configurado_e_extraido():
    edital = estruturar_edital(PAGINAS, 'Analista de TI - Ciência de Dados', 'edital.pdf')

    assert [c.nome for c in edital.conhecimentos] == ['Conhecimentos Gerais', 'Conhecimentos Específicos']
    assert disciplinas(edital, 0) == ['Língua Portuguesa', 'Raciocínio Lógico Matemático', 'Língua Inglesa']
    assert disciplinas(edital, 1) == ['Banco de Dados', 'Engenharia de Software', 'Direito Civil']


def test_topicos_numerados_agrupam_subtopicos_e_toleram_lacunas():
    edital = estruturar_edital(PAGINAS, 'Analista de TI - Ciência de Dados', 'edital.pdf')

    portugues = edital.conhecimentos[0].disciplinas[0]
    assert [t.nome for t in portugues.topicos] == [
        'Compreensão e interpretação de textos',
        'Domínio da ortografia',
        'Reescrita de frases',
    ]
    assert 'Emprego da crase' in portugues.topicos[1].descricao
    banco = edital.conhecimentos[1].disciplinas[0]
    assert [t.numero for t in banco.topicos] == ['1', '2', '3', '5']
    assert 'Retificado' not in banco.topicos[-1].descricao


def test_disciplina_sem_numeracao_vira_topicos_por_frase():
    edital = estruturar_edital(PAGINAS, 'Analista de TI - Ciência de Dados', 'edital.pdf')

    raciocinio = edital.conhecimentos[0].disciplinas[1]
    assert [t.nome for t in raciocinio.topicos] == [
        'Proposições e conectivos',
        'Equivalências lógicas',
        'Problemas de contagem',
    ]


def test_restricoes_por_cargo_nas_disciplinas_gerais():
    edital = estruturar_edital(PAGINAS, 'Analista Legislativo', 'edital.pdf')

    assert disciplinas(edital, 0) == [
        'Língua Portuguesa',
        'Raciocínio Lógico Matemático',
        'Noções de Informática',
    ]
    assert disciplinas(edital, 1) == ['Regimento Interno da Câmara dos Deputados e Código de Ética']


def test_edital_com_varios_cargos_exige_cargo_configurado():
    with pytest.raises(EditalNaoEstruturadoError, match='CARGO 1: ANALISTA LEGISLATIVO'):
        estruturar_edital(PAGINAS, None, 'edital.pdf')


TOPICO_LONGO = (
    'Ameaças e vulnerabilidades em aplicações: injection (SQL, LDAP), cross-site scripting (XSS), quebra de '
    'autenticação e gerenciamento de sessão, referência insegura a objetos, cross-site request forgery'
)


def test_nome_de_topico_longo_fica_inteiro():
    paginas = [ANEXO_POR_EIXOS[0].replace('Conceitos de Big Data e Internet das Coisas (IoT)', TOPICO_LONGO)]

    edital = estruturar_edital(paginas, 'Bloco Temático 3 - Ciências, Dados e Tecnologia', 'anexo.pdf')

    assert edital.conhecimentos[1].disciplinas[1].topicos[1].nome == TOPICO_LONGO


def test_anexo_por_eixos_usa_eixos_como_disciplinas():
    edital = estruturar_edital(
        ANEXO_POR_EIXOS, 'Bloco Temático 3 - Ciências, Dados e Tecnologia', 'anexo.pdf'
    )

    assert disciplinas(edital, 0) == ['Conhecimentos Gerais']
    assert [t.nome for t in edital.conhecimentos[0].disciplinas[0].topicos] == [
        'Desafios do estado de direito: democracia e cidadania',
        'Políticas públicas',
    ]
    assert disciplinas(edital, 1) == [
        'Eixo Temático 1 – Ciência, Tecnologia e Sociedade (CTS)',
        'Eixo Temático 4 – Tecnologias da Informação e Comunicação (TICs) & Ciência de Dados',
    ]


def test_cargo_com_areas_e_modulos():
    edital = estruturar_edital(
        EDITAL_POR_MODULOS_E_AREAS,
        'Analista em Geociências - Análise e Desenvolvimento de Sistemas',
        'edital.pdf',
    )

    assert [c.nome for c in edital.conhecimentos] == ['Conhecimentos Básicos', 'Conhecimentos Específicos']
    assert disciplinas(edital, 0) == ['Língua Portuguesa']
    assert disciplinas(edital, 1) == [
        'Análise e Desenvolvimento de Sistemas - I - Suporte Técnico',
        'II - Banco de Dados',
    ]


EDITAL_COM_TITULOS_QUEBRADOS = [
    """15 DOS OBJETOS DE AVALIAÇÃO
15.2.3 CONHECIMENTOS ESPECÍFICOS
EMPREGO 9: ANALISTA DE TECNOLOGIA DA INFORMAÇÃO – ESPECIALIDADE: CIÊNCIA DE DADOS E
INOVAÇÃO
ESTATÍSTICA: 1 Probabilidade. 2 Inferência.
EMPREGO 10: ANALISTA DE TECNOLOGIA DA INFORMAÇÃO – SUBATIVIDADE:
DESENVOLVIMENTO DE SISTEMAS
ENGENHARIA DE SOFTWARE: 1 Requisitos. 2 Testes.
BANCOS DE DADOS: 1 Modelagem. 2 SQL.
EMPREGO 11: ATUÁRIO
ATUÁRIO: 1 Matemática financeira. 2 Tábuas de mortalidade.
"""
]


def test_titulos_de_emprego_quebrados_em_duas_linhas():
    edital = estruturar_edital(
        EDITAL_COM_TITULOS_QUEBRADOS,
        'EMPREGO 10: ANALISTA DE TECNOLOGIA DA INFORMAÇÃO – SUBATIVIDADE: DESENVOLVIMENTO DE SISTEMAS',
        'edital.pdf',
    )

    assert disciplinas(edital, 0) == ['Engenharia de Software', 'Bancos de Dados']


def test_texto_sem_conteudo_programatico_gera_erro_claro():
    with pytest.raises(EditalNaoEstruturadoError, match='edital.pdf: conteúdo programático não encontrado'):
        estruturar_edital(['EDITAL Nº 1\nDas inscrições.\n'], 'Analista', 'edital.pdf')
