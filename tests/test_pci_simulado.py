import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml
from conftest import analisar, criar_concurso
from test_analytics_correcao import CEBRASPE
from test_edital import PAGINAS
from transporte_pci import TransporteFalso, payload

from concursos.analytics.consolidado import concursos_analisados, contar_questoes
from concursos.aplicacao import integracoes as aplicacao_integracoes
from concursos.assistente import InteracaoAutomatica
from concursos.cadastro import cadastrar
from concursos.cli import main
from concursos.concurso_config import carregar_concurso, ler_dados
from concursos.integracoes import download_assistido, pci_mcp
from concursos.integracoes.pci_mcp import ProvaAnteriorPci
from concursos.integracoes.simulado_pci import (
    ARQUIVO_PROVAS_ANTERIORES,
    BANCA_RESERVA,
    banca_da_organizadora,
    nome_da_pasta,
    preparar_pasta,
    termos_automaticos,
)
from concursos.manifesto import calcular
from concursos.relatorio_html import gerar_relatorio_html

FIXTURE_PAGINA = Path(__file__).parent / 'fixtures' / 'pci' / 'pagina_prova.html'
LINK = 'https://www.pciconcursos.com.br/provas/download/analista-alfa-fgv-2019'
PROVA = ProvaAnteriorPci(
    id=4242, descricao='Analista Judiciário', orgao='Tribunal Alfa', ano=2019, organizadora='FGV', link=LINK
)
ALVO = {
    'nome': 'Tribunal Alfa 2026',
    'banca': 'cebraspe',
    'cargo': 'Analista de TI - Ciência de Dados',
    'formato': 'certo_errado',
    'pontuacao': 'cebraspe',
    'edital': 'edital.txt',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
    'respostas': {'arquivo': 'respostas.txt'},
}
ARQUIVOS_ALVO = {
    'edital.txt': '\f'.join([*PAGINAS, CEBRASPE]),
    'gabarito.txt': '1 C\n2 E\n3 C\n4 C\n',
    'respostas.txt': '1 C\n2 C\n3 E\n4 E\n',
}
SIMULADO = {
    'nome': 'Tribunal Alfa 2019 (simulado PCI 4242)',
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'data_prova': '2026-11-02',
    'edital': '../alvo/edital.txt',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
    'respostas': {'arquivo': 'respostas.txt'},
    'simulado': {
        'fonte': 'pci',
        'id_pci': 4242,
        'ano_original': 2019,
        'organizadora': 'FGV',
        'orgao': 'Tribunal Alfa',
        'link': LINK,
        'concurso_alvo': 'alvo',
        'cargo_alvo': 'Analista de TI - Ciência de Dados',
    },
}
ARQUIVOS_SIMULADO = {'gabarito.txt': '1 A\n2 B\n3 C\n4 D\n', 'respostas.txt': '1 A\n2 B\n3 D\n4 E\n'}


@pytest.mark.parametrize(
    ('organizadora', 'banca'),
    [
        ('FGV', 'fgv'),
        ('CESPE', 'cebraspe'),
        ('Cebraspe', 'cebraspe'),
        ('Fundação Carlos Chagas (FCC)', 'fcc'),
        ('VUNESP', 'vunesp'),
        ('ESAF', None),
        ('', None),
    ],
)
def test_banca_vem_das_marcas_do_perfil(organizadora: str, banca: str | None):
    assert banca_da_organizadora(organizadora) == banca


def test_pasta_do_simulado_leva_orgao_ano_e_id():
    assert nome_da_pasta(PROVA) == 'tribunal_alfa_2019_pci4242'


def test_termos_automaticos_tiram_o_numero_do_cargo_e_tentam_com_e_sem_banca(raizes):
    provas, _ = raizes
    criar_concurso(
        provas, 'alvo', {**ALVO, 'cargo': 'CARGO 12: ANALISTA JUDICIÁRIO - ÁREA ADMINISTRATIVA'}, {}
    )
    assert termos_automaticos(carregar_concurso(provas / 'alvo')) == [
        'analista judiciário cebraspe',
        'analista judiciário',
    ]


