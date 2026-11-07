import json

import pandas as pd
import pytest
import yaml
from conftest import criar_concurso

from concursos.aplicacao import conferencia
from concursos.config.contexto import Contexto
from concursos.erros import ErroDoUsuario
from concursos.modelo import Bloco, TipoCampo
from concursos.topicos import ARQUIVO_REVISAO, NAO_MAPEADO, gravar_revisao

CONFIRMACAO = """\
# Campos do edital que a análise não encontrou.
#
# data da prova objetiva (AAAA-MM-DD)
data_prova:
# número de alternativas por questão (2 a 10)
alternativas:
"""


@pytest.fixture
def contexto(tmp_path) -> Contexto:
    contexto = Contexto(
        raiz=tmp_path,
        home=tmp_path / 'home',
        projeto=tmp_path / '.concurso',
        provas=tmp_path / 'provas',
        analises=tmp_path / 'analises',
    )
    criar_concurso(
        contexto.provas,
        'tcu',
        {'nome': 'tcu', 'banca': 'fgv', 'formato': 'multipla_escolha', 'pontuacao': 'simples', 'provas': {}},
        {},
    )
    return contexto


@pytest.fixture
def revisao(contexto):
    caminho = contexto.provas / 'tcu' / ARQUIVO_REVISAO
    gravar_revisao(
        caminho,
        [
            {
                'questao': 1,
                'prova': 'unica',
                'disciplina_sugerida': 'Português',
                'topico_sugerido': 'Crase',
                'score': 0.4,
                'enunciado': 'Assinale a crase.',
            },
            {
                'questao': 2,
                'prova': 'unica',
                'disciplina_sugerida': 'Português',
                'topico_sugerido': NAO_MAPEADO,
                'score': 0.0,
                'enunciado': 'Sobre o texto, é correto.',
            },
            {
                'questao': 3,
                'prova': 'unica',
                'disciplina_sugerida': 'Direito',
                'topico_sugerido': 'Licitação',
                'score': 0.01,
                'enunciado': 'A licitação é.',
            },
        ],
    )
    return caminho


def test_topicos_pendentes_sao_os_sem_sugestao_confiavel(contexto, revisao):
    linhas = conferencia.topicos_para_conferir(contexto, 'tcu')

    assert [linha.questao for linha in linhas if linha.pendente] == [2, 3]
    assert conferencia.pendencias(contexto, 'tcu').topicos == 2


def test_gravar_topicos_preserva_colunas_e_as_linhas_nao_editadas(contexto, revisao):
    antes = pd.read_csv(revisao, dtype=str, keep_default_na=False)

    conferencia.gravar_topicos(
        contexto,
        'tcu',
        {(2, 'unica'): conferencia.OpcaoTopico('Português', 'Interpretação'), (3, 'unica'): None},
    )

    depois = pd.read_csv(revisao, dtype=str, keep_default_na=False)
    assert list(depois.columns) == list(antes.columns)
    assert depois.loc[0].tolist() == antes.loc[0].tolist()
    assert depois.loc[1, ['disciplina', 'topico']].tolist() == ['Português', 'Interpretação']
    assert depois.loc[2, ['disciplina', 'topico']].tolist() == ['', NAO_MAPEADO]
    assert conferencia.pendencias(contexto, 'tcu').topicos == 0


def test_gravar_de_novo_o_mesmo_nao_reescreve(contexto, revisao):
    escolha = {(2, 'unica'): conferencia.OpcaoTopico('Português', 'Interpretação')}
    assert conferencia.gravar_topicos(contexto, 'tcu', escolha)
    assert not conferencia.gravar_topicos(contexto, 'tcu', escolha)


def test_opcoes_de_topico_vem_do_edital_estruturado(contexto, revisao):
    pasta = contexto.analises / 'ana' / 'tcu'
    pasta.mkdir(parents=True)
    edital = {
        'conhecimentos': [
            {
                'nome': 'Gerais',
                'disciplinas': [{'nome': 'Português', 'topicos': [{'nome': 'Crase'}, {'nome': 'Regência'}]}],
            }
        ]
    }
    (pasta / 'edital_estruturado.json').write_text(json.dumps(edital), encoding='utf-8')

    opcoes = conferencia.opcoes_de_topico(contexto, 'tcu')

    assert [opcao.rotulo for opcao in opcoes] == ['Português — Crase', 'Português — Regência']


