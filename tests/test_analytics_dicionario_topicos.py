import json

import pandas as pd
import pytest

from concursos.analytics.dicionario_topicos import (
    MAXIMO_MARCAS,
    Dicionario,
    EntradaTema,
    Questao,
    avaliar_ganho,
    carregar_dicionario,
    com_recusa,
    com_termo,
    dicionario_em_dados,
    edital_do_json,
    expandir_consulta,
    expansao_para,
    ganho_em_markdown,
    ler_dicionario,
    questoes_revisadas,
    sugerir_termos,
)
from concursos.edital import Conhecimento, Disciplina, Edital, Topico
from concursos.erros import ErroDoUsuario
from concursos.topicos import NAO_MAPEADO, sugerir_topicos

PORTUGUES = 'Língua Portuguesa'
CRASE = 'Emprego do sinal indicativo de crase'
CONCORDANCIA = 'Concordância verbal e nominal'
PONTUACAO = 'Pontuação'


def _edital() -> Edital:
    topicos = tuple(Topico(str(i), nome, nome) for i, nome in enumerate((CRASE, CONCORDANCIA, PONTUACAO), 1))
    return Edital('edital.pdf', None, (Conhecimento('Gerais', (Disciplina(PORTUGUES, topicos),)),))


def _dicionario(**extra) -> Dicionario:
    dados = {
        'versao': 1,
        'lingua_portuguesa': {
            'crase': {'termos': ['acento grave'], 'expressoes': ['à medida que']},
            'concordancia': {'nomes': [CONCORDANCIA], 'termos': ['sujeito composto']},
        },
    }
    dados.update(extra)
    return ler_dicionario(dados)


ACENTO = 'Assinale a frase em que o acento grave foi usado corretamente no período.'


def test_le_o_dicionario_e_volta_aos_mesmos_dados():
    dicionario = _dicionario()
    assert [e.marca for e in dicionario.entradas] == [
        'tema_lingua_portuguesa_crase',
        'tema_lingua_portuguesa_concordancia',
    ]
    assert ler_dicionario(dicionario_em_dados(dicionario)) == dicionario


@pytest.mark.parametrize(
    'dados',
    [
        {'lingua_portuguesa': {'crase': {'sinonimos': ['x']}}},
        {'versao': 2},
        {'lingua_portuguesa': {'crase': {'termos': ['']}}},
        {'lingua_portuguesa': {'crase': {'termos': ['um dois tres quatro cinco seis sete']}}},
        {'lingua_portuguesa': ['crase']},
    ],
)
def test_dicionario_invalido_vira_erro_do_usuario(dados):
    with pytest.raises(ErroDoUsuario):
        ler_dicionario(dados)


def test_yaml_quebrado_vira_erro_do_usuario(tmp_path):
    caminho = tmp_path / 'taxonomia_topicos.yaml'
    caminho.write_text('lingua: [', encoding='utf-8')
    with pytest.raises(ErroDoUsuario):
        carregar_dicionario(caminho)


def test_marcas_vao_so_para_os_topicos_casados_e_no_maximo_tres():
    entradas = tuple(
        EntradaTema('lingua_portuguesa', 'crase', (CRASE,), (f'termo{i}',)) for i in range(MAXIMO_MARCAS + 2)
    )
    entradas = tuple(
        EntradaTema(e.disciplina, f'crase{i}', e.nomes, e.termos) for i, e in enumerate(entradas)
    )
    expansao = expansao_para(Dicionario(entradas), [(PORTUGUES, CRASE), (PORTUGUES, PONTUACAO)])
    assert set(expansao.por_topico) == {(PORTUGUES, CRASE)}
    texto = ' '.join(f'termo{i}' for i in range(MAXIMO_MARCAS + 2))
    assert len(expansao.marcas(texto)) == MAXIMO_MARCAS
    assert expansao.marcas(texto, aceitas={'Direito Civil'}) == []
    assert expansao.documento(PORTUGUES, CRASE, CRASE).endswith('tema_lingua_portuguesa_crase4')
    assert 'termo0' not in expansao.documento(PORTUGUES, CRASE, CRASE)
    assert expansao.documento(PORTUGUES, PONTUACAO, PONTUACAO) == PONTUACAO


