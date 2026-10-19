from conftest import analisar, criar_concurso, ler_csv

CONFIG_FGV = {
    'nome': 'fgv_sintetico',
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'provas': {
        'unica': {
            'gabarito': {'arquivo': 'gabarito.txt', 'status': 'definitivo'},
            'itens': [1, 6],
            'disciplinas': [
                {'inicio': 1, 'fim': 3, 'disciplina': 'Português'},
                {'inicio': 4, 'fim': 6, 'disciplina': 'Informática'},
            ],
        }
    },
    'respostas': {'arquivo': 'respostas.txt'},
}

GABARITO_FGV = '1 A\n2 B\n3 C\n4 D\n5 E\n6 A\n'
RESPOSTAS_FGV = '1 A\n02: b\n3-D\n# questão 5 omitida\n4 -\n6 A\n'


def test_analisar_gera_respostas_extraidas_com_todas_as_questoes(raizes):
    provas, analises = raizes
    criar_concurso(
        provas, 'fgv_sintetico', CONFIG_FGV, {'gabarito.txt': GABARITO_FGV, 'respostas.txt': RESPOSTAS_FGV}
    )

    assert analisar(provas, analises) == 0

    respostas = ler_csv(analises / 'fgv_sintetico' / 'respostas_extraidas.csv')
    assert list(respostas.columns) == [
        'concurso',
        'prova',
        'questao',
        'alternativa_marcada',
        'estado',
        'confianca_ocr',
        'revisar',
        'origem',
        'arquivo',
        'pagina',
    ]
    assert respostas['questao'].tolist() == [1, 2, 3, 4, 5, 6]
    assert respostas['alternativa_marcada'].tolist() == ['A', 'B', 'D', '', '', 'A']
    assert respostas['estado'].tolist() == ['marcada', 'marcada', 'marcada', 'branco', 'branco', 'marcada']
    assert set(respostas['origem']) == {'manual'}
    assert set(respostas['confianca_ocr']) == {1.0}


def test_analisar_gera_desempenho_por_disciplina(raizes):
    provas, analises = raizes
    criar_concurso(
        provas, 'fgv_sintetico', CONFIG_FGV, {'gabarito.txt': GABARITO_FGV, 'respostas.txt': RESPOSTAS_FGV}
    )

    analisar(provas, analises)

    desempenho = ler_csv(analises / 'fgv_sintetico' / 'desempenho_por_disciplina.csv')
    assert list(desempenho.columns[:8]) == [
        'concurso',
        'prova',
        'disciplina',
        'topico',
        'total',
        'acertos',
        'erros',
        'percentual',
    ]
    por_disciplina = desempenho.set_index('disciplina')
    assert por_disciplina.loc['Português', ['total', 'acertos', 'erros']].tolist() == [3, 2, 1]
    assert por_disciplina.loc['Português', 'percentual'] == 66.67
    assert por_disciplina.loc['Informática', ['total', 'acertos', 'erros']].tolist() == [3, 1, 0]
    assert por_disciplina.loc['Informática', 'percentual'] == 33.33


def test_analisar_gera_desempenho_por_topico_e_relatorio(raizes):
    provas, analises = raizes
    criar_concurso(
        provas, 'fgv_sintetico', CONFIG_FGV, {'gabarito.txt': GABARITO_FGV, 'respostas.txt': RESPOSTAS_FGV}
    )

    analisar(provas, analises)

    saida = analises / 'fgv_sintetico'
    topicos = ler_csv(saida / 'desempenho_por_topico.csv')
    assert set(topicos['topico']) == {'nao_mapeado'}
    assert topicos['total'].sum() == 6
    relatorio = (saida / 'relatorio.md').read_text(encoding='utf-8')
    assert 'fgv_sintetico' in relatorio
    assert 'Português' in relatorio
