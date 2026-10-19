import logging

from conftest import analisar, criar_concurso

from concursos.cli import main


def config(nome: str, **extra) -> dict:
    base = {
        'nome': nome,
        'banca': 'fgv',
        'formato': 'multipla_escolha',
        'pontuacao': 'simples',
        'provas': {
            'unica': {'gabarito': {'arquivo': 'gabarito.txt', 'status': 'preliminar'}, 'itens': [1, 2]}
        },
        'respostas': {'arquivo': 'respostas.txt'},
    }
    return base | extra


ARQUIVOS = {'gabarito.txt': '1 A\n2 B\n', 'respostas.txt': '1 A\n2 C\n'}


def status(provas, capsys) -> str:
    assert main(['status', '--provas', str(provas)]) == 0
    return capsys.readouterr().out


def test_status_lista_concursos_com_situacao_motivo_e_gabarito(raizes, capsys):
    provas, _ = raizes
    criar_concurso(provas, 'completo', config('completo'), ARQUIVOS)
    criar_concurso(provas, 'sem_respostas', config('sem_respostas'), {'gabarito.txt': '1 A\n2 B\n'})

    saida = status(provas, capsys)

    linhas = {linha.split()[0]: linha for linha in saida.splitlines()[2:]}
    assert 'completo' in linhas['completo'] and 'preliminar' in linhas['completo']
    assert 'incompleto' in linhas['sem_respostas']
    assert str(provas / 'sem_respostas' / 'respostas.txt') in linhas['sem_respostas']


def test_concurso_sem_respostas_configuradas_fica_incompleto(raizes, capsys):
    provas, _ = raizes
    sem_bloco = config('sem_bloco')
    del sem_bloco['respostas']
    criar_concurso(provas, 'sem_bloco', sem_bloco, {'gabarito.txt': '1 A\n2 B\n'})

    assert 'respostas não configuradas' in status(provas, capsys)


def test_concurso_incompleto_nao_impede_analise_dos_demais(raizes, caplog):
    provas, analises = raizes
    criar_concurso(provas, 'completo', config('completo'), ARQUIVOS)
    criar_concurso(provas, 'sem_respostas', config('sem_respostas'), {'gabarito.txt': '1 A\n2 B\n'})

    with caplog.at_level(logging.WARNING):
        assert analisar(provas, analises) == 0

    assert (analises / 'completo' / 'desempenho_por_disciplina.csv').exists()
    assert not (analises / 'sem_respostas').exists()
    assert 'sem_respostas' in caplog.text and 'incompleto' in caplog.text


def test_erro_em_um_concurso_nao_impede_os_demais_mas_retorna_falha(raizes):
    provas, analises = raizes
    criar_concurso(provas, 'a_quebrado', config('a_quebrado'), {**ARQUIVOS, 'gabarito.txt': '1 A\n'})
    criar_concurso(provas, 'b_completo', config('b_completo'), ARQUIVOS)

    assert analisar(provas, analises) == 1
    assert (analises / 'b_completo' / 'relatorio.md').exists()


def test_yaml_invalido_aponta_o_campo(raizes, capsys):
    provas, _ = raizes
    sem_banca = config('sem_banca')
    del sem_banca['banca']
    criar_concurso(provas, 'sem_banca', sem_banca, ARQUIVOS)
    formato_errado = config('formato_errado', formato='discursiva')
    criar_concurso(provas, 'formato_errado', formato_errado, ARQUIVOS)

    saida = status(provas, capsys)

    assert "campo obrigatório 'banca' ausente" in saida
    assert "formato: valor 'discursiva' inválido" in saida