def test_termo_casa_so_a_palavra_inteira():
    expansao = expansao_para(_dicionario(), [(PORTUGUES, CRASE)])
    assert expansao.marcas('acento graveolente') == []
    assert expansao.marcas('O ACENTO GRAVE indica crase') == ['tema_lingua_portuguesa_crase']


def test_sem_dicionario_a_sugestao_nao_muda():
    textos = {1: ACENTO, 2: 'Quanto à concordância verbal do sujeito composto.'}
    sem = sugerir_topicos(_edital(), textos, {1: PORTUGUES})
    vazio = sugerir_topicos(_edital(), textos, {1: PORTUGUES}, Dicionario(()))
    assert {q: (s.topico, s.score) for q, s in sem.items()} == {
        q: (s.topico, s.score) for q, s in vazio.items()
    }
    assert all(s.topico_tfidf is None for s in sem.values())


def test_sinonimo_leva_ao_topico_certo_e_guarda_o_tfidf():
    sem = sugerir_topicos(_edital(), {1: ACENTO}, {1: PORTUGUES})
    com = sugerir_topicos(_edital(), {1: ACENTO}, {1: PORTUGUES}, _dicionario())
    assert sem[1].topico != CRASE
    assert com[1].topico == CRASE
    assert (com[1].topico_tfidf, com[1].score_tfidf) == (sem[1].topico, sem[1].score)


def test_disciplina_casa_pelo_nome_canonico():
    dicionario = ler_dicionario({'portugues': {'crase': {'termos': ['acento grave']}}})
    sem_canonica = expansao_para(dicionario, [(PORTUGUES, CRASE)])
    com_canonica = expansao_para(dicionario, [(PORTUGUES, CRASE)], {PORTUGUES: 'Português'})
    assert not sem_canonica.por_topico
    assert com_canonica.por_topico


def test_expandir_consulta_acrescenta_os_outros_termos_do_tema():
    assert expandir_consulta(_dicionario(), 'quando usar acento grave?') == ['à medida que']
    assert expandir_consulta(None, 'acento grave') == []


def _revisadas(concurso='c1', n=6) -> dict:
    questoes = [Questao(concurso, i, 'p1', PORTUGUES, ACENTO, CRASE) for i in range(1, n + 1)]
    return {concurso: (_edital(), questoes)}


def test_ganho_mede_antes_e_depois():
    ganho = avaliar_ganho(_revisadas(), _dicionario())
    assert (ganho.geral.n, ganho.geral.antes, ganho.geral.depois) == (6, 0, 6)
    assert ganho.geral.delta_pp == 100.0
    assert len(ganho.corrigidas) == 6 and not ganho.quebradas
    assert not ganho.alerta
    assert ganho.por_disciplina[PORTUGUES].amostra_suficiente
    texto = ganho_em_markdown(ganho)
    assert '0,0% → 100,0% (n = 6' in texto
    assert 'Atenção' not in texto


def test_ganho_nao_usa_termo_tirado_do_proprio_concurso():
    dados = dicionario_em_dados(_dicionario())
    dados['lingua_portuguesa']['crase']['origem'] = ['c1']
    ganho = avaliar_ganho(_revisadas('c1'), ler_dicionario(dados))
    assert ganho.geral.depois == ganho.geral.antes
    assert avaliar_ganho(_revisadas('c2'), ler_dicionario(dados)).geral.depois == 6


def test_alerta_quando_o_dicionario_piora():
    errado = ler_dicionario({'lingua_portuguesa': {'pontuacao': {'termos': ['acento grave']}}})
    texto = 'O acento grave indica a crase.'
    revisadas = {'c1': (_edital(), [Questao('c1', i, 'p1', PORTUGUES, texto, CRASE) for i in range(6)])}
    ganho = avaliar_ganho(revisadas, errado)
    assert ganho.quebradas
    assert ganho.alerta
    assert 'Atenção' in ganho_em_markdown(ganho)


