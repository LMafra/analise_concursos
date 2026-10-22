import json

import yaml
from conftest import analisar, ler_csv
from test_cli_correcao_edital import CERTO_ERRADO, MULTIPLA_ESCOLHA, criar
from test_cli_edital import MANUAL
from test_edital import PAGINAS

from concursos.analytics.correcao import ler_correcao
from concursos.analytics.validacao_edital import COLUNAS_DISCREPANCIAS
from concursos.cli import main

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


CORTES = """8.11.4 Será reprovado nas provas objetivas e eliminado do concurso público o candidato que
se enquadrar em pelo menos um dos itens a seguir:
a) obtiver nota inferior a 3,00 pontos na prova objetiva de conhecimentos gerais P ;
b) obtiver nota inferior a 2,00 pontos na prova objetiva de conhecimentos específicos P ;
c) obtiver nota inferior a 6,00 pontos no conjunto das provas objetivas."""


def test_edital_estruturado_ganha_os_cortes_com_unidade_escopo_e_origem(raizes):
    provas, analises = raizes
    criar(provas, CERTO_ERRADO, 'edital.txt', edital(CORTES))

    assert analisar(provas, analises) == 0

    cortes = estruturado(analises)['cortes']
    assert [(c['escopo'], c['valor'], c['unidade']) for c in cortes] == [
        ('geral', 3.0, 'pontos'),
        ('especifico', 2.0, 'pontos'),
        ('conjunto', 6.0, 'pontos'),
    ]
    assert {(c['fonte'], c['documento_origem'], c['pagina_origem']) for c in cortes} == {
        ('edital', 'edital.txt', 6)
    }


RETIFICACAO = """CONSELHO FEDERAL DE EXEMPLO (CFE)
EDITAL Nº 2 – CFE, DE 9 DE FEVEREIRO DE 2026
O Presidente torna pública a retificação do subitem 8.11.4, que passa a ter a seguinte redação:
8.11.4 [...] c) obtiver nota inferior a 7,00 pontos no conjunto das provas objetivas."""


def test_retificacao_declarada_sobrescreve_o_corte_e_marca_a_fonte(raizes):
    provas, analises = raizes
    declarado = {'arquivo': 'edital.txt', 'retificacoes': ['retificacao.txt']}
    criar(provas, CERTO_ERRADO, declarado, {**edital(CORTES), 'retificacao.txt': RETIFICACAO})

    assert analisar(provas, analises) == 0

    dados = estruturado(analises)
    cortes = {c['escopo']: c for c in dados['cortes']}
    assert list(cortes) == ['geral', 'especifico', 'conjunto']
    conjunto = cortes['conjunto']
    assert (conjunto['valor'], conjunto['fonte'], conjunto['documento_origem']) == (
        7.0,
        'retificacao',
        'retificacao.txt',
    )
    assert cortes['geral']['fonte'] == 'edital'
    assert dados['identificacao']['edital']['valor'] == 'EDITAL Nº 1 – CFE, DE 2 DE JANEIRO DE 2026'
    assert ler_correcao(analises / 'sintetico')[0].nota_corte != 7.0


def test_retificacao_ausente_deixa_o_concurso_incompleto(raizes, capsys):
    provas, _ = raizes
    declarado = {'arquivo': 'edital.txt', 'retificacoes': ['retificacao.txt']}
    criar(provas, CERTO_ERRADO, declarado, edital(CORTES))

    assert main(['status', '--provas', str(provas)]) == 0

    saida = capsys.readouterr().out
    assert 'incompleto' in saida and 'retificacao.txt: arquivo ausente (edital)' in saida


def test_retificacoes_que_nao_sao_lista_de_arquivos_apontam_o_campo(raizes, capsys):
    provas, _ = raizes
    criar(provas, CERTO_ERRADO, {'arquivo': 'edital.txt', 'retificacoes': 'ret.txt'}, edital())

    assert main(['status', '--provas', str(provas)]) == 0

    assert 'edital.retificacoes: deve ser uma lista de arquivos' in capsys.readouterr().out


