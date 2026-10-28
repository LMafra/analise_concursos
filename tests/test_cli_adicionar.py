from pathlib import Path

import pytest
import yaml
from conftest import analisar, com_edital_minimo

from concursos.cli import main
from concursos.concurso_config import gravar_dados

GABARITO_FGV = '# FGV - Gabarito definitivo\n1 A\n2 B\n3 C\n4 D\n5 E\n6 A\n'
RESPOSTAS = '1 A\n2 B\n3 D\n4 D\n5 -\n6 A\n'


def criar_pasta(provas: Path, arquivos: dict[str, str], nome: str = 'novo') -> Path:
    pasta = provas / nome
    pasta.mkdir()
    for nome_arquivo, conteudo in arquivos.items():
        (pasta / nome_arquivo).write_text(conteudo, encoding='utf-8')
    return pasta


def adicionar(pasta: Path, *extra: str) -> int:
    return main(['adicionar', str(pasta), *extra])


def roteirizar(monkeypatch, *respostas: str) -> list[str]:
    """Simula o teclado; devolve a lista de prompts exibidos."""
    fila = list(respostas)
    prompts: list[str] = []

    def entrada(prompt: str = '') -> str:
        prompts.append(prompt)
        if not fila:
            raise AssertionError(f'pergunta inesperada: {prompt!r}')
        return fila.pop(0)

    monkeypatch.setattr('builtins.input', entrada)
    return prompts


def ler_config(pasta: Path) -> dict:
    return yaml.safe_load((pasta / 'concurso.yaml').read_text(encoding='utf-8'))


def test_caminho_feliz_grava_config_aceita_pelo_analisar(raizes, monkeypatch, capsys):
    provas, analises = raizes
    pasta = criar_pasta(provas, {'gab.txt': GABARITO_FGV, 'minhas.txt': RESPOSTAS})
    prompts = roteirizar(monkeypatch, '', '', 's')

    assert adicionar(pasta) == 0
    assert len(prompts) == 3

    config = ler_config(pasta)
    assert config['banca'] == 'fgv'
    assert config['formato'] == 'multipla_escolha'
    assert config['pontuacao'] == 'simples'
    assert config['provas'] == {
        'unica': {'gabarito': {'arquivo': 'gab.txt', 'status': 'definitivo'}, 'itens': [1, 6]}
    }
    assert config['respostas'] == {'arquivo': 'minhas.txt'}
    assert 'gab.txt' in capsys.readouterr().out
    gravar_dados(pasta, com_edital_minimo(pasta, config))
    assert analisar(provas, analises) == 0
    assert (analises / 'novo' / 'desempenho_por_disciplina.csv').exists()


def test_recusar_confirmacao_nao_grava(raizes, monkeypatch):
    provas, _ = raizes
    pasta = criar_pasta(provas, {'gab.txt': GABARITO_FGV, 'minhas.txt': RESPOSTAS})
    roteirizar(monkeypatch, 'n')

    assert adicionar(pasta) == 1
    assert not (pasta / 'concurso.yaml').exists()


def test_cebraspe_gera_uma_prova_por_gabarito_com_regra_cebraspe(raizes, monkeypatch):
    provas, analises = raizes
    pasta = criar_pasta(
        provas,
        {
            'g1.txt': '# CEBRASPE - CONHECIMENTOS GERAIS - gabarito definitivo\n1 C\n2 E\n3 C\n',
            'g2.txt': (
                '# CEBRASPE - gabarito definitivo\n'
                '# CARGO 2: ANALISTA DE TI – ESPECIALIDADE: DADOS - CÓDIGO: X-02\n'
                '4 E\n5 X\n6 C\n'
            ),
            'respostas.txt': '1 C\n2 C\n3 C\n4 E\n5 -\n6 -\n',
        },
    )
    roteirizar(monkeypatch)

    assert adicionar(pasta, '--aceitar-sugestoes') == 0

    config = ler_config(pasta)
    assert (config['banca'], config['formato'], config['pontuacao']) == (
        'cebraspe',
        'certo_errado',
        'cebraspe',
    )
    assert config['provas']['cg']['itens'] == [1, 3]
    assert config['provas']['ce']['itens'] == [4, 6]
    assert config['cargo'] == 'CARGO 2: ANALISTA DE TI – ESPECIALIDADE: DADOS'
    assert analisar(provas, analises) == 0


