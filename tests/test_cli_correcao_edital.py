import json
import logging
from datetime import date

import pandas as pd
import pytest
from conftest import analisar, criar_concurso, ler_csv
from test_analytics_correcao import AGSUS, CEBRASPE
from test_cli_edital import MANUAL
from test_edital import PAGINAS

from concursos import pipeline
from concursos.analytics.correcao import FonteCorrecao, aplicar_correcao, ler_correcao
from concursos.cli import main
from concursos.concurso_config import carregar_concurso
from concursos.modelo import Escolaridade, Formato, Nivel

CERTO_ERRADO = {
    'formato': 'certo_errado',
    'pontuacao': 'cebraspe',
    'arquivos': {'gabarito.txt': '1 C\n2 E\n3 X\n4 C\n', 'respostas.txt': '1 C\n2 C\n3 E\n4 E\n'},
}
MULTIPLA_ESCOLHA = {
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'arquivos': {'gabarito.txt': '1 A\n2 B\n3 *\n4 D\n', 'respostas.txt': '1 A\n2 C\n'},
}


def criar(provas, prova: dict, edital=None, arquivos: dict | None = None, **extra):
    config = {
        'nome': 'sintetico',
        'banca': 'cebraspe' if prova['pontuacao'] == 'cebraspe' else 'fgv',
        'cargo': 'Analista de TI - Ciência de Dados',
        'formato': prova['formato'],
        'pontuacao': prova['pontuacao'],
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
        'respostas': {'arquivo': 'respostas.txt'},
        **extra,
    }
    if edital is not None:
        config['edital'] = edital
    criar_concurso(provas, 'sintetico', config, {**prova['arquivos'], **(arquivos or {})})


def correcao(analises) -> list[dict]:
    return json.loads((analises / 'sintetico' / 'correcao.json').read_text(encoding='utf-8'))


def edital_com(*regra: str) -> dict[str, str]:
    return {'edital.txt': '\f'.join([*PAGINAS, *regra])}


def test_regra_do_edital_e_gravada_com_fonte_documento_pagina_e_trecho(raizes):
    provas, analises = raizes
    criar(provas, MULTIPLA_ESCOLHA, 'edital.txt', edital_com(AGSUS))

    assert analisar(provas, analises) == 0

    [cfg] = correcao(analises)
    assert cfg['modelo'] == 'bruta'
    assert cfg['fator_penalidade'] == 0.0
    assert cfg['fonte'] == 'edital'
    assert cfg['documento_origem'] == 'edital.txt'
    assert cfg['pagina_origem'] == len(PAGINAS) + 1
    assert 'valendo 1 (um) ponto cada questão' in cfg['trecho_origem']
    assert cfg['nota_maxima'] == 70.0
    assert cfg['variante'] is None


def test_cebraspe_liquida_e_nota_corrigida_igual_a_nota_liquida_legada(raizes):
    provas, analises = raizes
    criar(provas, CERTO_ERRADO, 'edital.txt', edital_com(CEBRASPE))

    assert analisar(provas, analises) == 0

    [cfg] = correcao(analises)
    assert (cfg['modelo'], cfg['fator_penalidade'], cfg['fonte']) == ('liquida', 1.0, 'edital')
    assert (cfg['nota_maxima'], cfg['nota_corte']) == (4.0, 60.0)
    questoes = ler_csv(analises / 'sintetico' / 'questoes.csv')
    [lida] = ler_correcao(analises / 'sintetico')
    nota = aplicar_correcao(questoes, lida, Formato.CERTO_ERRADO).nota
    legado = ler_csv(analises / 'sintetico' / 'desempenho_por_disciplina.csv')
    assert nota == legado['nota_liquida'].sum() == 0


def relatorio(analises) -> str:
    return (analises / 'sintetico' / 'relatorio.md').read_text(encoding='utf-8')


def linha_do_comparativo(analises) -> dict[str, str]:
    texto = (analises / 'consolidado' / 'comparativo_concursos.md').read_text(encoding='utf-8')
    linhas = texto.split('## Desempenho por concurso', 1)[1].strip().splitlines()
    cabecalho, linha = (
        ([c.strip() for c in linha.strip('|').split('|')]) for linha in (linhas[0], linhas[2])
    )
    return dict(zip(cabecalho, linha, strict=True))


def test_relatorio_e_comparativo_mostram_a_nota_final_quando_ha_desconto_por_erro(raizes):
    provas, analises = raizes
    criar(provas, CERTO_ERRADO, 'edital.txt', edital_com(CEBRASPE))

    assert analisar(provas, analises) == 0

    nota = '0 de 4 pontos, nota de corte 60 (abaixo do corte)'
    assert f'**Nota final** (regra do edital): {nota}.' in relatorio(analises)
    assert linha_do_comparativo(analises)['nota_final'] == nota


def test_sem_desconto_nem_pesos_a_nota_final_e_a_propria_nota(raizes):
    provas, analises = raizes
    criar(provas, MULTIPLA_ESCOLHA, 'edital.txt', edital_com(AGSUS))

    assert analisar(provas, analises) == 0

    assert 'Nota final' not in relatorio(analises)
    assert linha_do_comparativo(analises)['nota_final'] == '-'


