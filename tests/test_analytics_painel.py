import pandas as pd
import pytest
from consolidado_sintetico import concurso, consolidado

from concursos.analytics.evolucao import Correlacao, topicos_fracos_persistentes
from concursos.analytics.painel import (
    FAIXA_NO_LIMITE,
    FontesDasAcoes,
    Prova,
    StatusProva,
    acoes_sugeridas,
    fracos_priorizados,
    frase_de_evolucao,
    ha_amostra_por_disciplina,
    kpis,
    montar_painel,
    pontos_fortes,
    resumo_executivo,
    situacao_por_disciplina,
    status_da_prova,
    tendencia_geral,
)

LIMIAR = 0.6


@pytest.mark.parametrize(
    ('gap', 'atingido', 'esperado'),
    [
        (17.8, True, StatusProva.ACIMA),
        (FAIXA_NO_LIMITE, True, StatusProva.LIMITE),
        (-FAIXA_NO_LIMITE, False, StatusProva.LIMITE),
        (-6.7, False, StatusProva.ABAIXO),
        (None, None, StatusProva.SEM_CORTE),
        (float('nan'), None, StatusProva.SEM_CORTE),
    ],
)
def test_status_da_prova_pela_distancia_do_corte(gap, atingido, esperado):
    assert status_da_prova(gap, atingido) is esperado


def test_corte_so_por_classificacao_nao_e_calculavel():
    assert status_da_prova(None, None, corte_calculavel=False) is StatusProva.NAO_CALCULAVEL


def test_quanto_falta_na_linha_da_prova():
    assert Prova('a', 'A', 60.0, gap=-6.7, atingido=False).quanto_falta == 'faltam 6,7 p.p.'
    assert Prova('a', 'A', 80.0, gap=17.8, atingido=True).quanto_falta == '+17,8 p.p. de folga'
    assert Prova('a', 'A', 80.0).quanto_falta == ''


@pytest.mark.parametrize(
    ('rho', 'p', 'pontos', 'chave'),
    [
        (0.9, 0.01, 5, 'melhorando'),
        (-0.9, 0.01, 5, 'piorando'),
        (-0.53, 0.148, 9, 'leve_queda'),
        (0.4, 0.3, 9, 'leve_alta'),
        (0.1, 0.8, 9, 'estavel'),
        (0.99, 0.0, 2, 'indefinida'),
    ],
)
def test_tendencia_so_afirma_melhora_ou_piora_com_significancia(rho, p, pontos, chave):
    tendencia = tendencia_geral(Correlacao(rho, p, pontos))

    assert tendencia.chave == chave
    if chave.startswith('leve'):
        assert 'ainda dentro da variação normal' in tendencia.frase


def test_sem_correlacao_ainda_nao_da_para_afirmar():
    assert tendencia_geral(None).rotulo == 'Ainda não dá para afirmar'


def _tendencias(*linhas):
    return pd.DataFrame(linhas, columns=['bloco', 'disciplina', 'slope', 'p_valor', 'situacao'])


def test_situacao_por_disciplina_e_frase_de_evolucao():
    tendencias = _tendencias(
        ('geral', 'Segurança', 0.8, 0.01, 'tendência'),
        ('geral', 'Banco de Dados', 0.3, 0.4, 'tendência'),
        ('geral', 'Português', float('nan'), float('nan'), 'amostra insuficiente'),
    )

    situacoes = situacao_por_disciplina(tendencias)

    assert [(s.disciplina, s.situacao) for s in situacoes] == [
        ('Banco de Dados', 'estável'),
        ('Segurança', 'melhorando'),
    ]
    assert frase_de_evolucao(situacoes) == 'Você está melhorando em Segurança; estável no restante.'


def test_frase_de_evolucao_sem_dados_e_sem_significancia():
    assert frase_de_evolucao([]).startswith('Ainda não dá para afirmar')
    sem = situacao_por_disciplina(_tendencias(('geral', 'X', 0.3, 0.4, 'tendência')))
    assert (
        frase_de_evolucao(sem)
        == 'Nenhuma disciplina mostrou melhora ou piora consistente entre os concursos.'
    )


