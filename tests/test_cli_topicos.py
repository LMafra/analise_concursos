import pandas as pd
from conftest import analisar, criar_concurso, ler_csv
from test_edital import PAGINAS

CADERNO = """CEBRASPE – CONCURSO TESTE
Acerca de bancos de dados NoSQL, julgue os itens a seguir.
1 O MongoDB é um banco de dados NoSQL orientado a documentos.
2 Bancos NoSQL não admitem replicação.
No que se refere à ortografia oficial, julgue o item seguinte.
3 A palavra "exceção" está grafada de acordo com a ortografia oficial.
"""


def criar(provas):
    config = {
        'nome': 'sintetico',
        'banca': 'cebraspe',
        'cargo': 'Analista de TI - Ciência de Dados',
        'formato': 'certo_errado',
        'pontuacao': 'cebraspe',
        'edital': 'edital.txt',
        'provas': {'unica': {'caderno': 'prova.txt', 'gabarito': 'gabarito.txt', 'itens': [1, 3]}},
        'respostas': {'arquivo': 'respostas.txt'},
    }
    arquivos = {
        'edital.txt': '\f'.join(PAGINAS),
        'prova.txt': CADERNO,
        'gabarito.txt': '1 C\n2 E\n3 C\n',
        'respostas.txt': '1 C\n2 C\n3 C\n',
    }
    return criar_concurso(provas, 'sintetico', config, arquivos)


def topicos(analises) -> list[tuple[str, str]]:
    desempenho = ler_csv(analises / 'sintetico' / 'desempenho_por_topico.csv')
    return list(zip(desempenho['disciplina'], desempenho['topico'], strict=True))


def test_sugestao_por_similaridade_aparece_no_desempenho_e_na_revisao(raizes):
    provas, analises = raizes
    pasta = criar(provas)

    assert analisar(provas, analises) == 0

    assert topicos(analises) == [
        ('Banco de Dados', 'Bancos de dados NoSQL'),
        ('Língua Portuguesa', 'Domínio da ortografia'),
    ]
    questoes = ler_csv(analises / 'sintetico' / 'questoes.csv')
    assert {'topico_sugerido', 'score', 'topico', 'revisado'} <= set(questoes.columns)
    assert (questoes['score'] > 0).all()
    revisao = ler_csv(pasta / 'revisao' / 'questoes_revisado.csv')
    assert list(revisao.columns) == [
        'questao',
        'prova',
        'disciplina_sugerida',
        'topico_sugerido',
        'score',
        'enunciado',
        'disciplina',
        'topico',
    ]
    assert revisao['topico_sugerido'].tolist()[0] == 'Bancos de dados NoSQL'
    assert (revisao['topico'] == '').all()


def test_revisao_manual_sobrescreve_a_sugestao(raizes):
    provas, analises = raizes
    pasta = criar(provas)
    analisar(provas, analises)
    caminho = pasta / 'revisao' / 'questoes_revisado.csv'
    revisao = pd.read_csv(caminho, keep_default_na=False)
    revisao.loc[revisao['questao'] == 3, ['disciplina', 'topico']] = [
        'Língua Portuguesa',
        'Reescrita de frases',
    ]
    revisao.to_csv(caminho, index=False)

    assert analisar(provas, analises) == 0

    assert ('Língua Portuguesa', 'Reescrita de frases') in topicos(analises)
    questoes = ler_csv(analises / 'sintetico' / 'questoes.csv').set_index('questao')
    assert questoes.loc[3, ['topico', 'revisado']].tolist() == ['Reescrita de frases', True]
    assert questoes.loc[3, 'topico_sugerido'] == 'Domínio da ortografia'
