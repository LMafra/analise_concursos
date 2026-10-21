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
    perfil_por_concurso,
    validar_schema,
)
from concursos.analytics.correcao import ConfiguracaoCorrecao, FonteCorrecao, gravar_correcao
from concursos.analytics.visualizacao import resumir
from concursos.concurso_config import PesoItens
from concursos.modelo import ModeloCorrecao

LIQUIDA = ConfiguracaoCorrecao(
    ModeloCorrecao.LIQUIDA, 1.0, nota_maxima=4.0, fonte=FonteCorrecao.EDITAL, confianca=0.95
)
BRUTA = ConfiguracaoCorrecao(
    ModeloCorrecao.BRUTA, 0.0, nota_maxima=4.0, fonte=FonteCorrecao.EDITAL, confianca=0.9
)


def criar_analise(
    raizes: tuple[Path, Path],
    nome: str,
    resultados: list[str],
    correcoes: list[ConfiguracaoCorrecao],
    formato: str = 'certo_errado',
    data_prova: date | None = None,
    anuladas: tuple[int, ...] = (),
    **config,
) -> None:
    provas, analises = raizes
    (provas / nome).mkdir(parents=True)
    dados = {
        'nome': nome,
        'banca': 'cebraspe' if formato == 'certo_errado' else 'fgv',
        'formato': formato,
        'provas': {'unica': {'gabarito': 'g.txt', 'itens': [1, len(resultados)]}},
        'respostas': {'arquivo': 'r.txt'},
        **config,
    }
    (provas / nome / 'concurso.yaml').write_text(yaml.safe_dump(dados), encoding='utf-8')
    destino = analises / nome
    destino.mkdir(parents=True)
    pd.DataFrame(
        {
            'questao': range(1, len(resultados) + 1),
            'prova': 'unica',
            'disciplina': ['Português', 'Português', *['TI'] * (len(resultados) - 2)],
            'topico_sugerido': 'x',
            'score': 0.5,
            'topico': ['Crase', 'Crase', *['Redes'] * (len(resultados) - 2)],
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
def base(tmp_path) -> tuple[Path, Path]:
    raizes = (tmp_path / 'provas', tmp_path / 'analises')
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
    raizes = (tmp_path / 'provas', tmp_path / 'analises')
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
    'arquivo', ['analises/tcu/questoes.csv', 'analises/tcu/correcao.json', 'provas/tcu/concurso.yaml']
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


def test_resumo_mostra_as_primeiras_linhas_e_o_total():
    tabela = pd.DataFrame({'x': range(30), 'grupo': ['a'] * 20 + ['b'] * 10})

    resumo = resumir(tabela, n=5, contar='grupo')

    assert resumo.total == 30
    assert resumo.primeiras['x'].tolist() == [0, 1, 2, 3, 4]
    assert resumo.contagens.to_dict() == {'a': 20, 'b': 10}
    assert '30 linhas' in resumo._repr_html_()
