from pathlib import Path

import yaml
from conftest import analisar, criar_concurso, ler_csv

from concursos.cli import main
from concursos.concurso_config import com_gabarito_definitivo

PRELIMINAR = '# FGV - Gabarito preliminar\n1 A\n2 B\n3 C\n4 D\n5 E\n6 A\n'
DEFINITIVO = '# FGV - Gabarito definitivo\n1 A\n2 B\n3 D\n4 X\n5 E\n6 A\n'
RESPOSTAS = '1 A\n2 B\n3 D\n4 D\n5 -\n6 A\n'
SELO = 'Gabarito preliminar (provisório)'


def criar(provas: Path, gabarito: str = 'gab_prel.txt', **extra) -> Path:
    config = {
        'nome': 'sintetico',
        'banca': 'fgv',
        'formato': 'multipla_escolha',
        'pontuacao': 'simples',
        'provas': {'unica': {'gabarito': {'arquivo': gabarito, 'status': 'preliminar'}, 'itens': [1, 6]}},
        'respostas': {'arquivo': 'respostas.txt'},
    } | extra
    return criar_concurso(provas, 'sintetico', config, {gabarito: PRELIMINAR, 'respostas.txt': RESPOSTAS})


def ler_config(pasta: Path) -> dict:
    return yaml.safe_load((pasta / 'concurso.yaml').read_text(encoding='utf-8'))


def relatorio(analises: Path) -> str:
    return (analises / 'sintetico' / 'relatorio.md').read_text(encoding='utf-8')


def status(provas: Path, capsys) -> str:
    capsys.readouterr()
    assert main(['status', '--provas', str(provas)]) == 0
    return capsys.readouterr().out


def test_definitivo_novo_substitui_o_preliminar(raizes):
    provas, analises = raizes
    pasta = criar(provas)
    assert analisar(provas, analises) == 0
    assert SELO in relatorio(analises)

    (pasta / 'gab_def.txt').write_text(DEFINITIVO, encoding='utf-8')
    assert analisar(provas, analises) == 0

    config = ler_config(pasta)
    assert config['provas']['unica']['gabarito'] == {'arquivo': 'gab_def.txt', 'status': 'definitivo'}
    assert 'gab_prel.txt' in config['ignorar']
    evento = config['historico'][-1]
    assert (evento['tipo'], evento['prova'], evento['anterior'], evento['novo']) == (
        'gabarito_definitivo',
        'unica',
        'gab_prel.txt',
        'gab_def.txt',
    )
    snapshots = list((analises / 'sintetico' / 'historico').glob('*/relatorio.md'))
    assert len(snapshots) == 1 and SELO in snapshots[0].read_text(encoding='utf-8')

    diff = ler_csv(analises / 'sintetico' / 'diff_gabarito.csv')
    assert list(diff.columns) == [
        'prova',
        'questao',
        'gabarito_preliminar',
        'gabarito_definitivo',
        'mudanca',
        'resposta',
        'acerto_antes',
        'acerto_depois',
    ]
    assert diff.values.tolist() == [
        ['unica', 3, 'C', 'D', 'alterada', 'D', False, True],
        ['unica', 4, 'D', '', 'anulada', 'D', True, True],
    ]
    texto = relatorio(analises)
    assert '## Preliminar → Definitivo' in texto
    assert 'Acertos: 4 → 5' in texto
    assert SELO not in texto
    desempenho = ler_csv(analises / 'sintetico' / 'desempenho_por_disciplina.csv')
    assert desempenho['acertos'].tolist() == [5]


def test_diff_e_recalculado_com_as_respostas_atuais_e_sobrevive_a_reanalise(raizes):
    provas, analises = raizes
    pasta = criar(provas)
    analisar(provas, analises)
    (pasta / 'gab_def.txt').write_text(DEFINITIVO, encoding='utf-8')
    analisar(provas, analises)

    (analises / 'sintetico' / 'diff_gabarito.csv').unlink()
    (pasta / 'respostas.txt').write_text(RESPOSTAS.replace('5 -', '5 E'), encoding='utf-8')
    assert analisar(provas, analises) == 0

    assert (analises / 'sintetico' / 'diff_gabarito.csv').exists()
    assert 'Acertos: 5 → 6' in relatorio(analises)


