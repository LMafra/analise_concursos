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


def test_relatorio_do_concurso_fecha_os_detalhes_tecnicos(projeto):
    assert main(['--candidate', 'alice']) == 0

    html = (projeto / 'analises' / 'alice' / 'alfa' / 'relatorio.html').read_text(encoding='utf-8')
    principal, tecnico = html.split('<details>\n<summary><h2>Detalhes técnicos</h2></summary>')
    assert '<h2>Resumo</h2>' in principal and '<h2>O que conferir</h2>' in principal
    for termo in ('nota_liquida', 'confianca_ocr', 'score', 'similaridade', 'TF-IDF'):
        assert termo not in principal
    assert 'nota_liquida' in tecnico


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
    principal, apendice = html.split('<details id="detalhes-tecnicos">')
    assert 'perfil da banca' not in principal
    assert 'Como o app chegou nesses números' in apendice
    assert 'alfa: o edital não traz a regra de correção; usei a regra padrão da banca.' in apendice
    assert 'Detalhe técnico: regra de correção do perfil da banca' in apendice
    assert 'regra padrão da banca (0,50)' in apendice
    assert 'Observações sobre os dados' in apendice
    assert re.search(r'Gerado por concurso-analise \d[\w.+]* em \d{2}/\d{2}/\d{4}', html)


def test_indice_e_um_painel_com_resumo_cards_e_selos(projeto):
    concurso(projeto, 'beta', '2025-09-01')
    respostas(projeto, 'beta', '1 A\n2 B\n3 D\n4 E\n')

    assert main(['--candidate', 'alice']) == 0

    html = indice(projeto).read_text(encoding='utf-8')
    assert re.search(r'<p class="resumo">Você fez 2 concursos\.', html)
    assert html.count('<div class="card">') == 5
    for titulo in ('Como estou saindo', 'Meus pontos fortes', 'Meus pontos a melhorar', 'Estou evoluindo?'):
        assert f'>{titulo}</h2>' in html
    assert '<nav aria-label="Ir para">' in html
    assert html.count('Sem corte no edital</span>') == 2
    assert '<span aria-hidden="true">–</span>' in html
    assert '<details id="detalhes-tecnicos">' in html and '<details id="detalhes-tecnicos" open' not in html


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
    assert 'Estou evoluindo?' in html
    assert 'consolidado/evolucao_zscore.png' in html
    assert '<figcaption>' in html
    assert 'Quanto falta para o corte (tabela técnica)' in html
    assert 'Relatório de evolução' in html.split('<details id="detalhes-tecnicos">')[1]


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
    assert 'alfa: o nome “alfa” não veio do edital; confirme na tela Concursos.' in html
    assert 'nome do concurso: alfa (da pasta do concurso); a confirmar em Concursos' in html

    pasta = projeto / 'provas' / 'alfa'
    dados = yaml.safe_load((pasta / 'concurso.yaml').read_text(encoding='utf-8'))
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump({**dados, 'titulo': 'Alfa 2025'}), encoding='utf-8')
    assert main(['--candidate', 'alice']) == 0

    html = indice(projeto).read_text(encoding='utf-8')
    assert '>Alfa 2025</a>' in html
    assert 'nome do concurso' not in html
