import logging
import tomllib
from pathlib import Path

import pytest
import yaml
from conftest import ler_csv

from concursos.cli import main

CONCURSO = {
    'nome': 'alfa',
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
}
GABARITO = '1 A\n2 B\n3 C\n4 D\n'


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    pasta = raiz / 'provas' / 'alfa'
    pasta.mkdir(parents=True)
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(CONCURSO), encoding='utf-8')
    (pasta / 'gabarito.txt').write_text(GABARITO, encoding='utf-8')
    candidato(raiz, 'alice', '1 A\n2 B\n3 C\n4 D\n')
    candidato(raiz, 'bob', '1 A\n2 C\n3 D\n4 E\n')
    monkeypatch.chdir(raiz)
    return raiz


def candidato(raiz: Path, slug: str, respostas: str, perfil: bool = True) -> Path:
    pasta = raiz / 'provas' / 'alfa' / 'candidatos' / slug
    pasta.mkdir(parents=True)
    (pasta / 'respostas.txt').write_text(respostas, encoding='utf-8')
    if perfil:
        dados = {'respostas': {'arquivo': 'respostas.txt'}}
        (pasta / 'candidato.yaml').write_text(yaml.safe_dump(dados), encoding='utf-8')
    return pasta


def acertos(raiz: Path, slug: str) -> int:
    return int(ler_csv(raiz / 'analises' / slug / 'alfa' / 'desempenho_por_disciplina.csv')['acertos'].sum())


def mtime(raiz: Path, slug: str) -> int:
    return (raiz / 'analises' / slug / 'alfa' / 'relatorio.md').stat().st_mtime_ns


def ultimo_candidato(raiz: Path) -> str | None:
    dados = tomllib.loads((raiz / '.concurso' / 'config.toml').read_text(encoding='utf-8'))
    return dados.get('candidato', {}).get('ultimo')


def test_cada_candidato_tem_a_sua_arvore_e_o_seu_consolidado(projeto):
    assert main(['--candidate', 'alice']) == 0
    assert main(['--candidate', 'bob']) == 0

    assert acertos(projeto, 'alice') == 4
    assert acertos(projeto, 'bob') == 1
    for slug in ('alice', 'bob'):
        assert (projeto / 'analises' / slug / 'consolidado' / 'comparativo_concursos.md').exists()
    assert not (projeto / 'analises' / 'alfa').exists()


def test_mudar_respostas_de_um_reprocessa_so_ele_e_o_gabarito_os_dois(projeto):
    assert main(['--all-candidates']) == 0
    antes = {slug: mtime(projeto, slug) for slug in ('alice', 'bob')}

    (projeto / 'provas/alfa/candidatos/bob/respostas.txt').write_text(
        '1 A\n2 B\n3 D\n4 E\n', encoding='utf-8'
    )
    assert main(['--all-candidates']) == 0
    assert mtime(projeto, 'alice') == antes['alice']
    assert mtime(projeto, 'bob') != antes['bob']
    assert acertos(projeto, 'bob') == 2

    depois = {slug: mtime(projeto, slug) for slug in ('alice', 'bob')}
    (projeto / 'provas/alfa/gabarito.txt').write_text('1 A\n2 B\n3 C\n4 E\n', encoding='utf-8')
    assert main(['--all-candidates']) == 0
    assert all(mtime(projeto, slug) != depois[slug] for slug in ('alice', 'bob'))


def test_sem_flag_vale_o_ultimo_candidato_usado(projeto):
    assert main(['--candidate', 'bob']) == 0
    assert ultimo_candidato(projeto) == 'bob'

    assert main(['--force']) == 0

    assert not (projeto / 'analises' / 'alice').exists()


def test_varios_candidatos_sem_escolha_pede_a_flag(projeto, capsys):
    assert main([]) == 1

    erro = capsys.readouterr().err
    assert 'alice' in erro and 'bob' in erro
    assert 'dica:' in erro and '--candidate' in erro


def test_dry_run_nao_grava_o_ultimo_candidato(projeto):
    assert main(['--candidate', 'bob', '--dry-run']) == 0

    assert not (projeto / '.concurso').exists()
    assert not (projeto / 'analises').exists()