def test_duplicado_por_hash_pergunta_qual_manter(raizes, monkeypatch, capsys):
    provas, _ = raizes
    pasta = criar_pasta(
        provas, {'gabarito.txt': GABARITO_FGV, 'respostas.txt': RESPOSTAS, 'respostas (1).txt': RESPOSTAS}
    )
    roteirizar(monkeypatch, '', 's')

    assert adicionar(pasta) == 0

    config = ler_config(pasta)
    assert config['respostas'] == {'arquivo': 'respostas.txt'}
    assert config['ignorar'] == ['respostas (1).txt']
    assert 'idêntic' in capsys.readouterr().out


def test_preliminar_e_definitivo_juntos_prefere_definitivo(raizes, monkeypatch):
    provas, _ = raizes
    pasta = criar_pasta(
        provas,
        {
            'gab_prel.txt': GABARITO_FGV.replace('definitivo', 'preliminar').replace('6 A', '6 B'),
            'gab_def.txt': GABARITO_FGV,
            'respostas.txt': RESPOSTAS,
        },
    )
    roteirizar(monkeypatch)

    assert adicionar(pasta, '--aceitar-sugestoes') == 0

    config = ler_config(pasta)
    assert config['provas']['unica']['gabarito'] == {'arquivo': 'gab_def.txt', 'status': 'definitivo'}
    assert config['ignorar'] == ['gab_prel.txt']


def test_arquivo_desconhecido_pergunta_o_papel(raizes, monkeypatch):
    provas, _ = raizes
    pasta = criar_pasta(
        provas, {'gabarito.txt': GABARITO_FGV, 'respostas.txt': RESPOSTAS, 'notas.txt': 'estudar'}
    )
    prompts = roteirizar(monkeypatch, '1', 's')

    assert adicionar(pasta) == 0
    assert ler_config(pasta)['ignorar'] == ['notas.txt']
    assert len(prompts) == 2


@pytest.mark.parametrize(
    ('arquivos', 'mensagem'),
    [
        ({'gabarito.txt': GABARITO_FGV, 'respostas.txt': RESPOSTAS, 'notas.txt': 'estudar'}, 'notas.txt'),
        ({'gabarito.txt': GABARITO_FGV.replace('FGV - ', ''), 'respostas.txt': RESPOSTAS}, 'banca'),
    ],
    ids=['arquivo_desconhecido', 'banca_nao_detectada'],
)
def test_modo_nao_interativo_falha_diante_de_ambiguidade(raizes, monkeypatch, caplog, arquivos, mensagem):
    provas, _ = raizes
    pasta = criar_pasta(provas, arquivos)
    roteirizar(monkeypatch)

    assert adicionar(pasta, '--aceitar-sugestoes') == 1
    assert not (pasta / 'concurso.yaml').exists()
    assert mensagem in caplog.text
    assert '--aceitar-sugestoes' in caplog.text