QUADRO_DE_PROVAS = """7.1 Será aplicado exame de habilidades e conhecimentos, conforme o quadro a seguir:
PROVA/TIPO ÁREA DE CONHECIMENTO NÚMERO DE ITENS CARÁTER
Prova objetiva (P ) Conhecimentos gerais 2
1
Prova objetiva (P ) Conhecimentos específicos 3
2
7.2 As provas objetivas terão a duração de 3 horas."""

QUADRO_DE_DISCIPLINAS = """9.5.1 A Prova Objetiva será composta por 3 (três) questões de Conhecimentos Gerais e 1 (uma)
questão de Conhecimentos Específicos.
CARGO: ANALISTA DE TI
CONHECIMENTOS DISCIPLINAS TOTAL DE QUESTÕES PONTUAÇÃO
Língua Portuguesa 3 3
ESPECÍFICOS Conforme conteúdo programático 1 1
Total: 4 4"""


def test_total_de_itens_divergente_do_edital_e_error(raizes):
    provas, analises = raizes
    criar(provas, CERTO_ERRADO, 'edital.txt', edital(QUADRO_DE_PROVAS))

    assert analisar(provas, analises) == 0

    assert estruturado(analises)['distribuicao']['total']['valor'] == 5
    [linha] = discrepancias(analises).query("item == 'total de itens'").to_dict('records')
    assert (linha['severidade'], linha['esperado_edital'], linha['observado_prova']) == ('error', 5, 4)


def test_contagem_por_disciplina_divergente_do_edital_e_warn(raizes):
    provas, analises = raizes
    disciplinas = [
        {'inicio': 1, 'fim': 2, 'disciplina': 'Língua Portuguesa'},
        {'inicio': 3, 'fim': 4, 'disciplina': 'Banco de Dados'},
    ]
    criar(provas, MULTIPLA_ESCOLHA, 'edital.txt', edital(QUADRO_DE_DISCIPLINAS))
    caminho = provas / 'sintetico' / 'concurso.yaml'
    config = yaml.safe_load(caminho.read_text(encoding='utf-8'))
    config['provas']['unica']['disciplinas'] = disciplinas
    caminho.write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')

    assert analisar(provas, analises) == 0

    [linha] = discrepancias(analises).query("item == 'disciplina: Língua Portuguesa'").to_dict('records')
    assert (linha['severidade'], linha['esperado_edital'], linha['observado_prova']) == ('warn', 3, 2)


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


def catalogo(analises) -> str:
    return (analises / 'sintetico' / 'catalogo_edital.md').read_text(encoding='utf-8')


def test_catalogo_tem_a_tabela_as_propostas_e_os_descartados(raizes):
    provas, analises = raizes
    criar(provas, CERTO_ERRADO, 'edital.txt', edital(CORTES))

    assert analisar(provas, analises) == 0

    texto = catalogo(analises)
    assert texto.startswith('# Catálogo do edital: Conselho Federal de Exemplo (CFE), Analista de TI')
    tabela, propostas, descartados = (
        texto.index(secao) for secao in ('## Descobertas', '## Propostas', '## Descartados')
    )
    assert tabela < propostas < descartados
    assert (
        '| Informação | Valor | Trecho de origem | Uso no projeto | Impacto | Status | No edital |' in texto
    )
    assert '| Critérios de aprovação |' in texto
    assert 'não encontrado' in texto[tabela:propostas]
    assert 'Número de alternativas' in texto[propostas:descartados]
    assert 'sem sinal na folha digitalizada' in texto[descartados:]
    assert 'Taxa de inscrição' in texto[descartados:]


def test_cinco_alternativas_no_edital_e_gabarito_ate_d_e_error(raizes):
    provas, analises = raizes
    alternativas = 'As questões da prova objetiva terão 5 (cinco) alternativas, com uma só correta.'
    criar(provas, MULTIPLA_ESCOLHA, 'edital.txt', edital(alternativas))

    assert analisar(provas, analises) == 0

    [linha] = discrepancias(analises).query("item == 'alternativas'").to_dict('records')
    assert (linha['severidade'], linha['esperado_edital'], linha['observado_prova']) == (
        'error',
        'A a E',
        'A a D',
    )