def test_all_candidates_gera_o_comparativo_entre_candidatos(projeto):
    assert main(['--all-candidates']) == 0

    comparativo = (projeto / 'analises' / 'comparativo_candidatos.md').read_text(encoding='utf-8')
    linhas = {
        linha.split('|')[1].strip(): linha for linha in comparativo.splitlines() if linha.startswith('| ')
    }
    assert '100' in linhas['alice'] and '25' in linhas['bob']


def test_add_copia_o_arquivo_para_o_candidato_e_cria_o_perfil(projeto, tmp_path, home_isolada):
    origem = tmp_path / 'minhas_respostas.txt'
    origem.write_text('1 A\n2 B\n3 A\n4 A\n', encoding='utf-8')

    assert main(['add', str(origem), '--candidate', 'Carol Souza', '--concurso', 'alfa']) == 0

    pasta = projeto / 'provas' / 'alfa' / 'candidatos' / 'carol_souza'
    assert (pasta / 'minhas_respostas.txt').read_text(encoding='utf-8') == origem.read_text(encoding='utf-8')
    perfil = yaml.safe_load((pasta / 'candidato.yaml').read_text(encoding='utf-8'))
    assert perfil['respostas'] == {'arquivo': 'minhas_respostas.txt'}
    global_ = tomllib.loads((home_isolada / 'candidatos' / 'carol_souza.toml').read_text(encoding='utf-8'))
    assert global_ == {'nome': 'Carol Souza', 'slug': 'carol_souza'}

    assert main(['--candidate', 'carol_souza']) == 0
    assert acertos(projeto, 'carol_souza') == 2


def test_subpasta_sem_perfil_cria_o_candidato_com_aviso(projeto, caplog):
    candidato(projeto, 'dave', '1 A\n2 B\n3 C\n4 A\n', perfil=False)

    with caplog.at_level(logging.WARNING):
        assert main(['--candidate', 'dave']) == 0

    assert 'dave' in caplog.text and 'candidato.yaml' in caplog.text
    perfil = projeto / 'provas' / 'alfa' / 'candidatos' / 'dave' / 'candidato.yaml'
    assert yaml.safe_load(perfil.read_text(encoding='utf-8'))['respostas'] == {'arquivo': 'respostas.txt'}
    assert acertos(projeto, 'dave') == 3


def test_concurso_sem_respostas_do_candidato_aparece_como_pendente(projeto):
    beta = projeto / 'provas' / 'beta'
    beta.mkdir()
    (beta / 'concurso.yaml').write_text(yaml.safe_dump({**CONCURSO, 'nome': 'beta'}), encoding='utf-8')
    (beta / 'gabarito.txt').write_text(GABARITO, encoding='utf-8')
    (projeto / 'provas' / 'gama').mkdir()

    assert main(['--candidate', 'alice']) == 0

    comparativo = (projeto / 'analises' / 'alice' / 'consolidado' / 'comparativo_concursos.md').read_text(
        encoding='utf-8'
    )
    assert '| beta | incompleto | respostas não configuradas' in comparativo
    assert '| gama | incompleto |' in comparativo


def test_identificador_do_resultado_oficial_nao_e_herdado(projeto):
    from concursos.status import avaliar

    pasta = projeto / 'provas' / 'alfa'
    dados = {**CONCURSO, 'resultado_oficial': {'arquivo': 'resultado.pdf', 'identificador': '999'}}
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(dados), encoding='utf-8')
    perfil = {'respostas': {'arquivo': 'respostas.txt'}, 'resultado_oficial': {'identificador': '123'}}
    (pasta / 'candidatos' / 'alice' / 'candidato.yaml').write_text(yaml.safe_dump(perfil), encoding='utf-8')

    assert avaliar(pasta, 'alice').config.resultado_oficial.identificador == '123'
    assert avaliar(pasta, 'bob').config.resultado_oficial.identificador is None
    assert avaliar(pasta, 'bob').config.respostas_arquivo == 'candidatos/bob/respostas.txt'
