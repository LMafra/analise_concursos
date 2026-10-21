import os
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml

from concursos.analytics import consolidado as modulo
from concursos.analytics.consolidado import (
    SchemaInvalidoError,
    avisos_do_consolidado,
    carregar_consolidado,
    construir_consolidado,
    contar_questoes,
    disciplinas_por_quantidade_de_concursos,
    n_por_topico,
    perfil_de_n,
    perfil_por_concurso,
    topicos_do_edital,
    topicos_por_n,
    validar_schema,
)
from concursos.analytics.correcao import ConfiguracaoCorrecao, FonteCorrecao, gravar_correcao
from concursos.analytics.visualizacao import resumir
from concursos.concurso_config import PesoItens
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO, Conhecimento, Disciplina, Edital, Topico
from concursos.modelo import ModeloCorrecao

LIQUIDA = ConfiguracaoCorrecao(
    ModeloCorrecao.LIQUIDA, 1.0, nota_maxima=4.0, fonte=FonteCorrecao.EDITAL, confianca=0.95
)
BRUTA = ConfiguracaoCorrecao(
    ModeloCorrecao.BRUTA, 0.0, nota_maxima=4.0, fonte=FonteCorrecao.EDITAL, confianca=0.9
)
TAXONOMIA = {
    'Língua Portuguesa': {'bloco': 'geral', 'nomes': ['Português']},
    'Tecnologia da Informação': {'bloco': 'especifico', 'nomes': ['TI']},
}


def gravar_taxonomia(caminho: Path, dados: dict) -> None:
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding='utf-8')


def preparar_raizes(tmp_path: Path) -> tuple[Path, Path, Path]:
    raizes = (tmp_path / 'provas', tmp_path / 'analises', tmp_path / 'taxonomia.yaml')
    gravar_taxonomia(raizes[2], TAXONOMIA)
    return raizes


def criar_analise(
    raizes: tuple[Path, Path, Path],
    nome: str,
    resultados: list[str],
    correcoes: list[ConfiguracaoCorrecao],
    formato: str = 'certo_errado',
    data_prova: date | None = None,
    anuladas: tuple[int, ...] = (),
    prova: str = 'unica',
    disciplinas: list[str] | None = None,
    topicos: list[str] | None = None,
    **config,
) -> None:
    provas, analises, _ = raizes
    (provas / nome).mkdir(parents=True)
    dados = {
        'nome': nome,
        'banca': 'cebraspe' if formato == 'certo_errado' else 'fgv',
        'formato': formato,
        'provas': {prova: {'gabarito': 'g.txt', 'itens': [1, len(resultados)]}},
        'respostas': {'arquivo': 'r.txt'},
        **config,
    }
    (provas / nome / 'concurso.yaml').write_text(yaml.safe_dump(dados), encoding='utf-8')
    destino = analises / nome
    destino.mkdir(parents=True)
    pd.DataFrame(
        {
            'questao': range(1, len(resultados) + 1),
            'prova': prova,
            'disciplina': disciplinas or ['Português', 'Português', *['TI'] * (len(resultados) - 2)],
            'topico_sugerido': 'x',
            'score': 0.5,
            'topico': topicos or ['Crase', 'Crase', *['Redes'] * (len(resultados) - 2)],
            'revisado': False,
            'gabarito': ['' if i + 1 in anuladas else 'C' for i in range(len(resultados))],
            'anulada': [i + 1 in anuladas for i in range(len(resultados))],
            'resposta': ['' if r == 'branco' else 'C' for r in resultados],
            'resultado': resultados,
        }
    ).to_csv(destino / 'questoes.csv', index=False)
    gravar_correcao(
        [
            replace(cfg, data_prova=data_prova, fonte_data=data_prova and FonteCorrecao.EDITAL)
            for cfg in correcoes
        ],
        destino,
    )


@pytest.fixture
def base(tmp_path) -> tuple[Path, Path, Path]:
    raizes = preparar_raizes(tmp_path)
    criar_analise(
        raizes, 'tcu', ['acerto', 'erro', 'branco', 'acerto'], [LIQUIDA], data_prova=date(2026, 2, 22)
    )
    criar_analise(
        raizes,
        'agsus',
        ['acerto', 'erro', 'acerto', 'acerto', 'erro'],
        [BRUTA],
        formato='multipla_escolha',
        data_prova=date(2025, 10, 12),
        anuladas=(4,),
        escolaridade='medio',
    )
    return raizes


