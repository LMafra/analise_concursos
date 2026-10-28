import pandas as pd
import pytest
from conftest import analisar, criar_concurso, ler_csv
from test_edital import PAGINAS, TOPICO_LONGO

from concursos.relatorio import LIMITE_TOPICO

CADERNO = """CEBRASPE – CONCURSO TESTE
Acerca de bancos de dados NoSQL, julgue os itens a seguir.
1 O MongoDB é um banco de dados NoSQL orientado a documentos.
2 Bancos NoSQL não admitem replicação.
No que se refere à ortografia oficial, julgue o item seguinte.
3 A palavra "exceção" está grafada de acordo com a ortografia oficial.
"""


def criar(provas, paginas: list[str] = PAGINAS):
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
        'edital.txt': '\f'.join(paginas),
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


def test_nome_de_topico_longo_fica_inteiro_nos_csvs_e_abreviado_no_relatorio(raizes):
    provas, analises = raizes
    paginas = [p.replace('Bancos de dados NoSQL', f'Bancos de dados NoSQL e {TOPICO_LONGO}') for p in PAGINAS]
    criar(provas, paginas)

    assert analisar(provas, analises) == 0

    nome = f'Bancos de dados NoSQL e {TOPICO_LONGO}'
    assert ('Banco de Dados', nome) in topicos(analises)
    relatorio = (analises / 'sintetico' / 'relatorio.md').read_text(encoding='utf-8')
    assert nome not in relatorio
    abreviado = next(linha for linha in relatorio.splitlines() if 'Bancos de dados NoSQL e' in linha)
    celula = next(c.strip() for c in abreviado.split('|') if 'Bancos de dados NoSQL e' in c)
    assert celula.endswith('…') and len(celula) <= LIMITE_TOPICO


@pytest.mark.parametrize(
    ('edital', 'documento'),
    [
        ({'manual': 'edital_manual.yaml'}, {'edital_manual.yaml': 'conhecimentos: []\n'}),
        ('edital.txt', {'edital.txt': 'EDITAL DE ABERTURA\nO concurso tem prova objetiva.\n'}),
    ],
    ids=['manual_vazio', 'sem_conteudo_programatico'],
)
def test_sem_topicos_do_edital_a_revisao_sai_com_a_disciplina_das_faixas(raizes, edital, documento):
    provas, analises = raizes
    config = {
        'nome': 'sintetico',
        'banca': 'cebraspe',
        'formato': 'certo_errado',
        'pontuacao': 'cebraspe',
        'edital': edital,
        'provas': {
            'unica': {
                'caderno': 'prova.txt',
                'gabarito': 'gabarito.txt',
                'itens': [1, 3],
                'disciplinas': [{'inicio': 1, 'fim': 2, 'disciplina': 'Banco de Dados'}],
            }
        },
        'respostas': {'arquivo': 'respostas.txt'},
    }
    arquivos = {
        **documento,
        'prova.txt': CADERNO,
        'gabarito.txt': '1 C\n2 E\n3 C\n',
        'respostas.txt': '1 C\n2 C\n3 C\n',
    }
    pasta = criar_concurso(provas, 'sintetico', config, arquivos)

    assert analisar(provas, analises) == 0

    caminho = pasta / 'revisao' / 'questoes_revisado.csv'
    revisao = ler_csv(caminho)
    assert revisao['disciplina_sugerida'].tolist() == ['Banco de Dados', 'Banco de Dados', 'nao_mapeado']
    assert (revisao['topico_sugerido'] == 'nao_mapeado').all()
    assert 'MongoDB' in revisao.loc[0, 'enunciado']

    revisao.loc[revisao['questao'] == 3, ['disciplina', 'topico']] = ['Língua Portuguesa', 'Ortografia']
    revisao.to_csv(caminho, index=False)
    assert analisar(provas, analises) == 0
    assert ('Língua Portuguesa', 'Ortografia') in topicos(analises)
