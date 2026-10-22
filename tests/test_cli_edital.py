import json
import logging

from conftest import analisar, criar_concurso, ler_csv
from test_edital import PAGINAS

GABARITO = '1 A\n2 B\n3 *\n4 D\n'
MANUAL = """conhecimentos:
  - nome: Conhecimentos Específicos
    disciplinas:
      - nome: Banco de Dados
        peso: 2
        topicos:
          - Modelagem relacional
          - {nome: NoSQL, descricao: Bancos de dados NoSQL orientados a documentos}
"""


def criar(provas, edital: dict, arquivos: dict[str, str]):
    config = {
        'nome': 'sintetico',
        'banca': 'fgv',
        'cargo': 'Analista de TI - Ciência de Dados',
        'formato': 'multipla_escolha',
        'pontuacao': 'simples',
        'edital': edital,
        'provas': {
            'unica': {
                'gabarito': 'gabarito.txt',
                'itens': [1, 4],
                'disciplinas': [{'inicio': 1, 'fim': 2, 'disciplina': 'Banco de Dados'}],
            }
        },
        'respostas': {'arquivo': 'respostas.txt'},
    }
    criar_concurso(
        provas, 'sintetico', config, {'gabarito.txt': GABARITO, 'respostas.txt': '1 A\n2 C\n', **arquivos}
    )


def edital_estruturado(analises) -> dict:
    return json.loads((analises / 'sintetico' / 'edital_estruturado.json').read_text(encoding='utf-8'))


def test_edital_estruturado_e_tabela_de_questoes(raizes):
    provas, analises = raizes
    criar(provas, {'arquivo': 'edital.txt'}, {'edital.txt': '\f'.join(PAGINAS)})

    assert analisar(provas, analises) == 0

    edital = edital_estruturado(analises)
    assert edital['cargo'] == 'Analista de TI - Ciência de Dados'
    especificos = edital['conhecimentos'][1]
    assert [d['nome'] for d in especificos['disciplinas']] == [
        'Banco de Dados',
        'Engenharia de Software',
        'Direito Civil',
    ]
    questoes = ler_csv(analises / 'sintetico' / 'questoes.csv')
    assert list(questoes.columns) == [
        'questao',
        'prova',
        'disciplina',
        'topico_sugerido',
        'score',
        'topico',
        'revisado',
        'gabarito',
        'anulada',
        'resposta',
        'resultado',
    ]
    assert questoes['disciplina'].tolist() == [
        'Banco de Dados',
        'Banco de Dados',
        'nao_mapeado',
        'nao_mapeado',
    ]
    assert questoes['anulada'].tolist() == [False, False, True, False]


def test_edital_manual_tem_precedencia(raizes):
    provas, analises = raizes
    criar(
        provas,
        {'arquivo': 'edital.txt', 'manual': 'edital_manual.yaml'},
        {'edital.txt': '\f'.join(PAGINAS), 'edital_manual.yaml': MANUAL},
    )

    assert analisar(provas, analises) == 0

    disciplina = edital_estruturado(analises)['conhecimentos'][0]['disciplinas'][0]
    assert disciplina['peso'] == 2
    assert [t['nome'] for t in disciplina['topicos']] == ['Modelagem relacional', 'NoSQL']


def test_edital_sem_conteudo_programatico_e_sem_manual_segue_sem_topicos_e_avisa(raizes, caplog):
    provas, analises = raizes
    criar(provas, {'arquivo': 'edital.txt'}, {'edital.txt': 'EDITAL Nº 1\nDas inscrições.\n'})

    with caplog.at_level(logging.WARNING):
        assert analisar(provas, analises) == 0

    assert 'edital.txt: conteúdo programático não encontrado' in caplog.text
    assert 'dica:' in caplog.text and 'edital.manual' in caplog.text
    assert ler_csv(analises / 'sintetico' / 'questoes.csv')['topico'].eq('nao_mapeado').all()