def _base():
    """Português forte (8 de 10 acertos em certo/errado), Direito fraco nos dois concursos."""
    disciplinas = ['Português'] * 5 + ['Direito'] * 5
    topicos = ['Crase'] * 5 + ['Atos'] * 5
    resultados = ['acerto', 'acerto', 'acerto', 'acerto', 'acerto', 'erro', 'erro', 'acerto', 'erro', 'erro']
    return consolidado(
        concurso('alfa', resultados, ordem=1, disciplinas=disciplinas, topicos=topicos),
        concurso('beta', resultados, ordem=2, disciplinas=disciplinas, topicos=topicos),
    )


def test_pontos_fortes_sao_disciplinas_acima_do_limiar_com_n_suficiente():
    fortes = pontos_fortes(_base(), LIMIAR)

    assert [(f.disciplina, f.acertos, f.n) for f in fortes] == [('Português', 10, 10)]
    assert fortes[0].frase == 'Você vai bem em Português: acertou 10 de 10; descontado o chute, 100%.'


def test_questoes_sem_disciplina_identificada_nao_sao_ponto_forte():
    sem_disciplina = consolidado(
        concurso(
            'alfa', ['acerto'] * 10, ordem=1, disciplinas=['nao_mapeado'] * 10, topicos=['nao_mapeado'] * 10
        )
    )

    assert pontos_fortes(sem_disciplina, LIMIAR) == []
    assert not ha_amostra_por_disciplina(sem_disciplina)


def test_pontos_fortes_vazio_com_amostra_pequena():
    pequeno = consolidado(concurso('alfa', ['acerto'] * 4, ordem=1))

    assert pontos_fortes(pequeno, LIMIAR) == []
    assert not ha_amostra_por_disciplina(pequeno)
    assert ha_amostra_por_disciplina(_base())


def test_fracos_agrupados_por_disciplina_com_frase_por_acertos():
    base = _base()
    grupos = fracos_priorizados(topicos_fracos_persistentes(base, LIMIAR), LIMIAR)

    assert [g.disciplina for g in grupos] == ['Direito']
    topico = grupos[0].topicos[0]
    assert (topico.acertos, topico.n) == (2, 10)
    assert topico.frase(LIMIAR) == (
        'Acertou 2 de 10 questões, menos do que acertaria chutando. '
        'Ficou abaixo em todos os concursos em que apareceu (alfa, beta).'
    )
    assert grupos[0].titulo == 'Direito: 1 tópico abaixo do esperado'


def test_topico_positivo_abaixo_do_minimo_fala_em_descontado_o_chute():
    resultados = ['acerto'] * 4 + ['erro']
    base = consolidado(
        concurso('alfa', resultados, ordem=1, topicos=['Atos'] * 5),
        concurso('beta', resultados, ordem=2, topicos=['Atos'] * 5),
    )
    grupos = fracos_priorizados(topicos_fracos_persistentes(base, 0.7), 0.7)

    assert (
        grupos[0]
        .topicos[0]
        .frase(0.7)
        .startswith(
            'Acertou 8 de 10; descontado o chute, ficou em 60%, abaixo do mínimo de 70% que você definiu.'
        )
    )


def test_prioridade_e_concursos_abaixo_vezes_o_deficit():
    fracos = pd.DataFrame(
        [
            ('A', 'leve', 3, ['x', 'y', 'z'], 10, 5, 50.0),
            ('B', 'grave', 1, ['x'], 10, 0, -60.0),
            ('A', 'grave', 2, ['x', 'y'], 10, 1, 10.0),
        ],
        columns=['disciplina', 'topico', 'concursos', 'concursos_abaixo', 'n', 'acertos', 'percentual'],
    )

    grupos = fracos_priorizados(fracos, LIMIAR)

    assert [g.disciplina for g in grupos] == ['B', 'A']
    assert grupos[0].prioridade == pytest.approx(1.2)
    assert grupos[1].prioridade == pytest.approx(1.0)
    assert [t.topico for t in grupos[1].topicos] == ['grave', 'leve']