def test_nota_final_por_variante_no_relatorio_e_no_comparativo(raizes):
    provas, analises = raizes
    variantes = ['geral', {'nome': 'ti', 'pesos': [{'itens': [3, 4], 'peso': 3}]}]
    criar(provas, MULTIPLA_ESCOLHA, correcao={'variantes': variantes})

    assert analisar(provas, analises) == 0

    assert '**Nota final** (regra do edital), por opção de cargo:\n\n- ti: 4 de 8 pontos.' in relatorio(
        analises
    )
    assert linha_do_comparativo(analises)['nota_final'] == 'ti: 4 de 8 pontos'


def test_edital_sem_a_regra_nem_configuracao_grava_default_e_avisa(raizes, caplog):
    provas, analises = raizes
    criar(provas, MULTIPLA_ESCOLHA, 'edital.txt', edital_com(), banca='generic')

    with caplog.at_level(logging.WARNING):
        assert analisar(provas, analises) == 0

    [cfg] = correcao(analises)
    assert (cfg['modelo'], cfg['fonte'], cfg['trecho_origem']) == ('bruta', 'default', None)
    assert 'usando o default' in caplog.text


def test_bloco_correcao_do_concurso_yaml_vira_fonte_config(raizes):
    provas, analises = raizes
    bloco = {'modelo': 'liquida', 'fator_penalidade': 1, 'nota_corte': 2}
    criar(provas, CERTO_ERRADO, correcao=bloco)

    assert analisar(provas, analises) == 0

    [cfg] = correcao(analises)
    assert (cfg['modelo'], cfg['fator_penalidade'], cfg['fonte']) == ('liquida', 1.0, 'config')
    assert (cfg['nota_maxima'], cfg['nota_corte']) == (4.0, 2.0)


def test_edital_manual_com_pdf_declarado_le_cada_documento_uma_vez(raizes, monkeypatch):
    provas, analises = raizes
    edital = {'arquivo': 'edital.txt', 'anexos': ['anexo.txt'], 'manual': 'edital_manual.yaml'}
    arquivos = {**edital_com(CEBRASPE), 'anexo.txt': 'ANEXO I', 'edital_manual.yaml': MANUAL}
    criar(provas, CERTO_ERRADO, edital, arquivos)
    lidos = []
    original = pipeline.extrair_paginas
    monkeypatch.setattr(
        pipeline,
        'extrair_paginas',
        lambda caminho, ocr=True: lidos.append(caminho.name) or original(caminho, ocr),
    )

    assert analisar(provas, analises) == 0

    assert sorted(lidos) == ['anexo.txt', 'edital.txt']
    [cfg] = correcao(analises)
    assert (cfg['fonte'], cfg['documento_origem']) == ('edital', 'edital.txt')


