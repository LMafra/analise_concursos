import logging

from conftest import analisar, criar_concurso

from concursos.cli import main
from concursos.concurso_config import carregar_concurso
from concursos.modelo import StatusGabarito


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


def test_pasta_sem_cadastro_aparece_como_incompleta(raizes, capsys):
    provas, analises = raizes
    criar_concurso(provas, 'completo', config('completo'), ARQUIVOS)
    (provas / 'novo').mkdir()
    (provas / 'novo' / 'gabarito.pdf').write_bytes(b'%PDF')

    linhas = {linha.split()[0]: linha for linha in status(provas, capsys).splitlines()[2:]}

    assert 'incompleto' in linhas['novo']
    assert 'concurso.yaml ausente' in linhas['novo'] and 'concurso-analise add' in linhas['novo']
    assert analisar(provas, analises) == 0
    comparativo = (analises / 'consolidado' / 'comparativo_concursos.md').read_text(encoding='utf-8')
    assert '| novo | incompleto |' in comparativo


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

    banca_errada = config('banca_errada', banca='cespe')
    criar_concurso(provas, 'banca_errada', banca_errada, ARQUIVOS)
    status_errado = config('status_errado')
    status_errado['provas']['unica']['gabarito']['status'] = 'Preliminar'
    criar_concurso(provas, 'status_errado', status_errado, ARQUIVOS)

    saida = status(provas, capsys)

    assert "campo obrigatório 'banca' ausente" in saida
    assert "formato: valor 'discursiva' inválido" in saida
    assert "banca: valor 'cespe' inválido" in saida
    assert "provas.unica.gabarito.status: valor 'Preliminar' inválido (use preliminar, definitivo)" in saida


def test_arquivos_referenciados_cobrem_todo_arquivo_do_yaml_com_o_papel(raizes):
    provas, _ = raizes
    completo = config(
        'completo',
        edital={
            'arquivo': 'edital.pdf',
            'anexos': ['anexo.pdf'],
            'retificacoes': ['retificacao.pdf'],
            'manual': 'edital_manual.yaml',
        },
        resultado_oficial={'arquivo': 'resultado.pdf', 'identificador': '1'},
    )
    completo['provas']['unica']['caderno'] = 'prova.pdf'
    pasta = criar_concurso(provas, 'completo', completo, ARQUIVOS)

    assert carregar_concurso(pasta).arquivos_referenciados == {
        'gabarito.txt': 'gabarito da prova unica',
        'prova.pdf': 'caderno da prova unica',
        'respostas.txt': 'respostas',
        'anexo.pdf': 'edital',
        'edital.pdf': 'edital',
        'retificacao.pdf': 'edital',
        'edital_manual.yaml': 'edital',
        'resultado.pdf': 'resultado oficial',
    }


def test_status_do_gabarito_vira_enum_ao_carregar(raizes):
    provas, _ = raizes
    pasta = criar_concurso(provas, 'completo', config('completo'), ARQUIVOS)

    assert carregar_concurso(pasta).provas[0].gabarito.status is StatusGabarito.PRELIMINAR


EDITAL_MANUAL = """conhecimentos:
  - nome: Conhecimentos Gerais
    disciplinas:
      - nome: Língua Portuguesa
        topicos: [Crase]
"""


def test_caderno_e_resultado_oficial_ausentes_so_avisam(raizes, capsys, caplog):
    provas, analises = raizes
    sem_opcionais = config(
        'sem_opcionais',
        edital={'manual': 'edital_manual.yaml'},
        resultado_oficial={'arquivo': 'resultado.pdf', 'identificador': '1'},
    )
    sem_opcionais['provas']['unica']['caderno'] = 'prova.pdf'
    pasta = criar_concurso(
        provas, 'sem_opcionais', sem_opcionais, {**ARQUIVOS, 'edital_manual.yaml': EDITAL_MANUAL}
    )

    linha = status(provas, capsys).splitlines()[2]
    assert 'completo' in linha and 'incompleto' not in linha
    assert f'{pasta / "prova.pdf"}: arquivo ausente (caderno da prova unica)' in linha
    assert f'{pasta / "resultado.pdf"}: arquivo ausente (resultado oficial)' in linha

    with caplog.at_level(logging.WARNING):
        assert analisar(provas, analises) == 0
    assert (analises / 'sem_opcionais' / 'relatorio.md').exists()
    assert 'prova.pdf: caderno ausente' in caplog.text