def test_uma_linha_por_questao_com_metadados_do_concurso(base):
    consolidado = construir_consolidado(*base)

    assert len(consolidado) == 4 + 5 == contar_questoes(base[1])
    agsus = consolidado[consolidado['concurso'] == 'agsus'].iloc[0]
    assert (agsus['banca'], agsus['formato'], agsus['escolaridade'], agsus['nivel']) == (
        'fgv',
        'multipla_escolha',
        'medio',
        'nao_informado',
    )
    assert agsus['data_prova'] == pd.Timestamp('2025-10-12')
    assert (agsus['modelo_correcao'], agsus['fonte_correcao'], agsus['nota_maxima']) == (
        'bruta',
        'edital',
        4.0,
    )


def test_ordem_cronologica_pela_data_e_vazia_sem_data(tmp_path):
    raizes = preparar_raizes(tmp_path)
    criar_analise(raizes, 'b', ['acerto'] * 3, [LIQUIDA], data_prova=date(2026, 2, 22))
    criar_analise(raizes, 'a', ['acerto'] * 3, [LIQUIDA], data_prova=date(2025, 7, 27))
    criar_analise(raizes, 'sem_data', ['acerto'] * 3, [LIQUIDA])

    ordem = construir_consolidado(*raizes).groupby('concurso')['ordem'].first()

    assert ordem['a'] == 1
    assert ordem['b'] == 2
    assert pd.isna(ordem['sem_data'])


def test_pontuacao_por_item_nas_tres_versoes(base):
    consolidado = construir_consolidado(*base).set_index(['concurso', 'questao'])

    tcu = consolidado.loc['tcu']
    assert tcu['pontos_bruta'].tolist() == [1.0, 0.0, 0.0, 1.0]
    assert tcu['pontos_corrigida'].tolist() == [1.0, -1.0, 0.0, 1.0]
    assert tcu['pontos_ajustada'].tolist() == [1.0, -1.0, 0.0, 1.0]
    agsus = consolidado.loc['agsus']
    assert agsus['pontos_corrigida'].tolist()[:3] == [1.0, 0.0, 1.0]
    assert agsus['pontos_ajustada'].tolist()[:3] == [1.0, -0.25, 1.0]
    assert agsus.loc[4, ['pontos_bruta', 'pontos_corrigida', 'pontos_ajustada']].isna().all()


def test_peso_de_cada_variante_em_uma_coluna(base):
    variantes = [
        ConfiguracaoCorrecao(ModeloCorrecao.PONDERADA, pesos=(PesoItens(3, 4, 2.0),), variante='B3-08-A'),
        ConfiguracaoCorrecao(ModeloCorrecao.PONDERADA, pesos=(PesoItens(3, 4, 3.0),), variante='B3-10-A'),
    ]
    criar_analise(base, 'cpnu', ['acerto'] * 4, variantes, formato='multipla_escolha')

    consolidado = construir_consolidado(*base).set_index(['concurso', 'questao'])

    assert consolidado.loc['cpnu', 'peso__B3-08-A'].tolist() == [1.0, 1.0, 2.0, 2.0]
    assert consolidado.loc['cpnu', 'peso__B3-10-A'].tolist() == [1.0, 1.0, 3.0, 3.0]
    assert consolidado.loc['cpnu', 'peso__padrao'].isna().all()
    assert consolidado.loc['tcu', 'peso__padrao'].tolist() == [1.0] * 4
    assert consolidado.loc['tcu', 'peso__B3-08-A'].isna().all()


def test_quantidade_de_questoes_do_topico(base):
    consolidado = construir_consolidado(*base)

    tcu = consolidado[consolidado['concurso'] == 'tcu']
    assert tcu['n_topico'].tolist() == [2, 2, 2, 2]
    assert consolidado[consolidado['concurso'] == 'agsus']['n_topico'].tolist() == [2, 2, 3, 3, 3]


