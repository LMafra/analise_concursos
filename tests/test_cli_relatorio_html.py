import re
from pathlib import Path

import pandas as pd
import pytest
import yaml
from conftest import com_edital_minimo

from concursos.cli import main

GABARITO = '1 A\n2 B\n3 C\n4 D\n'


def concurso(raiz: Path, nome: str, data: str) -> Path:
    pasta = raiz / 'provas' / nome
    pasta.mkdir(parents=True)
    config = {
        'nome': nome,
        'banca': 'fgv',
        'formato': 'multipla_escolha',
        'pontuacao': 'simples',
        'data_prova': data,
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
    }
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(com_edital_minimo(pasta, config)), encoding='utf-8')
    (pasta / 'gabarito.txt').write_text(GABARITO, encoding='utf-8')
    return pasta


def respostas(raiz: Path, nome: str, texto: str, candidato: str = 'alice') -> None:
    pasta = raiz / 'provas' / nome / 'candidatos' / candidato
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / 'respostas.txt').write_text(texto, encoding='utf-8')


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    concurso(raiz, 'alfa', '2025-03-01')
    respostas(raiz, 'alfa', '1 A\n2 B\n3 C\n4 E\n')
    monkeypatch.chdir(raiz)
    return raiz


def indice(raiz: Path) -> Path:
    return raiz / 'analises' / 'alice' / 'index.html'


def test_indice_liga_cada_concurso_ao_seu_relatorio_com_os_numeros(projeto):
    assert main(['--candidate', 'alice']) == 0

    html = indice(projeto).read_text(encoding='utf-8')
    assert 'href="alfa/relatorio.html"' in html
    assert '3 de 4' in html and '75' in html
    relatorio = projeto / 'analises' / 'alice' / 'alfa' / 'relatorio.html'
    assert '<table>' in relatorio.read_text(encoding='utf-8')


def test_percentual_do_indice_segue_a_regra_da_banca(projeto):
    pasta = projeto / 'provas' / 'gama'
    pasta.mkdir(parents=True)
    config = {
        'nome': 'gama',
        'banca': 'cebraspe',
        'formato': 'certo_errado',
        'pontuacao': 'cebraspe',
        'data_prova': '2025-06-01',
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
    }
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(com_edital_minimo(pasta, config)), encoding='utf-8')
    (pasta / 'gabarito.txt').write_text('1 C\n2 E\n3 C\n4 E\n', encoding='utf-8')
    respostas(projeto, 'gama', '1 C\n2 E\n3 C\n4 C\n')

    assert main(['--candidate', 'alice']) == 0

    html = indice(projeto).read_text(encoding='utf-8')
    linha = re.search(r'<tr><td><a href="gama/.*?</tr>', html).group(0)
    assert '3 de 4' in linha
    assert '50,0%' in linha and '2 de 4 pontos' in linha
    linha = re.search(r'<tr><td><a href="alfa/.*?</tr>', html).group(0)
    assert '75,0%' in linha


def test_indice_diz_o_que_o_app_decidiu_sozinho_e_a_origem(projeto):
    assert main(['--candidate', 'alice']) == 0

    html = indice(projeto).read_text(encoding='utf-8')
    assert 'O que o app decidiu sozinho' in html
    assert 'alfa: regra de correção do perfil da banca' in html
    assert 'regra do perfil da banca (0,50)' in html
    assert 'Avisos' in html
    assert re.search(r'Gerado por concurso-analise \d[\w.+]* em \d{2}/\d{2}/\d{4}', html)


def test_html_funciona_sem_rede(projeto):
    assert main(['--candidate', 'alice']) == 0

    for arquivo in (indice(projeto), projeto / 'analises' / 'alice' / 'alfa' / 'relatorio.html'):
        html = arquivo.read_text(encoding='utf-8')
        assert '<style>' in html
        assert not re.search(r'(?:src|href)="(?:https?:|//|/)', html)