def test_estrutura_dos_csvs_nao_muda(raizes):
    provas, analises = raizes
    criar(provas, CERTO_ERRADO, 'edital.txt', edital_com(CEBRASPE))

    assert analisar(provas, analises) == 0

    pasta = analises / 'sintetico'
    desempenho = [
        'concurso',
        'prova',
        'disciplina',
        'topico',
        'total',
        'acertos',
        'erros',
        'percentual',
        'em_branco',
        'anuladas',
        'nota_liquida',
    ]
    assert list(ler_csv(pasta / 'desempenho_por_disciplina.csv').columns) == desempenho
    assert list(ler_csv(pasta / 'desempenho_por_topico.csv').columns) == desempenho
    assert list(ler_csv(pasta / 'questoes.csv').columns) == [
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
    assert list(pd.read_csv(pasta / 'respostas_extraidas.csv').columns) == [
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


def test_analise_de_versao_anterior_e_refeita_e_ganha_o_arquivo_de_correcao(raizes, caplog):
    provas, analises = raizes
    criar(provas, MULTIPLA_ESCOLHA)
    assert analisar(provas, analises) == 0
    pasta = analises / 'sintetico'
    caminho_manifesto = pasta / '.manifesto.json'
    manifesto = json.loads(caminho_manifesto.read_text(encoding='utf-8'))
    caminho_manifesto.write_text(json.dumps({**manifesto, 'versao': 3}), encoding='utf-8')
    (pasta / 'correcao.json').unlink()

    with caplog.at_level(logging.INFO):
        assert analisar(provas, analises) == 0

    assert (pasta / 'correcao.json').exists()
    assert 'sem mudanças' not in caplog.text


@pytest.mark.parametrize(
    ('bloco', 'mensagem'),
    [
        ({'modelo': 'escalonada'}, "correcao.modelo: valor 'escalonada' inválido"),
        ({'modelo': 'liquida'}, "modelo 'liquida' exige fator_penalidade maior que 0"),
        ({'modelo': 'bruta', 'fator_penalidade': 1}, "modelo 'bruta' incompatível com fator_penalidade 1"),
        (
            {'modelo': 'ponderada', 'fator_penalidade': 1},
            "modelo 'ponderada' incompatível com fator_penalidade 1",
        ),
        ({'modelo': 'ponderada'}, "modelo 'ponderada' exige pesos ou variantes"),
        ({'pesos': [{'itens': [3, 1], 'peso': 2}]}, 'correcao.pesos: faixa 3-1 inválida'),
        ({'pesos': [{'itens': [1, 4], 'peso': 0}]}, 'correcao.pesos: peso 0 deve ser maior que 0'),
        ({'variantes': ['A', 'A']}, "correcao.variantes: 'A' repetida"),
        ({'variantes': [{'pesos': []}]}, "campo obrigatório 'correcao.variantes.nome' ausente"),
        ({'fator_penalidade': 'um'}, "correcao.fator_penalidade: valor 'um' não é numérico"),
    ],
)
def test_bloco_correcao_invalido_aponta_o_campo(raizes, capsys, bloco, mensagem):
    provas, _ = raizes
    criar(provas, CERTO_ERRADO, correcao=bloco)

    assert main(['status', '--provas', str(provas)]) == 0

    assert mensagem in capsys.readouterr().out


def test_variantes_declaradas_viram_uma_configuracao_por_variante_no_arquivo(raizes):
    provas, analises = raizes
    variantes = ['geral', {'nome': 'ti', 'pesos': [{'itens': [3, 4], 'peso': 3}]}]
    criar(provas, MULTIPLA_ESCOLHA, correcao={'variantes': variantes})

    assert analisar(provas, analises) == 0

    geral, ti = ler_correcao(analises / 'sintetico')
    assert (geral.variante, geral.modelo, geral.pesos, geral.nota_maxima) == ('geral', 'bruta', (), 4.0)
    assert (ti.variante, ti.modelo, ti.fonte, ti.nota_maxima) == ('ti', 'ponderada', 'config', 1 + 1 + 3 + 3)
    assert ti.pesos[0].peso == 3.0
    questoes = ler_csv(analises / 'sintetico' / 'questoes.csv')
    assert aplicar_correcao(questoes, ti, Formato.MULTIPLA_ESCOLHA).nota == 1 + 3


def test_data_da_prova_e_metadados_declarados_sao_aceitos_e_a_data_vai_para_o_arquivo(raizes):
    provas, analises = raizes
    criar(provas, MULTIPLA_ESCOLHA, data_prova=date(2025, 10, 5), nivel='federal', escolaridade='medio')

    assert analisar(provas, analises) == 0

    config = carregar_concurso(provas / 'sintetico')
    assert (config.data_prova, config.nivel, config.escolaridade) == (
        date(2025, 10, 5),
        Nivel.FEDERAL,
        Escolaridade.MEDIO,
    )
    [cfg] = ler_correcao(analises / 'sintetico')
    assert (cfg.data_prova, cfg.fonte_data) == (date(2025, 10, 5), FonteCorrecao.CONFIG)


def test_metadados_ausentes_ficam_nao_informados(raizes):
    provas, _ = raizes
    criar(provas, MULTIPLA_ESCOLHA)

    config = carregar_concurso(provas / 'sintetico')

    assert (config.data_prova, config.nivel, config.escolaridade) == (
        None,
        Nivel.NAO_INFORMADO,
        Escolaridade.NAO_INFORMADO,
    )


@pytest.mark.parametrize(
    ('campos', 'mensagem'),
    [
        ({'data_prova': '22/02/2026'}, "data_prova: valor '22/02/2026' não é uma data ISO 8601 (aaaa-mm-dd)"),
        ({'data_prova': 20260222}, "data_prova: valor '20260222' não é uma data ISO 8601"),
        ({'nivel': 'distrital'}, "nivel: valor 'distrital' inválido"),
        ({'escolaridade': 'fundamental'}, "escolaridade: valor 'fundamental' inválido"),
    ],
)
def test_data_e_metadados_invalidos_apontam_o_campo(raizes, capsys, campos, mensagem):
    provas, _ = raizes
    criar(provas, MULTIPLA_ESCOLHA, **campos)

    assert main(['status', '--provas', str(provas)]) == 0

    assert mensagem in capsys.readouterr().out


def test_data_impossivel_sem_aspas_no_yaml_aponta_o_campo_sem_derrubar_os_outros(raizes, capsys):
    provas, _ = raizes
    criar(provas, MULTIPLA_ESCOLHA)
    caminho = provas / 'sintetico' / 'concurso.yaml'
    caminho.write_text(caminho.read_text(encoding='utf-8') + 'data_prova: 2026-02-30\n', encoding='utf-8')

    assert main(['status', '--provas', str(provas)]) == 0

    assert "data_prova: valor '2026-02-30' não é uma data ISO 8601" in capsys.readouterr().out


def test_nivel_e_escolaridade_vazios_ficam_nao_informados(raizes):
    provas, _ = raizes
    criar(provas, MULTIPLA_ESCOLHA, nivel=None, escolaridade=None)

    config = carregar_concurso(provas / 'sintetico')

    assert (config.nivel, config.escolaridade) == (Nivel.NAO_INFORMADO, Escolaridade.NAO_INFORMADO)