def test_disciplina_canonica_vem_da_taxonomia(base):
    tcu = construir_consolidado(*base).query("concurso == 'tcu'")

    assert tcu['disciplina'].tolist() == ['Português', 'Português', 'TI', 'TI']
    assert tcu['disciplina_canonica'].tolist() == ['Língua Portuguesa'] * 2 + ['Tecnologia da Informação'] * 2


def test_bloco_vem_da_prova_dividida_e_da_taxonomia_na_prova_unica(base):
    criar_analise(base, 'pf_cb', ['acerto'] * 3, [LIQUIDA], prova='cb')
    criar_analise(base, 'pf_cg', ['acerto'] * 3, [LIQUIDA], prova='cg')
    criar_analise(base, 'pf_ce', ['acerto'] * 3, [LIQUIDA], prova='ce')

    blocos = construir_consolidado(*base).groupby('concurso')['bloco'].agg(list)

    assert blocos['pf_cb'] == ['geral'] * 3
    assert blocos['pf_cg'] == ['geral'] * 3
    assert blocos['pf_ce'] == ['especifico'] * 3
    assert blocos['tcu'] == ['geral', 'geral', 'especifico', 'especifico']


def test_disciplina_nao_mapeada_pelo_pipeline_fica_sem_bloco_na_prova_unica(base):
    criar_analise(base, 'fgv', ['acerto'] * 3, [BRUTA], disciplinas=['nao_mapeado', 'Português', 'TI'])
    criar_analise(
        base, 'cespe', ['acerto'] * 3, [LIQUIDA], prova='ce', disciplinas=['nao_mapeado', 'TI', 'TI']
    )
    consolidado = construir_consolidado(*base).set_index(['concurso', 'questao'])

    assert consolidado.loc[('fgv', 1), ['disciplina_canonica', 'bloco']].tolist() == [
        'nao_mapeado',
        'nao_informado',
    ]
    assert consolidado.loc[('cespe', 1), 'bloco'] == 'especifico'
    validar_schema(consolidado.reset_index(), contar_questoes(base[1]))


def test_chave_de_topico_junta_disciplina_canonica_e_palavras_do_topico(base):
    criar_analise(base, 'outro', ['acerto'] * 3, [LIQUIDA], disciplinas=['Língua Portuguesa', 'TI', 'TI'])
    consolidado = construir_consolidado(*base).set_index(['concurso', 'questao'])

    assert consolidado.loc[('tcu', 1), 'chave_topico'] == consolidado.loc[('outro', 1), 'chave_topico']
    assert consolidado.loc[('tcu', 1), 'chave_topico'] != consolidado.loc[('tcu', 3), 'chave_topico']


def test_topico_nao_classificado_fica_sem_chave(base):
    criar_analise(
        base,
        'outro',
        ['acerto'] * 3,
        [LIQUIDA],
        disciplinas=['Português', 'nao_mapeado', 'TI'],
        topicos=['nao_mapeado', 'nao_mapeado', 'Redes'],
    )
    chaves = construir_consolidado(*base).query("concurso == 'outro'")['chave_topico']

    assert chaves.isna().tolist() == [True, True, False]


def test_disciplina_sem_mapeamento_reprova_a_validacao_com_os_nomes(base):
    gravar_taxonomia(base[2], {'Língua Portuguesa': {'bloco': 'geral'}})
    criar_analise(base, 'outro', ['acerto'] * 3, [LIQUIDA], disciplinas=['Português', 'Redes', 'TI'])
    consolidado = construir_consolidado(*base)

    with pytest.raises(
        SchemaInvalidoError, match=r"sem mapeamento na taxonomia: \['Português', 'Redes', 'TI'\]"
    ):
        validar_schema(consolidado, contar_questoes(base[1]))


def test_disciplinas_por_quantidade_de_concursos(base):
    criar_analise(base, 'terceiro', ['acerto'] * 3, [LIQUIDA], disciplinas=['Português', 'Atualidades', 'TI'])
    criar_analise(base, 'quarto', ['acerto'] * 3, [LIQUIDA], disciplinas=['nao_mapeado', 'Português', 'TI'])
    gravar_taxonomia(base[2], {**TAXONOMIA, 'Atualidades': {'bloco': 'geral'}})

    tabela = disciplinas_por_quantidade_de_concursos(construir_consolidado(*base))

    assert tabela.to_dict('records') == [
        {'concursos': '1', 'disciplinas': 1, 'nomes': 'Atualidades'},
        {'concursos': '2', 'disciplinas': 0, 'nomes': ''},
        {
            'concursos': '3 ou mais',
            'disciplinas': 2,
            'nomes': 'Língua Portuguesa, Tecnologia da Informação',
        },
    ]


