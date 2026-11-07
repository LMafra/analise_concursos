import json
from pathlib import Path

import pytest
from conftest import criar_concurso
from servidor_open_notebook import ServidorOpenNotebook

from concursos.cli import main
from concursos.config.contexto import ler_toml

CONFIG = {
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
}


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    for nome in ('alfa', 'beta'):
        pasta = criar_concurso(raiz / 'provas', nome, CONFIG, {'gabarito.txt': '1 A\n2 B\n3 C\n4 D\n'})
        for candidato, respostas in (
            ('zuleica', '1 A\n2 B\n3 D\n4 D\n'),
            ('yolanda', '1 B\n2 B\n3 C\n4 D\n'),
        ):
            (pasta / 'candidatos' / candidato).mkdir(parents=True)
            (pasta / 'candidatos' / candidato / 'respostas.txt').write_text(respostas, encoding='utf-8')
    monkeypatch.chdir(raiz)
    assert main(['--yes', '--no-open', '--all-candidates']) == 0
    return raiz


@pytest.fixture
def servidor():
    servidor = ServidorOpenNotebook()
    yield servidor
    servidor.desligar()


def secao(home: Path) -> dict:
    return ler_toml(home / 'config.toml').get('open_notebook', {})


def ligar(url: str) -> None:
    assert main(['--yes', 'notebook', 'enable', '--url', url]) == 0


def test_enable_com_yes_grava_consentimento_e_mostra_o_que_vai(home_isolada, servidor, capsys):
    ligar(servidor.url)

    assert secao(home_isolada) == {
        **secao(home_isolada),
        'enabled': True,
        'consentimento': True,
        'url': servidor.url,
    }
    saida = capsys.readouterr().out
    assert 'relatorio.md' in saida and 'pseudônimo' in saida
    assert 'senha' not in json.dumps(secao(home_isolada))


def test_enable_sem_terminal_e_sem_yes_recusa_sem_gravar(home_isolada, servidor, capsys):
    assert main(['notebook', 'enable', '--url', servidor.url]) == 1

    assert secao(home_isolada) == {}
    erro = capsys.readouterr().err
    assert 'dica:' in erro and '--yes' in erro


def test_enable_com_dry_run_nao_grava(home_isolada, servidor):
    assert main(['--yes', '--dry-run', 'notebook', 'enable', '--url', servidor.url]) == 0

    assert not (home_isolada / 'config.toml').exists()


def test_disable_desliga_sem_apagar_a_url(home_isolada, servidor):
    ligar(servidor.url)

    assert main(['notebook', 'disable']) == 0

    assert secao(home_isolada)['enabled'] is False
    assert secao(home_isolada)['url'] == servidor.url


def test_sync_desligado_explica_como_ligar(projeto, capsys):
    assert main(['notebook', 'sync', '--candidate', 'zuleica']) == 1

    assert 'notebook enable' in capsys.readouterr().err


def test_sync_imprime_o_resumo_e_sai_com_zero(projeto, servidor, capsys):
    ligar(servidor.url)
    capsys.readouterr()

    assert main(['notebook', 'sync', '--candidate', 'zuleica']) == 0

    saida = capsys.readouterr().out
    assert 'notebooks: 3 criados' in saida
    assert sorted(n['name'] for n in servidor.notebooks.values()) == [
        'Consolidado — candidato 1',
        'alfa — candidato 1',
        'beta — candidato 1',
    ]


def test_sync_all_candidates_usa_um_pseudonimo_por_candidato(projeto, servidor):
    ligar(servidor.url)

    assert main(['notebook', 'sync', '--all-candidates']) == 0

    rotulos = {n['name'].split(' — ')[1] for n in servidor.notebooks.values()}
    assert rotulos == {'candidato 1', 'candidato 2'}


def test_sync_de_um_concurso(projeto, servidor):
    ligar(servidor.url)

    assert main(['notebook', 'sync', '--candidate', 'zuleica', '--concurso', 'alfa']) == 0

    assert [n['name'] for n in servidor.notebooks.values()] == ['alfa — candidato 1']


def test_sync_com_falha_parcial_sai_com_um(projeto, servidor, capsys):
    ligar(servidor.url)
    servidor.falhas[('POST', r'/api/notes$')] = 500

    assert main(['notebook', 'sync', '--candidate', 'zuleica']) == 1

    assert 'falha:' in capsys.readouterr().out


def test_sync_com_instancia_fora_do_ar_sai_com_dois(projeto, capsys):
    ligar('http://127.0.0.1:1')

    assert main(['notebook', 'sync', '--candidate', 'zuleica']) == 2

    erro = capsys.readouterr().err
    assert 'docker compose' in erro and 'Traceback' not in erro