def test_termos_explicitos_do_concurso_vencem(raizes):
    provas, _ = raizes
    criar_concurso(provas, 'alvo', {**ALVO, 'pci': {'termos_provas': ['auditor receita']}}, {})
    assert termos_automaticos(carregar_concurso(provas / 'alvo')) == ['auditor receita']


def test_preparar_pasta_empresta_o_edital_e_preserva_o_que_o_usuario_mudou(raizes):
    provas, _ = raizes
    criar_concurso(provas, 'alvo', ALVO, ARQUIVOS_ALVO)
    alvo = carregar_concurso(provas / 'alvo')

    pasta, avisos = preparar_pasta(provas, PROVA, alvo)

    assert avisos == []
    dados = ler_dados(pasta)
    assert dados['banca'] == 'fgv' and dados['edital'] == '../alvo/edital.txt'
    assert dados['simulado']['concurso_alvo'] == 'alvo'
    assert dados['simulado']['cargo_alvo'] == ALVO['cargo']
    (pasta / 'concurso.yaml').write_text(
        yaml.safe_dump({**dados, 'banca': 'vunesp'}, allow_unicode=True), encoding='utf-8'
    )
    preparar_pasta(provas, PROVA, alvo)
    assert ler_dados(pasta)['banca'] == 'vunesp'


def test_organizadora_sem_perfil_usa_a_reserva_e_avisa(raizes):
    provas, _ = raizes
    esaf = ProvaAnteriorPci(
        id=1, descricao='Auditor', orgao='Receita', ano=2014, organizadora='ESAF', link=LINK
    )

    pasta, avisos = preparar_pasta(provas, esaf, None)

    assert ler_dados(pasta)['banca'] == BANCA_RESERVA
    assert any('ESAF' in aviso for aviso in avisos)
    assert any('sem tópico' in aviso for aviso in avisos)


def test_cadastro_preserva_o_edital_de_fora_da_pasta(raizes):
    provas, _ = raizes
    criar_concurso(provas, 'alvo', ALVO, ARQUIVOS_ALVO)
    pasta, _ = preparar_pasta(provas, PROVA, carregar_concurso(provas / 'alvo'))
    (pasta / 'gab.txt').write_text('# FGV - Gabarito definitivo\n1 A\n2 B\n', encoding='utf-8')

    assert cadastrar(pasta, InteracaoAutomatica())

    dados = ler_dados(pasta)
    assert dados['edital'] == '../alvo/edital.txt'
    assert dados['simulado']['id_pci'] == 4242
    assert dados['banca'] == 'fgv'


def test_manifesto_do_simulado_muda_quando_o_edital_emprestado_muda(raizes):
    provas, _ = raizes
    criar_concurso(provas, 'alvo', ALVO, ARQUIVOS_ALVO)
    pasta = criar_concurso(provas, 'simulado', SIMULADO, ARQUIVOS_SIMULADO)
    antes = calcular(pasta)

    (provas / 'alvo' / 'edital.txt').write_text('outro edital', encoding='utf-8')

    assert calcular(pasta) != antes


def _analisar_alvo_e_simulado(provas: Path, analises: Path, *extra: str) -> None:
    criar_concurso(provas, 'alvo', ALVO, ARQUIVOS_ALVO)
    criar_concurso(provas, 'simulado', SIMULADO, ARQUIVOS_SIMULADO)
    assert analisar(provas, analises, *extra) == 0


def test_simulado_usa_os_topicos_do_alvo_mas_nao_a_regra_dele(raizes):
    provas, analises = raizes
    _analisar_alvo_e_simulado(provas, analises)

    [alvo] = json.loads((analises / 'alvo' / 'correcao.json').read_text(encoding='utf-8'))
    [simulado] = json.loads((analises / 'simulado' / 'correcao.json').read_text(encoding='utf-8'))
    assert (alvo['fonte'], alvo['fator_penalidade']) == ('edital', 1.0)
    assert simulado['fonte'] != 'edital'
    assert simulado['fator_penalidade'] == 0.0
    assert simulado['documento_origem'] is None
    assert simulado['nota_corte'] is None
    assert simulado['data_prova'] == '2026-11-02'
    estruturado_alvo = json.loads((analises / 'alvo' / 'edital_estruturado.json').read_text(encoding='utf-8'))
    estruturado = json.loads((analises / 'simulado' / 'edital_estruturado.json').read_text(encoding='utf-8'))
    assert estruturado['conhecimentos'] == estruturado_alvo['conhecimentos'] != []


