import pandas as pd
from consolidado_sintetico import concurso, consolidado

from concursos.analytics.evolucao import simular_cenario
from concursos.analytics.insights import (
    calcular_achados,
    descrever_simulacao,
    desempate_por_concurso,
    diferencas,
    gravar_relatorio_evolucao,
    respostas,
    sem_nivel_medio,
    sensibilidade_em_markdown,
)

PT, TI = 'Português', 'TI'


def prova(nome: str, ordem: int, acertos_ti: int, escolaridade: str = 'superior') -> pd.DataFrame:
    """Português estável (metade certa, tópico Crase) e TI com `acertos_ti` de 6 (tópico Redes)."""
    return concurso(
        nome,
        ['acerto', 'erro'] * 3 + ['acerto'] * acertos_ti + ['erro'] * (6 - acertos_ti),
        ordem=ordem,
        disciplinas=[PT] * 6 + [TI] * 6,
        topicos=['Crase'] * 6 + ['Redes'] * 6,
        escolaridade=escolaridade,
    )


SUPERIOR = [prova('a', 1, 1), prova('b', 2, 2), prova('c', 3, 3), prova('d', 4, 5), prova('e', 5, 6)]
BASE = consolidado(*SUPERIOR, prova('medio', 6, 0, escolaridade='medio'))


def test_sem_nivel_medio_tira_so_os_concursos_de_nivel_medio():
    assert sorted(sem_nivel_medio(BASE)['concurso'].unique()) == ['a', 'b', 'c', 'd', 'e']


def test_achados_trazem_a_melhora_significativa_e_os_fracos():
    achados = calcular_achados(sem_nivel_medio(BASE))

    assert achados.melhoras['disciplina'].tolist() == [TI]
    assert achados.pioras['disciplina'].tolist() == [PT]
    assert set(achados.fracos['topico']) == {'Crase', 'Redes'}
    assert achados.correlacao_geral.pontos == 5


def test_respostas_as_quatro_perguntas_com_numeros():
    textos = respostas(calcular_achados(sem_nivel_medio(BASE)))

    assert len(textos) == 4
    assert 'TI' in textos[0] and 'p = ' in textos[0] and 'n = ' in textos[0]
    assert 'Crase' in textos[1] and 'n = ' in textos[1]
    assert 'ρ = ' in textos[2] and 'p = ' in textos[2]
    assert 'não muda' in textos[3]


def test_sem_melhora_significativa_a_resposta_diz_nenhuma():
    plana = consolidado(prova('a', 1, 3), prova('b', 2, 3), prova('c', 3, 3))

    assert respostas(calcular_achados(plana))[0].startswith('Nenhuma disciplina melhorou')


def test_ranking_que_muda_entre_bruto_e_ajustado_vira_achado():
    cebraspe = concurso('cebraspe', ['acerto'] * 3 + ['erro'], ordem=1)
    fgv = concurso('fgv', ['acerto'] * 7 + ['erro'] * 3, formato='multipla_escolha', ordem=2)

    texto = respostas(calcular_achados(consolidado(cebraspe, fgv)))[3]

    assert 'muda' in texto and 'não muda' not in texto
    assert 'fgv: 2º no bruto' in texto


def test_diferencas_sem_o_nivel_medio_sao_declaradas():
    textos = diferencas(calcular_achados(BASE), calcular_achados(sem_nivel_medio(BASE)))

    assert any(TI in texto for texto in textos)
    assert all(isinstance(texto, str) for texto in textos)


def test_sensibilidade_avisa_quando_nao_ha_nivel_medio():
    base = consolidado(*SUPERIOR)

    assert (
        sensibilidade_em_markdown(base, calcular_achados(base)) == 'Nenhum concurso de nível médio na base.'
    )
    assert sensibilidade_em_markdown(BASE, calcular_achados(BASE)).startswith(
        'Os achados recalculados sem medio'
    )


def test_relatorio_traz_a_nota_final_so_dos_concursos_com_desconto_ou_pesos(tmp_path):
    base = consolidado(
        concurso('tcu', ['acerto'] * 3 + ['erro'], ordem=1, nota_corte=1.0),
        concurso('fgv', ['acerto', 'erro'], formato='multipla_escolha', ordem=2),
    )

    texto = gravar_relatorio_evolucao(base, tmp_path).read_text(encoding='utf-8')

    secao = texto.split('## Nota final pela regra do edital', 1)[1].split('\n## ', 1)[0]
    assert '- tcu: 2 de 4 pontos, nota de corte 1 (atinge o corte).' in secao
    assert 'fgv' not in secao


def test_relatorio_com_as_tres_imagens_e_as_quatro_respostas(tmp_path):
    relatorio = gravar_relatorio_evolucao(BASE, tmp_path)

    texto = relatorio.read_text(encoding='utf-8')
    for numero in range(1, 5):
        assert f'## {numero}.' in texto
    assert 'Sensibilidade' in texto
    imagens = ['evolucao_zscore.png', 'heatmap_topicos.png', 'painel_correcao.png']
    for imagem in imagens:
        assert f']({imagem})' in texto
        assert (tmp_path / imagem).exists()


def test_simulacao_e_rotulada_como_estimativa_sem_linguagem_de_previsao():
    prova = concurso('cd_25', ['acerto'] * 5 + ['erro'] * 5, disciplinas=['Dados'] * 10)
    cortes = {'cd_25': [{'escopo': 'conjunto', 'valor': 2, 'unidade': 'pontos', 'bloco': None}]}
    simulacao = simular_cenario(consolidado(prova), cortes, 'Dados', 30)

    texto = descrever_simulacao(simulacao, 'Dados', 30)

    assert texto.startswith('**Estimativa')
    assert '+30 p.p. em Dados' in texto
    assert 'nota 0 → 6' in texto
    for previsao in ('vou passar', 'serei aprovado', 'aprovad', 'colocação estimada'):
        assert previsao not in texto.lower()


def test_desempate_sai_na_ordem_do_edital_sem_calculo():
    regras = {
        'tcu_25': {
            'metadados': [{'chave': 'desempate', 'valor': ['tiver mais de 60 anos', 'maior nota em P2']}]
        },
        'agsus': {'metadados': [{'chave': 'desempate', 'valor': None}]},
    }

    tabela = desempate_por_concurso(regras)

    assert tabela.to_dict('records') == [
        {'concurso': 'tcu_25', 'prioridade': 1, 'criterio': 'tiver mais de 60 anos'},
        {'concurso': 'tcu_25', 'prioridade': 2, 'criterio': 'maior nota em P2'},
    ]
    assert desempate_por_concurso(regras, concurso_alvo='agsus').empty
