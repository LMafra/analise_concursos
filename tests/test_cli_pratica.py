import json
from pathlib import Path

import pytest
from conftest import criar_concurso
from servidor_open_notebook import ServidorOpenNotebook

from concursos.cli import main
from concursos.pratica_tec import ARQUIVO_ERROS, PASTA_PRATICA

CONFIG = {
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
}

EXPORTACAO = {
    'app': 'tec-erros',
    'v': 1,
    'dev': 'd1',
    'erros': [
        {
            'id': 'q1',
            'fp': 'texto',
            'd': '2026-11-02',
            'ds': ['2026-11-02T10:00:00-03:00', '2026-11-03T10:00:00-03:00'],
            'origem': 'tempo_real',
            'mat': 'Conhecimentos',
            'ass': 'Assunto qualquer',
            'enun': 'Texto',
        }
    ],
    'cads': [],
}


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    pasta = criar_concurso(raiz / 'provas', 'alfa', CONFIG, {'gabarito.txt': '1 A\n2 B\n3 C\n4 D\n'})
    for candidato in ('zuleica', 'yolanda'):
        (pasta / 'candidatos' / candidato).mkdir(parents=True)
        (pasta / 'candidatos' / candidato / 'respostas.txt').write_text(
            '1 A\n2 B\n3 D\n4 D\n', encoding='utf-8'
        )
    monkeypatch.chdir(raiz)
    assert main(['--yes', '--no-open', '--all-candidates']) == 0
    return raiz


def com_pratica(projeto: Path, extra: str = '') -> None:
    config = projeto / '.concurso' / 'config.toml'
    atual = config.read_text(encoding='utf-8') if config.exists() else ''
    config.parent.mkdir(exist_ok=True)
    config.write_text(atual + f'\n[pratica]\nentrada_tec = "tec"\n{extra}', encoding='utf-8')


def exportacao(pasta: Path, nome: str = 'tec-erros-d1-2026-11-03.json', dados: dict | None = None) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / nome
    caminho.write_text(json.dumps(dados or EXPORTACAO, ensure_ascii=False), encoding='utf-8')
    return caminho


def erros_tec(projeto: Path, candidato: str = 'zuleica') -> Path:
    return projeto / 'analises' / candidato / PASTA_PRATICA / ARQUIVO_ERROS


def test_sem_secao_pratica_a_analise_nao_cria_a_pasta(projeto):
    assert not (projeto / 'analises' / 'zuleica' / PASTA_PRATICA).exists()


def test_import_copia_para_a_entrada_e_analisa(projeto, tmp_path):
    com_pratica(projeto)
    arquivo = exportacao(tmp_path / 'downloads')

    assert main(['--yes', '--no-open', 'pratica', 'import', str(arquivo), '--candidate', 'zuleica']) == 0

    assert (projeto / 'tec' / arquivo.name).exists()
    linhas = erros_tec(projeto).read_text(encoding='utf-8').splitlines()
    assert linhas[1].startswith('q1,2,2026-11-02,2026-11-03,tempo_real,')
    assert not erros_tec(projeto, 'yolanda').exists()


def test_a_analise_padrao_le_a_pasta_de_entrada(projeto):
    com_pratica(projeto)
    exportacao(projeto / 'tec')

    assert main(['--yes', '--no-open', '--candidate', 'zuleica']) == 0

    assert erros_tec(projeto).exists()


def test_import_sem_secao_pratica_explica_como_ligar(projeto, tmp_path, capsys):
    assert main(['--yes', '--no-open', 'pratica', 'import', str(exportacao(tmp_path))]) == 1

    erro = capsys.readouterr().err
    assert '[pratica]' in erro and 'entrada_tec' in erro


def test_import_recusa_arquivo_que_nao_e_do_tec_erros(projeto, tmp_path, capsys):
    com_pratica(projeto)
    arquivo = exportacao(tmp_path, 'outro.json', {'app': 'outro', 'v': 1})

    assert main(['--yes', '--no-open', 'pratica', 'import', str(arquivo), '--candidate', 'zuleica']) == 1

    assert not (projeto / 'tec').exists()
    assert 'tec-erros' in capsys.readouterr().err


