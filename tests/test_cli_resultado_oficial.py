import logging

from conftest import analisar, criar_concurso

GABARITO = '1 A\n2 B\n3 C\n4 D\n5 E\n6 A\n'
RESPOSTAS = '1 A\n2 B\n3 C\n4 A\n5 E\n6 B\n'
LISTA = 'RESULTADO DA PROVA OBJETIVA\nInscrição Nome Nota\n100001 Fulano de Tal {nota}\n'


def criar(provas, nota: str, extra: dict | None = None, cabecalho: str = ''):
    config = {
        'nome': 'sintetico',
        'banca': 'fgv',
        'formato': 'multipla_escolha',
        'pontuacao': 'simples',
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 6]}},
        'respostas': {'arquivo': 'respostas.txt'},
        'resultado_oficial': {'arquivo': 'resultado.txt', 'identificador': '100001', **(extra or {})},
    }
    arquivos = {
        'gabarito.txt': GABARITO,
        'respostas.txt': RESPOSTAS,
        'resultado.txt': cabecalho + LISTA.format(nota=nota),
    }
    criar_concurso(provas, 'sintetico', config, arquivos)


def relatorio(analises) -> str:
    return (analises / 'sintetico' / 'relatorio.md').read_text(encoding='utf-8')


def test_resultado_divergente_gera_alerta_no_relatorio_e_no_log(raizes, caplog):
    provas, analises = raizes
    criar(provas, '5')

    with caplog.at_level(logging.WARNING):
        assert analisar(provas, analises) == 0

    texto = relatorio(analises)
    assert '## Validação com o resultado oficial' in texto
    assert '> **Atenção:**' in texto
    assert 'oficial 5 pontos, calculado 4' in texto
    assert 'diverge do resultado oficial' in caplog.text


def test_resultado_que_confere(raizes, caplog):
    provas, analises = raizes
    criar(provas, '4,00')

    with caplog.at_level(logging.WARNING):
        analisar(provas, analises)

    texto = relatorio(analises)
    assert 'confere com o resultado oficial (4 pontos)' in texto
    assert 'Atenção' not in texto
    assert 'diverge' not in caplog.text


def test_pesos_por_faixa_de_itens(raizes):
    provas, analises = raizes
    criar(provas, '5,5', {'pesos': [{'itens': [4, 6], 'peso': 2.5}]})

    analisar(provas, analises)

    assert 'confere com o resultado oficial (5,5 pontos)' in relatorio(analises)


def test_nota_final_do_concurso_e_apenas_informativa(raizes, caplog):
    provas, analises = raizes
    criar(provas, '30', cabecalho='RESULTADO FINAL DO CONCURSO\n')

    with caplog.at_level(logging.WARNING):
        analisar(provas, analises)

    texto = relatorio(analises)
    assert 'Atenção' not in texto
    assert 'inclui outras fases' in texto
    assert 'diverge' not in caplog.text


def test_erro_na_leitura_do_resultado_nao_bloqueia_a_analise(raizes, caplog):
    provas, analises = raizes
    criar(provas, '4', {'identificador': '999999'})

    with caplog.at_level(logging.WARNING):
        assert analisar(provas, analises) == 0

    assert (analises / 'sintetico' / 'desempenho_por_disciplina.csv').exists()
    assert 'inscrição 999999 não encontrada' in relatorio(analises)
    assert 'inscrição 999999 não encontrada' in caplog.text