def test_consolidado_construido_passa_na_validacao(base):
    consolidado = construir_consolidado(*base)

    validar_schema(consolidado, contar_questoes(base[1]))


@pytest.mark.parametrize(
    ('estragar', 'mensagem'),
    [
        (lambda df: df.drop(columns='fonte_correcao'), 'coluna ausente: fonte_correcao'),
        (
            lambda df: df.assign(modelo_correcao='escalonada'),
            "modelo_correcao: valores fora do domínio ['escalonada']",
        ),
        (lambda df: df.assign(resultado='talvez'), "resultado: valores fora do domínio ['talvez']"),
        (lambda df: df.iloc[1:], 'linhas: 8, esperadas 9'),
        (lambda df: df.assign(questao=df['questao'].astype(str)), 'questao: tipo'),
    ],
)
def test_validacao_aponta_cada_problema(base, estragar, mensagem):
    consolidado = estragar(construir_consolidado(*base))

    with pytest.raises(SchemaInvalidoError, match=mensagem.replace('[', r'\[').replace(']', r'\]')):
        validar_schema(consolidado, 9)


@pytest.fixture
def construcoes(monkeypatch) -> list[int]:
    chamadas = []
    original = modulo.construir_consolidado
    monkeypatch.setattr(modulo, 'construir_consolidado', lambda *a: chamadas.append(1) or original(*a))
    return chamadas


def test_carregar_grava_o_cache_e_nao_reconstroi_sem_mudanca(base, construcoes):
    primeiro = carregar_consolidado(*base)
    segundo = carregar_consolidado(*base)

    assert len(construcoes) == 1
    assert (base[1] / 'consolidado' / 'consolidado.parquet').exists()
    pd.testing.assert_frame_equal(primeiro, segundo)


@pytest.mark.parametrize(
    'arquivo',
    ['analises/tcu/questoes.csv', 'analises/tcu/correcao.json', 'provas/tcu/concurso.yaml', 'taxonomia.yaml'],
)
def test_carregar_reconstroi_quando_uma_entrada_fica_mais_nova_que_o_cache(base, construcoes, arquivo):
    carregar_consolidado(*base)
    cache = base[1] / 'consolidado' / 'consolidado.parquet'
    futuro = cache.stat().st_mtime + 10
    os.utime(base[0].parent / arquivo, (futuro, futuro))

    carregar_consolidado(*base)

    assert len(construcoes) == 2


def test_carregar_reconstroi_quando_surge_um_concurso_novo(base):
    carregar_consolidado(*base)
    criar_analise(base, 'novo', ['acerto'] * 2, [LIQUIDA])
    cache = base[1] / 'consolidado' / 'consolidado.parquet'
    passado = cache.stat().st_mtime - 10
    for arquivo in ['analises/novo/questoes.csv', 'analises/novo/correcao.json', 'provas/novo/concurso.yaml']:
        os.utime(base[0].parent / arquivo, (passado, passado))

    assert set(carregar_consolidado(*base)['concurso']) == {'tcu', 'agsus', 'novo'}


def test_concurso_sem_arquivo_de_correcao_fica_fora_e_reprova_a_contagem(base):
    (base[1] / 'agsus' / 'correcao.json').unlink()
    consolidado = construir_consolidado(*base)

    assert set(consolidado['concurso']) == {'tcu'}
    with pytest.raises(SchemaInvalidoError, match='linhas: 4, esperadas 9'):
        validar_schema(consolidado, contar_questoes(base[1]))


def test_avisos_de_data_e_de_correcao(base):
    default = ConfiguracaoCorrecao(nota_maxima=2.0)
    criar_analise(base, 'sem_regra', ['acerto'] * 2, [default])

    avisos = avisos_do_consolidado(construir_consolidado(*base))

    assert avisos.to_dict('records') == [
        {
            'concurso': 'sem_regra',
            'tipo': 'data',
            'aviso': 'sem data da prova; fora das análises de tendência',
        },
        {
            'concurso': 'sem_regra',
            'tipo': 'correcao',
            'aviso': 'regra de correção no default (bruta, fator 0)',
        },
    ]