def test_opcoes_de_topico_sem_edital_usa_as_sugestoes(contexto, revisao):
    assert [o.topico for o in conferencia.opcoes_de_topico(contexto, 'tcu')] == ['Crase', 'Licitação']


def test_concurso_sem_revisao_nao_tem_topicos(contexto):
    assert conferencia.topicos_para_conferir(contexto, 'tcu') == []
    with pytest.raises(ErroDoUsuario):
        conferencia.gravar_topicos(contexto, 'tcu', {})


def test_concurso_inexistente(contexto):
    with pytest.raises(ErroDoUsuario):
        conferencia.topicos_para_conferir(contexto, 'nada')


@pytest.fixture
def confirmacao(contexto):
    caminho = contexto.provas / 'tcu' / 'edital_a_confirmar.yaml'
    caminho.write_text(CONFIRMACAO, encoding='utf-8')
    return caminho


def test_campos_a_confirmar_com_tipo(contexto, confirmacao):
    campos = conferencia.campos_a_confirmar(contexto, 'tcu')

    assert [(c.campo, c.tipo, c.valor) for c in campos] == [
        ('data_prova', TipoCampo.DATA, ''),
        ('alternativas', TipoCampo.INTEIRO, ''),
    ]
    assert conferencia.pendencias(contexto, 'tcu').campos == 2


def test_gravar_campos_preserva_os_comentarios(contexto, confirmacao):
    conferencia.gravar_campos(contexto, 'tcu', {'data_prova': '15/03/2026', 'alternativas': '5'})

    texto = confirmacao.read_text(encoding='utf-8')
    assert '# data da prova objetiva (AAAA-MM-DD)\ndata_prova: 2026-03-15\n' in texto
    assert 'alternativas: 5\n' in texto
    assert [c.valor for c in conferencia.campos_a_confirmar(contexto, 'tcu')] == ['2026-03-15', '5']
    assert conferencia.pendencias(contexto, 'tcu').campos == 0


@pytest.mark.parametrize(
    ('campo', 'texto'),
    [('data_prova', '31/02/2026'), ('data_prova', 'amanhã'), ('alternativas', '1'), ('alternativas', '4,5')],
)
def test_campo_invalido_nao_grava(contexto, confirmacao, campo, texto):
    with pytest.raises(ErroDoUsuario):
        conferencia.gravar_campos(contexto, 'tcu', {campo: texto})
    assert confirmacao.read_text(encoding='utf-8') == CONFIRMACAO


def test_numero_aceita_virgula():
    assert conferencia.validar_campo('fator_penalidade', '0,25') == 0.25
    assert conferencia.validar_campo('nota_corte', '') is None


def test_juntar_e_separar_disciplinas(contexto):
    questoes = contexto.analises / 'ana' / 'tcu' / 'questoes.csv'
    questoes.parent.mkdir(parents=True)
    pd.DataFrame({'disciplina': ['Português', 'Língua Portuguesa', 'Direito Constitucional']}).to_csv(
        questoes, index=False
    )

    assert conferencia.taxonomia(contexto).soltas == [
        'Direito Constitucional',
        'Língua Portuguesa',
        'Português',
    ]

    conferencia.juntar_disciplinas(
        contexto, ['Português', 'Língua Portuguesa'], 'Língua Portuguesa', Bloco.GERAL
    )

    atual = conferencia.taxonomia(contexto)
    assert atual.grupos == [conferencia.GrupoDisciplinas('Língua Portuguesa', Bloco.GERAL, ('Português',))]
    assert atual.soltas == ['Direito Constitucional']
    dados = yaml.safe_load(contexto.taxonomia.read_text(encoding='utf-8'))
    assert dados == {'Língua Portuguesa': {'bloco': 'geral', 'nomes': ['Português']}}

    conferencia.separar_disciplina(contexto, 'Língua Portuguesa')
    assert conferencia.taxonomia(contexto).grupos == []


def test_nome_em_duas_disciplinas_e_recusado(contexto):
    with pytest.raises(ErroDoUsuario):
        conferencia.gravar_taxonomia(
            contexto,
            [
                conferencia.GrupoDisciplinas('A', Bloco.GERAL, ('X',)),
                conferencia.GrupoDisciplinas('B', Bloco.GERAL, ('X',)),
            ],
        )