def test_disciplina_forte_com_topico_fraco_continua_forte():
    fracos = pd.DataFrame(
        [('Português', 'Crase', 2, ['x', 'y'], 6, 1, 10.0)],
        columns=['disciplina', 'topico', 'concursos', 'concursos_abaixo', 'n', 'acertos', 'percentual'],
    )
    fortes = pontos_fortes(_base(), LIMIAR)

    grupo = fracos_priorizados(fracos, LIMIAR, fortes)[0]

    assert grupo.forte_no_geral
    assert grupo.sugestao.startswith('Mesmo indo bem no geral, 1 tópico ficou abaixo')


def _provas():
    return [
        Prova('alfa', 'Alfa 2024', 72.5, data='2024-01-01', gap=17.8, atingido=True),
        Prova('beta', 'Beta 2025', 55.0, data='2025-01-01', gap=-6.7, atingido=False),
        Prova('beta', 'Beta 2025', 61.0, variante='TI', data='2025-01-01', gap=1.0, atingido=True),
        Prova('gama', 'Gama 2025', 50.0),
    ]


def test_kpis_contam_provas_por_opcao_de_cargo():
    indicadores = kpis(_provas(), [], tendencia_geral(Correlacao(-0.53, 0.148, 9)))

    assert (indicadores.concursos, indicadores.provas) == (3, 4)
    assert (indicadores.acima, indicadores.abaixo, indicadores.no_limite, indicadores.com_corte) == (
        2,
        1,
        1,
        3,
    )
    assert indicadores.melhor.titulo == 'Alfa 2024'


def test_resumo_executivo_responde_como_estou_saindo():
    base = _base()
    grupos = fracos_priorizados(topicos_fracos_persistentes(base, LIMIAR), LIMIAR)
    indicadores = kpis(_provas(), grupos, tendencia_geral(Correlacao(-0.53, 0.148, 9)))

    assert resumo_executivo(indicadores) == (
        'Você fez 3 concursos (4 provas). Ficou acima do corte em 2 das 3 provas com corte no edital. '
        'Seu melhor desempenho foi em Alfa 2024 (72,5%). O ponto mais fraco é Direito, com 1 tópico abaixo '
        'do esperado. Leve tendência de queda, ainda dentro da variação normal.'
    )


def test_resumo_sem_concursos():
    assert resumo_executivo(kpis([], [], tendencia_geral(None))) == 'Ainda não há concursos analisados.'


def test_acoes_derivadas_dos_dados_no_maximo_cinco():
    base = _base()
    painel = montar_painel(
        _provas(),
        base,
        topicos_fracos_persistentes(base, LIMIAR),
        _tendencias(),
        None,
        LIMIAR,
        FontesDasAcoes(leituras_a_conferir=2, topicos_a_conferir=3),
    )

    textos = [acao.texto for acao in painel.acoes]
    assert textos[0] == 'Foque em Direito: 1 tópico abaixo do esperado, em 2 concursos.'
    assert textos[1] == 'Revise Atos (Direito): ficou abaixo em todos os 2 concursos em que apareceu.'
    assert (
        textos[2]
        == 'Você ficou 1,0 p.p. acima do corte em Beta 2025 (TI): pequenos ganhos já mudam o resultado.'
    )
    assert 'Confira 2 respostas da folha com leitura incerta (tela Analisar).' in textos
    assert len(textos) == 5


def test_acoes_com_links_para_as_secoes_proprias():
    from pathlib import Path

    painel = montar_painel(
        [],
        pd.DataFrame(),
        pd.DataFrame(),
        _tendencias(),
        None,
        LIMIAR,
        FontesDasAcoes(simulado_focado=Path('s.md'), recomendacoes=Path('r.md'), radar=Path('p.md')),
    )

    assert [
        (a.texto, a.link) for a in acoes_sugeridas(painel, FontesDasAcoes(simulado_focado=Path('s.md')))
    ] == [('Faça o simulado focado nos seus tópicos fracos.', '#simulado-focado')]
    assert [a.link for a in painel.acoes] == ['#simulado-focado', '#onde-estudar', '#prazos']