def test_perfil_por_concurso_em_ordem_cronologica(base):
    perfil = perfil_por_concurso(construir_consolidado(*base))

    assert perfil['concurso'].tolist() == ['agsus', 'tcu']
    assert perfil.set_index('concurso').loc['agsus', ['questoes', 'anuladas', 'variantes']].tolist() == [
        5,
        1,
        1,
    ]


def test_perfil_de_n_por_concurso_e_prova(base):
    criar_analise(
        base,
        'pf',
        ['acerto'] * 4,
        [LIQUIDA],
        prova='ce',
        disciplinas=['TI', 'TI', 'TI', 'nao_mapeado'],
        topicos=['Redes', 'Redes', 'Redes', 'nao_mapeado'],
        anuladas=(1,),
    )

    perfil = perfil_de_n(construir_consolidado(*base), min_n=3).set_index(['concurso', 'prova'])

    assert perfil.loc[('pf', 'ce')].to_dict() == {
        'questoes': 4,
        'anuladas': 1,
        'topicos': 1,
        'topicos_com_n_minimo': 1,
        'mediana_n_topico': 3.0,
    }
    assert perfil.loc[('agsus', 'unica'), ['topicos', 'topicos_com_n_minimo']].tolist() == [2, 1]


def test_n_por_topico_do_maior_para_o_menor(base):
    tabela = n_por_topico(construir_consolidado(*base))

    assert tabela[['concurso', 'topico', 'disciplina_canonica', 'n']].to_dict('records') == [
        {'concurso': 'agsus', 'topico': 'Redes', 'disciplina_canonica': 'Tecnologia da Informação', 'n': 3},
        {'concurso': 'agsus', 'topico': 'Crase', 'disciplina_canonica': 'Língua Portuguesa', 'n': 2},
        {'concurso': 'tcu', 'topico': 'Crase', 'disciplina_canonica': 'Língua Portuguesa', 'n': 2},
        {'concurso': 'tcu', 'topico': 'Redes', 'disciplina_canonica': 'Tecnologia da Informação', 'n': 2},
    ]


def test_topicos_por_n_conta_combinacoes_de_topico_e_prova(base):
    tabela = topicos_por_n(construir_consolidado(*base), min_n=3)

    assert tabela.to_dict('records') == [
        {'n': '1', 'topicos': 0},
        {'n': '2', 'topicos': 3},
        {'n': '3 ou mais', 'topicos': 1},
    ]


def test_resumo_mostra_as_primeiras_linhas_e_o_total():
    tabela = pd.DataFrame({'x': range(30), 'grupo': ['a'] * 20 + ['b'] * 10})

    resumo = resumir(tabela, n=5, contar='grupo')

    assert resumo.total == 30
    assert resumo.primeiras['x'].tolist() == [0, 1, 2, 3, 4]
    assert resumo.contagens.to_dict() == {'a': 20, 'b': 10}
    assert '30 linhas' in resumo._repr_html_()


def test_topicos_do_edital_de_cada_concurso(tmp_path):
    edital = Edital(
        'edital.pdf',
        None,
        (
            Conhecimento(
                'Gerais',
                (
                    Disciplina(
                        'Português', (Topico('1', 'Crase', 'Crase.'), Topico('2', 'Regência', 'Regência.'))
                    ),
                ),
            ),
        ),
    )
    (tmp_path / 'tcu').mkdir()
    edital.gravar_json(tmp_path / 'tcu' / ARQUIVO_EDITAL_ESTRUTURADO)
    (tmp_path / 'sem_edital').mkdir()

    tabela = topicos_do_edital(tmp_path)

    assert tabela.to_dict('records') == [
        {'concurso': 'tcu', 'disciplina': 'Português', 'topico': 'Crase'},
        {'concurso': 'tcu', 'disciplina': 'Português', 'topico': 'Regência'},
    ]
    assert topicos_do_edital(tmp_path / 'vazia').columns.tolist() == ['concurso', 'disciplina', 'topico']
