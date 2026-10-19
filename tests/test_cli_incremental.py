import logging

import pytest
from conftest import analisar, criar_concurso


def config(nome: str) -> dict:
    return {
        'nome': nome,
        'banca': 'fgv',
        'formato': 'multipla_escolha',
        'pontuacao': 'simples',
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 2]}},
        'respostas': {'arquivo': 'respostas.txt'},
    }


ARQUIVOS = {'gabarito.txt': '1 A\n2 B\n', 'respostas.txt': '1 A\n2 C\n'}


@pytest.fixture
def dois_concursos(raizes):
    provas, analises = raizes
    criar_concurso(provas, 'alfa', config('alfa'), ARQUIVOS)
    criar_concurso(provas, 'beta', config('beta'), ARQUIVOS)
    assert analisar(provas, analises) == 0
    return provas, analises


def analisados(caplog) -> set[str]:
    return {r.args[0] for r in caplog.records if r.msg == 'Analisando %s'}


def test_segunda_execucao_sem_mudancas_nao_reprocessa(dois_concursos, caplog):
    provas, analises = dois_concursos

    with caplog.at_level(logging.INFO):
        assert analisar(provas, analises) == 0

    assert analisados(caplog) == set()
    assert 'sem mudanças' in caplog.text


@pytest.mark.parametrize('arquivo', ['respostas.txt', 'concurso.yaml', 'revisao/questoes_revisado.csv'])
def test_mudanca_em_arquivo_reprocessa_apenas_o_concurso_afetado(dois_concursos, caplog, arquivo):
    provas, analises = dois_concursos
    caminho = provas / 'beta' / arquivo
    caminho.parent.mkdir(exist_ok=True)
    with caminho.open('a', encoding='utf-8') as saida:
        saida.write('\n# alterado\n')

    with caplog.at_level(logging.INFO):
        analisar(provas, analises)

    assert analisados(caplog) == {'beta'}


def test_forcar_reprocessa_tudo(dois_concursos, caplog):
    provas, analises = dois_concursos

    with caplog.at_level(logging.INFO):
        analisar(provas, analises, '--forcar')

    assert analisados(caplog) == {'alfa', 'beta'}


def test_concurso_especifico_processa_so_ele(raizes, caplog):
    provas, analises = raizes
    criar_concurso(provas, 'alfa', config('alfa'), ARQUIVOS)
    criar_concurso(provas, 'beta', config('beta'), ARQUIVOS)

    with caplog.at_level(logging.INFO):
        analisar(provas, analises, '--concurso', 'beta')

    assert analisados(caplog) == {'beta'}
    assert not (analises / 'alfa').exists()


def test_concurso_especifico_inexistente_falha(raizes):
    provas, analises = raizes
    criar_concurso(provas, 'alfa', config('alfa'), ARQUIVOS)

    assert analisar(provas, analises, '--concurso', 'gama') == 1


def test_falha_no_processamento_nao_deixa_manifesto_atualizado(dois_concursos, caplog):
    provas, analises = dois_concursos
    respostas = provas / 'beta' / 'respostas.txt'
    original = respostas.read_text(encoding='utf-8')
    respostas.write_text('1 Z\n', encoding='utf-8')
    assert analisar(provas, analises) == 1

    respostas.write_text(original, encoding='utf-8')
    with caplog.at_level(logging.INFO):
        analisar(provas, analises)

    assert analisados(caplog) == {'beta'}