def test_simulado_fica_fora_do_consolidado_por_padrao(raizes):
    provas, analises = raizes
    _analisar_alvo_e_simulado(provas, analises)

    geral = pd.read_csv(analises / 'consolidado' / 'desempenho_geral.csv')
    assert set(geral['concurso']) == {ALVO['nome']}
    assert concursos_analisados(provas, analises, incluir_simulados=False) == ['alvo']
    assert concursos_analisados(provas, analises, incluir_simulados=True) == ['alvo', 'simulado']
    assert contar_questoes(analises, provas, incluir_simulados=False) == 4
    assert contar_questoes(analises) == 8
    indice = gerar_relatorio_html(provas, analises, provas.parent / 'taxonomia.yaml', 0.6).read_text(
        encoding='utf-8'
    )
    tabela_de_concursos = indice.split('>Como estou saindo</h2>')[1].split('<h3>')[0]
    assert 'simulado/relatorio.html' not in tabela_de_concursos
    assert 'Simulados que você fez' in indice
    assert LINK in indice


def test_incluir_simulados_no_projeto_traz_o_simulado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raiz = tmp_path / 'projeto'
    provas, analises = raiz / 'provas', raiz / 'analises'
    provas.mkdir(parents=True)
    (raiz / '.concurso').mkdir()
    (raiz / '.concurso' / 'config.toml').write_text('[analise]\nincluir_simulados = true\n', encoding='utf-8')
    monkeypatch.chdir(raiz)
    (raiz / 'config.yaml').write_text('incluir_simulados: true\n', encoding='utf-8')

    _analisar_alvo_e_simulado(provas, analises, '--config', str(raiz / 'config.yaml'))

    geral = pd.read_csv(analises / 'consolidado' / 'desempenho_geral.csv')
    assert set(geral['concurso']) == {ALVO['nome'], SIMULADO['nome']}
    assert concursos_analisados(provas, analises) == ['alvo', 'simulado']
    assert contar_questoes(analises, provas) == 8


