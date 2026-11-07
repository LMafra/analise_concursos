import logging

from conftest import analisar, criar_concurso, ler_csv, log_completo


def config(formato: str, pontuacao: str, fim: int) -> dict:
    return {
        'nome': 'sintetico',
        'banca': 'cebraspe' if pontuacao == 'cebraspe' else 'fgv',
        'formato': formato,
        'pontuacao': pontuacao,
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, fim]}},
        'respostas': {'arquivo': 'respostas.txt'},
    }


def desempenho_geral(analises):
    linhas = ler_csv(analises / 'sintetico' / 'desempenho_por_disciplina.csv')
    assert len(linhas) == 1
    return linhas.iloc[0]


def test_pontuacao_cebraspe_erro_anula_acerto_e_anulada_conta_como_acerto(raizes):
    provas, analises = raizes
    criar_concurso(
        provas,
        'sintetico',
        config('certo_errado', 'cebraspe', 6),
        {'gabarito.txt': '1 C\n2 E\n3 X\n4 C\n5 E\n6 C\n', 'respostas.txt': '1 C\n2 C\n3 E\n4 -\n5 E\n6 E\n'},
    )

    assert analisar(provas, analises) == 0

    linha = desempenho_geral(analises)
    assert linha[['total', 'acertos', 'erros', 'em_branco', 'anuladas']].tolist() == [6, 3, 2, 1, 1]
    assert linha['nota_liquida'] == 1
    assert linha['percentual'] == 40.0


def test_pontuacao_simples_anulada_em_branco_conta_como_acerto(raizes):
    provas, analises = raizes
    criar_concurso(
        provas,
        'sintetico',
        config('multipla_escolha', 'simples', 3),
        {'gabarito.txt': '1 A\n2 *\n3 B\n', 'respostas.txt': '1 A\n3 C\n'},
    )

    analisar(provas, analises)

    linha = desempenho_geral(analises)
    assert linha[['total', 'acertos', 'erros', 'em_branco', 'anuladas']].tolist() == [3, 2, 1, 0, 1]
    assert linha['nota_liquida'] == 2
    assert linha['percentual'] == 50.0


def test_gabarito_com_contagem_diferente_da_faixa_falha_com_mensagem_clara(raizes, caplog):
    provas, analises = raizes
    criar_concurso(
        provas,
        'sintetico',
        config('certo_errado', 'cebraspe', 4),
        {'gabarito.txt': '1 C\n2 E\n3 C\n', 'respostas.txt': '1 C\n'},
    )

    with caplog.at_level(logging.ERROR):
        assert analisar(provas, analises) == 1

    assert 'gabarito.txt' in log_completo(caplog)
    assert 'questões 1-4' in log_completo(caplog)
    assert '3 itens' in log_completo(caplog)