def test_import_com_dry_run_nao_copia(projeto, tmp_path, capsys):
    com_pratica(projeto)
    arquivo = exportacao(tmp_path)

    assert main(['--yes', '--dry-run', 'pratica', 'import', str(arquivo), '--candidate', 'zuleica']) == 0

    assert not (projeto / 'tec').exists()
    assert 'copiaria' in capsys.readouterr().out


def test_todos_os_candidatos_so_o_da_pratica_recebe(projeto):
    com_pratica(projeto, 'candidato = "yolanda"\n')
    exportacao(projeto / 'tec')

    assert main(['--yes', '--no-open', '--all-candidates']) == 0

    assert erros_tec(projeto, 'yolanda').exists()
    assert not erros_tec(projeto).exists()


def test_secao_pratica_invalida_e_erro_do_usuario(projeto, capsys):
    com_pratica(projeto, 'pasta = "x"\n')

    assert main(['--yes', '--no-open', '--candidate', 'zuleica']) == 1

    assert '[pratica]' in capsys.readouterr().err


@pytest.fixture
def servidor():
    servidor = ServidorOpenNotebook()
    yield servidor
    servidor.desligar()


def test_caderno_de_erros_so_vai_ao_open_notebook_com_consentimento(projeto, servidor):
    assert main(['--yes', 'notebook', 'enable', '--url', servidor.url]) == 0
    com_pratica(projeto)
    exportacao(projeto / 'tec')

    assert main(['--yes', '--no-open', '--candidate', 'zuleica']) == 0
    assert not any(n['name'].startswith('Caderno de erros') for n in servidor.notebooks.values())

    com_pratica_e_open_notebook = (projeto / '.concurso' / 'config.toml').read_text(encoding='utf-8')
    (projeto / '.concurso' / 'config.toml').write_text(
        com_pratica_e_open_notebook.replace(
            'entrada_tec = "tec"', 'entrada_tec = "tec"\nopen_notebook = true'
        ),
        encoding='utf-8',
    )
    assert main(['--yes', '--no-open', '--candidate', 'zuleica']) == 0
    assert any(n['name'].startswith('Caderno de erros') for n in servidor.notebooks.values())


def test_indice_ganha_a_secao_pratica_no_tec(projeto):
    com_pratica(projeto)
    exportacao(projeto / 'tec')

    assert main(['--yes', '--no-open', '--candidate', 'zuleica']) == 0

    indice = (projeto / 'analises' / 'zuleica' / 'index.html').read_text(encoding='utf-8')
    assert '<section id="pratica">\n<h2>Prática no TEC</h2>' in indice
    assert 'Questões que você errou mais de uma vez' in indice


def test_import_de_planilha_cria_a_secao_e_analisa(projeto, tmp_path):
    planilha = tmp_path / 'downloads' / 'historico.csv'
    planilha.parent.mkdir()
    planilha.write_text(
        'Disciplina;Assunto;Questão;Resultado\nConhecimentos;Assunto qualquer;#4321;Errado\n'
        'Conhecimentos;Assunto qualquer;#4322;Certo\n',
        encoding='utf-8',
    )

    assert main(['--yes', '--no-open', 'pratica', 'import', str(planilha), '--candidate', 'zuleica']) == 0

    assert '[pratica]' in (projeto / '.concurso' / 'config.toml').read_text(encoding='utf-8')
    assert [p.name.startswith('tec-erros-planilha-historico-') for p in (projeto / 'tec').iterdir()] == [True]
    assert erros_tec(projeto).read_text(encoding='utf-8').splitlines()[1].startswith('q4321,')


def test_simulado_com_os_erros_tem_o_gabarito_no_fim(projeto):
    com_pratica(projeto)
    dados = json.loads(json.dumps(EXPORTACAO))
    dados['erros'][0] |= {'gab': 'C', 'marc': 'E', 'enun': 'Texto <com> marcação'}
    exportacao(projeto / 'tec', dados=dados)

    assert main(['--yes', '--no-open', '--candidate', 'zuleica']) == 0

    pagina = (projeto / 'analises' / 'zuleica' / PASTA_PRATICA / 'simulado_tec.html').read_text(
        encoding='utf-8'
    )
    assert 'Texto &lt;com&gt; marcação' in pagina
    assert pagina.index('Texto &lt;com&gt;') < pagina.index('<h2>Gabarito</h2>')
    assert 'Questão 1: C (você marcou E)' in pagina