def test_sugere_termos_repetidos_e_respeita_recusa():
    sugestoes = sugerir_termos(_revisadas(n=3))
    termos = {s.termo for s in sugestoes}
    assert 'acento grave' in termos
    assert all(s.n >= 2 for s in sugestoes)
    sugestao = next(s for s in sugestoes if s.termo == 'acento grave')
    assert sugestao.concursos == ('c1',)

    aceito = com_termo(Dicionario(()), sugestao)
    assert aceito.entradas[0].expressoes == ('acento grave',)
    assert aceito.entradas[0].origem == ('c1',)
    assert 'acento grave' not in {s.termo for s in sugerir_termos(_revisadas(n=3), aceito)}

    recusado = com_recusa(Dicionario(()), sugestao)
    assert 'acento grave' not in {s.termo for s in sugerir_termos(_revisadas(n=3), recusado)}


def test_questao_unica_nao_gera_sugestao():
    assert sugerir_termos(_revisadas(n=1)) == []


def test_questoes_revisadas_le_revisao_e_edital(tmp_path):
    provas, analises = tmp_path / 'provas', tmp_path / 'analises'
    revisao = provas / 'c1' / 'revisao' / 'questoes_revisado.csv'
    revisao.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                'questao': 1,
                'prova': 'p1',
                'disciplina_sugerida': PORTUGUES,
                'topico_sugerido': PONTUACAO,
                'score': 0.1,
                'enunciado': ACENTO,
                'disciplina': '',
                'topico': CRASE,
            },
            {
                'questao': 2,
                'prova': 'p1',
                'disciplina_sugerida': PORTUGUES,
                'topico_sugerido': PONTUACAO,
                'score': 0.1,
                'enunciado': 'x',
                'disciplina': '',
                'topico': '',
            },
        ]
    ).to_csv(revisao, index=False)
    edital = analises / 'c1' / 'edital_estruturado.json'
    edital.parent.mkdir(parents=True)
    edital.write_text(
        json.dumps(
            {
                'fonte': 'e.pdf',
                'conhecimentos': [
                    {
                        'nome': 'Gerais',
                        'disciplinas': [{'nome': PORTUGUES, 'topicos': [{'numero': '1', 'nome': CRASE}]}],
                    }
                ],
            }
        ),
        encoding='utf-8',
    )
    revisadas = questoes_revisadas(provas, analises)
    assert list(revisadas) == ['c1']
    edital_lido, questoes = revisadas['c1']
    assert edital_lido == edital_do_json(edital)
    assert [(q.questao, q.disciplina, q.revisado) for q in questoes] == [(1, PORTUGUES, CRASE)]


def test_nao_mapeado_conta_como_acerto_so_quando_igual():
    questoes = [Questao('c1', 1, 'p1', PORTUGUES, '', NAO_MAPEADO)]
    ganho = avaliar_ganho({'c1': (_edital(), questoes)}, _dicionario())
    assert ganho.geral.antes == ganho.geral.depois == 1


def test_plural_simples_casa():
    expansao = expansao_para(_dicionario(), [(PORTUGUES, CONCORDANCIA)])
    assert expansao.marcas('Os sujeitos compostos exigem plural.') == ['tema_lingua_portuguesa_concordancia']


def test_termo_que_ja_nomeia_outro_topico_deixa_o_edital_decidir():
    logica = 'Raciocínio Lógico'
    proposicoes, tabelas = 'Proposições simples e compostas', 'Tabelas-verdade'
    topicos = tuple(Topico(str(i), n, n) for i, n in enumerate((proposicoes, tabelas), 1))
    edital = Edital('e.pdf', None, (Conhecimento('Gerais', (Disciplina(logica, topicos),)),))
    dicionario = ler_dicionario(
        {'raciocinio_logico': {'proposicoes': {'termos': ['proposição', 'tabela verdade']}}}
    )
    texto = 'Considerando as proposições P e Q, o número de linhas da tabela-verdade é 4.'

    expansao = expansao_para(dicionario, [(logica, proposicoes), (logica, tabelas)])
    assert expansao.marcas(texto) == []
    assert expansao.marcas('A proposição P é falsa.') == ['tema_raciocinio_logico_proposicoes']
    sem = sugerir_topicos(edital, {1: texto}, {1: logica})
    com = sugerir_topicos(edital, {1: texto}, {1: logica}, dicionario)
    assert com[1].topico == sem[1].topico == tabelas