def test_sync_com_dry_run_nao_chama_a_rede(projeto, servidor, capsys):
    ligar(servidor.url)
    pedidos = len(servidor.pedidos)

    assert main(['--dry-run', 'notebook', 'sync', '--candidate', 'zuleica']) == 0

    assert len(servidor.pedidos) == pedidos
    assert 'alfa' in capsys.readouterr().out


def mtimes(pasta: Path) -> dict[str, int]:
    return {str(p.relative_to(pasta)): p.stat().st_mtime_ns for p in sorted(pasta.rglob('*')) if p.is_file()}


def test_analise_sincroniza_sozinha_quando_ligado(projeto, servidor):
    ligar(servidor.url)

    assert main(['--yes', '--no-open', '--force', '--candidate', 'zuleica']) == 0

    assert len(servidor.notebooks) == 3


def test_analise_sem_mudanca_nao_escreve_no_open_notebook_nem_em_analises(projeto, servidor):
    ligar(servidor.url)
    assert main(['--yes', '--no-open', '--all-candidates']) == 0
    escritas = len(servidor.escritas)
    antes = mtimes(projeto / 'analises')

    assert main(['--yes', '--no-open', '--all-candidates']) == 0

    assert len(servidor.escritas) == escritas
    assert mtimes(projeto / 'analises') == antes


def test_analise_offline_nao_chama_a_instancia(projeto, servidor):
    ligar(servidor.url)

    assert main(['--yes', '--no-open', '--offline', '--force', '--candidate', 'zuleica']) == 0

    assert servidor.pedidos == []


def test_analise_dry_run_nao_chama_a_instancia(projeto, servidor):
    ligar(servidor.url)

    assert main(['--yes', '--dry-run', '--candidate', 'zuleica']) == 0

    assert servidor.pedidos == []


def test_instancia_fora_do_ar_vira_aviso_e_a_analise_sai_com_zero(projeto, caplog):
    ligar('http://127.0.0.1:1')

    assert main(['--yes', '--no-open', '--force', '--candidate', 'zuleica']) == 0

    assert 'open-notebook' in caplog.text and 'docker compose' in caplog.text


def test_desligado_a_analise_nao_chama_a_instancia(projeto, servidor):
    ligar(servidor.url)
    assert main(['notebook', 'disable']) == 0

    assert main(['--yes', '--no-open', '--force', '--candidate', 'zuleica']) == 0

    assert servidor.pedidos == []


def recomendacoes(projeto: Path) -> Path:
    return projeto / 'analises' / 'zuleica' / 'consolidado' / 'recomendacoes_estudo.md'


def com_biblioteca(projeto: Path, disciplina: str = 'Conhecimentos') -> None:
    catalogo = projeto / 'estante.md'
    catalogo.write_text(
        '## TI - Banco de Dados › SQL e Teoria\n\n| Título | Autor | Arquivo |\n|---|---|---|\n'
        '| SQL Cookbook | Anthony Molinaro | `SQL Cookbook - Anthony Molinaro.pdf` |\n',
        encoding='utf-8',
    )
    (projeto / '.concurso' / 'biblioteca.yaml').write_text(
        f'catalogo: estante.md\ndisciplinas:\n  {disciplina}: ["TI - Banco de Dados › SQL e Teoria"]\n',
        encoding='utf-8',
    )


def test_sem_biblioteca_nem_legislacao_nao_ha_recomendacoes(projeto):
    assert not recomendacoes(projeto).exists()
    indice = (projeto / 'analises' / 'zuleica' / 'index.html').read_text(encoding='utf-8')
    assert 'id="onde-estudar"' not in indice


def test_com_biblioteca_a_analise_grava_recomendacoes_e_a_secao_sem_rede(projeto, servidor):
    ligar(servidor.url)
    com_biblioteca(projeto)

    assert main(['--yes', '--no-open', '--offline', '--candidate', 'zuleica']) == 0

    assert recomendacoes(projeto).read_text(encoding='utf-8').startswith('# Onde estudar')
    indice = (projeto / 'analises' / 'zuleica' / 'index.html').read_text(encoding='utf-8')
    assert '<section id="onde-estudar">\n<h2>Onde estudar</h2>' in indice
    assert servidor.pedidos == []
    antes = mtimes(projeto / 'analises')
    assert main(['--yes', '--no-open', '--offline', '--candidate', 'zuleica']) == 0
    assert mtimes(projeto / 'analises') == antes


def test_disciplina_fora_da_taxonomia_e_erro_do_usuario(projeto, capsys):
    (projeto / '.concurso' / 'taxonomia.yaml').write_text(
        'Conhecimentos:\n  bloco: geral\n', encoding='utf-8'
    )
    com_biblioteca(projeto, 'Banco de dados')

    assert main(['--yes', '--no-open', '--candidate', 'zuleica']) == 1

    erro = capsys.readouterr().err
    assert "'Banco de dados' fora da taxonomia" in erro and 'biblioteca.yaml' in erro