def test_recadastro_mostra_diff_e_preserva_ajustes_manuais(raizes, monkeypatch, capsys):
    provas, _ = raizes
    pasta = criar_pasta(
        provas,
        {'gabarito.txt': GABARITO_FGV.replace('definitivo', 'preliminar'), 'respostas.txt': RESPOSTAS},
    )
    roteirizar(monkeypatch)
    assert adicionar(pasta, '--aceitar-sugestoes') == 0
    config = ler_config(pasta)
    config['provas']['unica']['disciplinas'] = [{'inicio': 1, 'fim': 6, 'disciplina': 'Português'}]
    config['correcao'] = {'variantes': ['B3-08-A']}
    config |= {'data_prova': '2026-02-22', 'nivel': 'federal', 'escolaridade': 'medio'}
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')
    (pasta / 'gabarito.txt').write_text(GABARITO_FGV, encoding='utf-8')
    capsys.readouterr()

    roteirizar(monkeypatch, 'n')
    assert adicionar(pasta) == 1
    saida = capsys.readouterr().out
    assert '-      status: preliminar' in saida
    assert '+      status: definitivo' in saida
    assert ler_config(pasta)['provas']['unica']['gabarito']['status'] == 'preliminar'

    roteirizar(monkeypatch, 's')
    assert adicionar(pasta) == 0
    novo = ler_config(pasta)['provas']['unica']
    assert novo['gabarito']['status'] == 'definitivo'
    assert novo['disciplinas'] == [{'inicio': 1, 'fim': 6, 'disciplina': 'Português'}]
    preservados = {
        chave: ler_config(pasta)[chave] for chave in ('correcao', 'data_prova', 'nivel', 'escolaridade')
    }
    assert preservados == {
        'correcao': {'variantes': ['B3-08-A']},
        'data_prova': '2026-02-22',
        'nivel': 'federal',
        'escolaridade': 'medio',
    }


def test_recadastro_sem_mudancas_nao_pergunta(raizes, monkeypatch, capsys):
    provas, _ = raizes
    pasta = criar_pasta(provas, {'gabarito.txt': GABARITO_FGV, 'respostas.txt': RESPOSTAS})
    roteirizar(monkeypatch)
    assert adicionar(pasta, '--aceitar-sugestoes') == 0

    roteirizar(monkeypatch)
    assert adicionar(pasta) == 0
    assert 'sem mudanças' in capsys.readouterr().out


def test_pasta_inexistente_falha_com_mensagem_clara(raizes, caplog):
    provas, _ = raizes
    assert adicionar(provas / 'nao_existe') == 1
    assert 'nao_existe' in caplog.text


def test_txt_sem_sinal_no_nome_pergunta_se_e_gabarito_ou_respostas(raizes, monkeypatch, capsys):
    provas, _ = raizes
    sem_titulo = GABARITO_FGV.replace('# FGV - Gabarito definitivo', '# FGV')
    pasta = criar_pasta(provas, {'definitivo.txt': sem_titulo, 'respostas.txt': RESPOSTAS})
    roteirizar(monkeypatch, '1', '', 's')

    assert adicionar(pasta) == 0

    config = ler_config(pasta)
    assert config['provas']['unica']['gabarito'] == {'arquivo': 'definitivo.txt', 'status': 'definitivo'}
    assert config['respostas'] == {'arquivo': 'respostas.txt'}
    assert 'definitivo.txt: é gabarito ou respostas?' in capsys.readouterr().out


def test_sem_tty_aceita_a_sugestao_do_txt_ambiguo_e_avisa(raizes, monkeypatch, caplog):
    provas, _ = raizes
    pasta = criar_pasta(provas, {'gab.txt': GABARITO_FGV, 'respostas.txt': RESPOSTAS})
    roteirizar(monkeypatch)

    assert adicionar(pasta, '--aceitar-sugestoes') == 0

    assert ler_config(pasta)['provas']['unica']['gabarito']['arquivo'] == 'gab.txt'
    assert 'gab.txt: tratado como gabarito' in caplog.text


def test_sem_edital_grava_e_avisa_que_fica_incompleto(raizes, monkeypatch, capsys):
    provas, _ = raizes
    pasta = criar_pasta(provas, {'gabarito.txt': GABARITO_FGV, 'respostas.txt': RESPOSTAS})
    roteirizar(monkeypatch)

    assert adicionar(pasta, '--aceitar-sugestoes') == 0

    assert 'edital' not in ler_config(pasta)
    assert 'nenhum edital; o concurso ficará incompleto' in capsys.readouterr().out