def test_sobrescrever_com_mesmo_nome_e_status_novo_dispara_a_troca(raizes):
    provas, analises = raizes
    pasta = criar(provas, gabarito='gabarito.txt')
    analisar(provas, analises)

    (pasta / 'gabarito.txt').write_text(DEFINITIVO, encoding='utf-8')
    assert analisar(provas, analises) == 0

    config = ler_config(pasta)
    assert config['provas']['unica']['gabarito'] == {'arquivo': 'gabarito.txt', 'status': 'definitivo'}
    assert 'gabarito.txt' not in config.get('ignorar', [])
    assert config['historico'][-1]['novo'] == 'gabarito.txt'
    assert (analises / 'sintetico' / 'diff_gabarito.csv').exists()
    assert '## Preliminar → Definitivo' in relatorio(analises)


def test_definitivo_de_outro_cargo_deixa_desatualizado(raizes, capsys):
    provas, analises = raizes
    cabecalho = '# CEBRASPE - gabarito {status}\n# {cargo}\n'
    config = {
        'nome': 'sintetico',
        'banca': 'cebraspe',
        'cargo': 'CARGO 2: ANALISTA',
        'formato': 'certo_errado',
        'pontuacao': 'cebraspe',
        'provas': {'ce': {'gabarito': {'arquivo': 'g.txt', 'status': 'preliminar'}, 'itens': [1, 3]}},
        'respostas': {'arquivo': 'respostas.txt'},
    }
    pasta = criar_concurso(
        provas,
        'sintetico',
        config,
        {
            'g.txt': cabecalho.format(status='preliminar', cargo='CARGO 2: ANALISTA') + '1 C\n2 E\n3 C\n',
            'respostas.txt': '1 C\n2 C\n3 C\n',
        },
    )
    analisar(provas, analises)
    original = ler_config(pasta)

    (pasta / 'g_def.txt').write_text(
        cabecalho.format(status='definitivo', cargo='CARGO 5: OUTRO') + '1 E\n2 E\n3 C\n', encoding='utf-8'
    )
    assert analisar(provas, analises) == 0

    assert ler_config(pasta) == original
    saida = status(provas, capsys)
    assert 'desatualizado' in saida
    assert 'g_def.txt' in saida and 'concurso-analise add' in saida


def test_dois_definitivos_candidatos_deixam_desatualizado(raizes, capsys):
    provas, analises = raizes
    pasta = criar(provas)
    analisar(provas, analises)
    original = ler_config(pasta)

    (pasta / 'def_a.txt').write_text(DEFINITIVO, encoding='utf-8')
    (pasta / 'def_b.txt').write_text(DEFINITIVO.replace('6 A', '6 B'), encoding='utf-8')
    assert analisar(provas, analises) == 0

    assert ler_config(pasta) == original
    saida = status(provas, capsys)
    assert 'desatualizado' in saida
    assert 'def_a.txt' in saida and 'def_b.txt' in saida


def test_arquivo_nao_cadastrado_deixa_desatualizado(raizes, capsys):
    provas, analises = raizes
    pasta = criar(provas)
    (pasta / 'anotacoes.docx').write_bytes(b'x')

    saida = status(provas, capsys)

    assert 'desatualizado' in saida and 'anotacoes.docx' in saida and 'concurso-analise add' in saida


def test_com_gabarito_definitivo_troca_o_arquivo_ignora_o_anterior_e_registra_o_evento():
    dados = {
        'provas': {'unica': {'gabarito': {'arquivo': 'prel.txt', 'status': 'preliminar'}, 'itens': [1, 6]}},
        'ignorar': ['velho.txt'],
    }

    novo = com_gabarito_definitivo(dados, 'unica', 'prel.txt', 'def.txt', '2026-03-01')

    assert novo['provas']['unica'] == {
        'gabarito': {'arquivo': 'def.txt', 'status': 'definitivo'},
        'itens': [1, 6],
    }
    assert novo['ignorar'] == ['velho.txt', 'prel.txt']
    assert novo['historico'] == [
        {
            'data': '2026-03-01',
            'tipo': 'gabarito_definitivo',
            'prova': 'unica',
            'anterior': 'prel.txt',
            'novo': 'def.txt',
        }
    ]
    assert dados['provas']['unica']['gabarito']['arquivo'] == 'prel.txt'