def test_add_de_respostas_data_o_simulado_com_hoje(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    raiz = tmp_path / 'projeto'
    provas = raiz / 'provas'
    provas.mkdir(parents=True)
    (raiz / '.concurso').mkdir()
    monkeypatch.chdir(raiz)
    sem_data = {chave: valor for chave, valor in SIMULADO.items() if chave != 'data_prova'}
    pasta = criar_concurso(provas, 'simulado', sem_data, {'gabarito.txt': ARQUIVOS_SIMULADO['gabarito.txt']})
    respostas = tmp_path / 'minhas.txt'
    respostas.write_text('1 A\n2 B\n', encoding='utf-8')

    assert (
        main(['--yes', 'add', str(respostas), '--candidate', 'Fulano Teste', '--concurso', 'simulado']) == 0
    )

    assert ler_dados(pasta)['data_prova'] == date.today().isoformat()
    assert 'simulado datado' in capsys.readouterr().out


@pytest.fixture
def projeto_pci(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    (raiz / 'provas').mkdir(parents=True)
    (raiz / '.concurso').mkdir()
    monkeypatch.chdir(raiz)
    criar_concurso(raiz / 'provas', 'alvo', ALVO, ARQUIVOS_ALVO)
    falso = TransporteFalso(
        {
            'pesquisar_provas': lambda a: payload(
                [
                    {
                        'id': PROVA.id,
                        'descricao': PROVA.descricao,
                        'orgao': PROVA.orgao,
                        'ano': PROVA.ano,
                        'organizadora': PROVA.organizadora,
                        'link': PROVA.link,
                    }
                ]
                if a['termo'] == 'analista ti'
                else []
            )
        }
    )
    monkeypatch.setattr(pci_mcp, 'abrir_transporte', lambda configuracao: falso)
    assert main(['--yes', 'pci', 'enable']) == 0
    return raiz


def test_pci_provas_tenta_com_e_sem_banca_e_grava_a_lista(projeto_pci: Path, capsys):
    assert main(['pci', 'provas', 'alvo', '--candidate', 'Fulano Teste']) == 0

    saida = capsys.readouterr().out
    assert '4242' in saida and 'Tribunal Alfa' in saida
    lista = projeto_pci / 'analises' / 'fulano_teste' / 'alvo' / ARQUIVO_PROVAS_ANTERIORES
    texto = lista.read_text(encoding='utf-8')
    assert 'Busca no PCI Concursos por "analista ti"' in texto
    assert f'[abrir]({LINK})' in texto


def test_pci_provas_download_abre_a_pagina_e_importa_o_baixado(
    projeto_pci: Path, monkeypatch: pytest.MonkeyPatch, navegador: list, capsys
):
    baixados = projeto_pci / 'downloads'
    baixados.mkdir()
    prova = baixados / 'prova1-auditor-fiscal.pdf'
    prova.write_bytes(b'%PDF-1.4 prova')
    paginas: list[str] = []
    cadastradas: list[Path] = []

    def ler_pagina(link: str, timeout: float) -> str:
        paginas.append(link)
        return FIXTURE_PAGINA.read_text(encoding='utf-8')

    def esperar(pasta, esperados, desde, timeout):
        assert pasta == baixados
        assert 'prova1_auditor_fiscal.pdf' in esperados
        return {'prova1_auditor_fiscal.pdf': prova}

    monkeypatch.setattr(aplicacao_integracoes, 'baixar_pagina', ler_pagina)
    monkeypatch.setattr(download_assistido, 'esperar_downloads', esperar)
    monkeypatch.setattr(
        aplicacao_integracoes, 'cadastrar', lambda pasta, interacao: cadastradas.append(pasta) or True
    )
    config = projeto_pci.parent / 'home_concurso' / 'config.toml'
    pci_mcp.gravar_configuracao(config, pasta_downloads=str(baixados))

    assert main(['--yes', 'pci', 'provas', 'alvo', '--download', '4242']) == 0

    pasta = projeto_pci / 'provas' / 'tribunal_alfa_2019_pci4242'
    assert paginas == [LINK]
    assert navegador == [LINK]
    assert (pasta / 'prova1_auditor_fiscal.pdf').read_bytes() == b'%PDF-1.4 prova'
    assert cadastradas == [pasta]
    assert ler_dados(pasta)['simulado']['concurso_alvo'] == 'alvo'
    assert 'simulado pronto' in capsys.readouterr().out


def test_pci_provas_download_offline_recusa(projeto_pci: Path, capsys):
    main(['pci', 'provas', 'alvo'])
    assert main(['--offline', 'pci', 'provas', 'alvo', '--download', '4242']) == 1
    assert '--offline' in capsys.readouterr().err


def test_pci_provas_download_de_id_fora_da_lista_recusa(projeto_pci: Path, capsys):
    assert main(['pci', 'provas', 'alvo', '--download', '1']) == 1
    assert 'não está no resultado' in capsys.readouterr().err


def test_pci_provas_import_all_importa_a_lista_uma_por_vez(
    projeto_pci: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    tentadas: list[int] = []
    monkeypatch.setattr(
        aplicacao_integracoes,
        'importar_simulado',
        lambda opcoes, provas, identificador, alvo, esperar=None: tentadas.append(identificador) or 0,
    )

    assert main(['--yes', 'pci', 'provas', 'alvo', '--import-all']) == 0

    assert tentadas == [4242]
    saida = capsys.readouterr().out
    assert 'Passo 1 de 1' in saida and 'provas anteriores: 1 importada(s)' in saida
