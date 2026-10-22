import json

from conftest import analisar, ler_csv
from test_cli_correcao_edital import CERTO_ERRADO, criar
from test_cli_edital import MANUAL
from test_edital import PAGINAS

from concursos.analytics.validacao_edital import COLUNAS_DISCREPANCIAS

CAPA = """CONSELHO FEDERAL DE EXEMPLO (CFE)
CONCURSO PÚBLICO PARA O PROVIMENTO DE VAGAS E A FORMAÇÃO DE CADASTRO DE RESERVA
EDITAL Nº 1 – CFE, DE 2 DE JANEIRO DE 2026
O Presidente do Conselho Federal de Exemplo torna pública a realização de concurso público."""


def edital(*paginas: str) -> dict[str, str]:
    return {'edital.txt': '\f'.join([CAPA, *PAGINAS, *paginas])}


def estruturado(analises) -> dict:
    return json.loads((analises / 'sintetico' / 'edital_estruturado.json').read_text(encoding='utf-8'))


def discrepancias(analises):
    return ler_csv(analises / 'sintetico' / 'discrepancias_edital.csv')


def test_edital_estruturado_ganha_a_identificacao_e_mantem_o_conteudo_programatico(raizes):
    provas, analises = raizes
    criar(provas, CERTO_ERRADO, 'edital.txt', edital())

    assert analisar(provas, analises) == 0
    assert analisar(provas, analises, '--forcar') == 0

    dados = estruturado(analises)
    identificacao = dados['identificacao']
    assert identificacao['nome_oficial']['valor'] == 'Conselho Federal de Exemplo (CFE)'
    assert identificacao['cargo']['valor'] == 'Analista de TI'
    assert identificacao['especialidade']['valor'] == 'Ciência de Dados'
    assert identificacao['cargo_casado'] is True
    cargo = identificacao['cargo']
    assert (cargo['fonte'], cargo['documento_origem'], cargo['pagina_origem']) == ('edital', 'edital.txt', 4)
    assert 'CARGO 2: ANALISTA DE TI' in cargo['trecho_origem']
    assert [c['nome'] for c in dados['conhecimentos']] == [
        'Conhecimentos Gerais',
        'Conhecimentos Específicos',
    ]


def test_discrepancias_tem_o_contrato_e_avisam_cargo_sem_casamento(raizes):
    provas, analises = raizes
    arquivos = {**edital(), 'edital_manual.yaml': MANUAL}
    criar(provas, CERTO_ERRADO, {'arquivo': 'edital.txt', 'manual': 'edital_manual.yaml'}, arquivos)
    caminho = provas / 'sintetico' / 'concurso.yaml'
    caminho.write_text(
        caminho.read_text(encoding='utf-8').replace('Analista de TI - Ciência de Dados', 'Auditor de Contas'),
        encoding='utf-8',
    )

    assert analisar(provas, analises) == 0

    tabela = discrepancias(analises)
    assert list(tabela.columns) == COLUNAS_DISCREPANCIAS
    [linha] = tabela[tabela['item'] == 'cargo'].to_dict('records')
    assert linha['severidade'] == 'warn'
    assert linha['observado_prova'] == 'Auditor de Contas'
    assert 'Analista de TI' in linha['esperado_edital']
    assert estruturado(analises)['identificacao']['cargo_casado'] is False


def test_cabecalho_do_relatorio_mostra_o_nome_oficial_e_o_cargo(raizes):
    provas, analises = raizes
    criar(provas, CERTO_ERRADO, 'edital.txt', edital())

    assert analisar(provas, analises) == 0

    relatorio = (analises / 'sintetico' / 'relatorio.md').read_text(encoding='utf-8')
    assert (
        '- Concurso: Conselho Federal de Exemplo (CFE) (EDITAL Nº 1 – CFE, DE 2 DE JANEIRO DE 2026)'
        in relatorio
    )
    assert '- Cargo: Analista de TI – Ciência de Dados' in relatorio