def test_abre_na_primeira_execucao_e_sem_mudancas_so_imprime_o_caminho(projeto, navegador, capsys):
    assert main(['--candidate', 'alice']) == 0
    assert navegador == [indice(projeto)]
    mtime = indice(projeto).stat().st_mtime_ns
    capsys.readouterr()

    assert main(['--candidate', 'alice']) == 0

    assert navegador == [indice(projeto)]
    assert str(indice(projeto)) in capsys.readouterr().out
    assert indice(projeto).stat().st_mtime_ns == mtime


def test_reprocessar_abre_de_novo(projeto, navegador):
    assert main(['--candidate', 'alice']) == 0
    respostas(projeto, 'alfa', '1 A\n2 B\n3 C\n4 D\n')

    assert main(['--candidate', 'alice']) == 0

    assert len(navegador) == 2
    assert '4 de 4' in indice(projeto).read_text(encoding='utf-8')


def test_no_open_nao_abre(projeto, navegador):
    assert main(['--no-open', '--candidate', 'alice']) == 0
    assert main(['analyze', '--no-open', '--force', '--candidate', 'alice']) == 0

    assert navegador == []
    assert indice(projeto).exists()


def test_report_reabre_o_ultimo_relatorio(projeto, navegador, capsys):
    assert main(['--no-open', '--candidate', 'alice']) == 0

    assert main(['report']) == 0

    assert navegador == [indice(projeto)]
    assert str(indice(projeto)) in capsys.readouterr().out


def test_report_sem_relatorio_da_dica(projeto, capsys):
    assert main(['report', '--candidate', 'alice']) != 0

    assert 'dica:' in capsys.readouterr().err


def test_evolucao_e_gap_com_dois_concursos(projeto):
    concurso(projeto, 'beta', '2025-09-01')
    respostas(projeto, 'beta', '1 A\n2 B\n3 D\n4 E\n')

    assert main(['--candidate', 'alice']) == 0

    html = indice(projeto).read_text(encoding='utf-8')
    assert 'Evolução' in html
    assert 'consolidado/evolucao_zscore.png' in html
    assert 'Gap para o corte' in html


def test_evolucao_com_um_concurso_explica_o_minimo(projeto):
    assert main(['--candidate', 'alice']) == 0

    assert 'pelo menos 2 concursos' in indice(projeto).read_text(encoding='utf-8')


@pytest.mark.parametrize('formato', ['csv', 'parquet', 'md'])
def test_export_grava_o_consolidado_do_candidato(projeto, formato, capsys):
    concurso(projeto, 'beta', '2025-09-01')
    respostas(projeto, 'beta', '1 A\n2 B\n3 D\n4 E\n')
    assert main(['--no-open', '--candidate', 'alice']) == 0

    assert main(['export', '--format', formato]) == 0

    arquivo = projeto / 'analises' / 'alice' / 'export' / f'consolidado.{formato}'
    assert str(arquivo) in capsys.readouterr().out
    if formato == 'csv':
        assert len(pd.read_csv(arquivo)) == 8
    elif formato == 'parquet':
        assert set(pd.read_parquet(arquivo)['concurso']) == {'alfa', 'beta'}
    else:
        linhas = arquivo.read_text(encoding='utf-8').splitlines()
        assert linhas[0].startswith('| concurso |') and len(linhas) == 10


def test_export_formato_invalido(projeto):
    assert main(['export', '--format', 'xlsx']) != 0


def test_nome_sem_edital_aparece_a_confirmar_e_o_corrigido_vence(projeto):
    assert main(['--candidate', 'alice']) == 0
    html = indice(projeto).read_text(encoding='utf-8')
    assert 'a confirmar' in html
    assert 'alfa: nome do concurso: alfa (da pasta do concurso); a confirmar em Concursos' in html

    pasta = projeto / 'provas' / 'alfa'
    dados = yaml.safe_load((pasta / 'concurso.yaml').read_text(encoding='utf-8'))
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump({**dados, 'titulo': 'Alfa 2025'}), encoding='utf-8')
    assert main(['--candidate', 'alice']) == 0

    html = indice(projeto).read_text(encoding='utf-8')
    assert '>Alfa 2025</a>' in html
    assert 'nome do concurso' not in html
