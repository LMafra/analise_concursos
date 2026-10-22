import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pytest
import yaml
from conftest import ler_csv
from editais_bancas import PF_2025
from PIL import Image

from concursos.analytics.regras_edital import NivelConfianca, extrair_regras
from concursos.cli import main
from concursos.concurso_config import ConfiguracaoInvalidaError, carregar_concurso, validar_dados

GABARITO = '1 A\n2 B\n3 C\n4 D\n'
CONFIRMAR = 'edital_a_confirmar.yaml'


@pytest.fixture
def sem_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    original = __import__('shutil').which
    monkeypatch.setattr(
        'concursos.texto.shutil.which', lambda nome: None if nome == 'tesseract' else original(nome)
    )


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sem_tesseract) -> Path:
    raiz = tmp_path / 'projeto'
    pasta = raiz / 'provas' / 'ficticia'
    pasta.mkdir(parents=True)
    config = {
        'banca': 'generic',
        'formato': 'multipla_escolha',
        'edital': 'edital.pdf',
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
    }
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(config), encoding='utf-8')
    (pasta / 'gabarito.txt').write_text(GABARITO, encoding='utf-8')
    imagem = np.full((800, 600), 255, dtype=np.uint8)
    imagem[100:120, 50:550] = 0
    Image.fromarray(imagem).save(pasta / 'edital.pdf', resolution=100)
    for slug, respostas in (('ana', '1 A\n2 B\n3 C\n4 C\n'), ('bia', '1 A\n2 C\n3 C\n4 C\n')):
        candidato = pasta / 'candidatos' / slug
        candidato.mkdir(parents=True)
        (candidato / 'respostas.txt').write_text(respostas, encoding='utf-8')
    monkeypatch.chdir(raiz)
    return raiz


def pasta(raiz: Path) -> Path:
    return raiz / 'provas' / 'ficticia'


def saida(raiz: Path, arquivo: str, candidato: str = 'ana') -> Path:
    return raiz / 'analises' / candidato / 'ficticia' / arquivo


def ler_json(caminho: Path):
    return json.loads(caminho.read_text(encoding='utf-8'))


def test_dica_do_tesseract_traz_o_comando_do_sistema(projeto, caplog, monkeypatch):
    monkeypatch.setattr('concursos.doctor.platform.system', lambda: 'Darwin')

    with caplog.at_level(logging.WARNING):
        assert main(['--all-candidates']) == 0

    assert 'brew install tesseract' in caplog.text
    assert 'apt' not in caplog.text


def test_edital_em_imagem_sem_tesseract_cai_no_modo_minimo_e_pede_confirmacao(projeto, caplog):
    with caplog.at_level(logging.WARNING):
        assert main(['--all-candidates']) == 0

    assert 'Tesseract' in caplog.text and 'dica:' in caplog.text
    confirmar = yaml.safe_load((pasta(projeto) / CONFIRMAR).read_text(encoding='utf-8'))
    assert confirmar == {
        'data_prova': None,
        'alternativas': None,
        'fator_penalidade': None,
        'nota_corte': None,
    }
    assert ler_csv(saida(projeto, 'questoes.csv'))['topico'].eq('nao_mapeado').all()
    edital = ler_json(saida(projeto, 'edital_estruturado.json'))
    assert edital['confianca_edital'] == {'valor': 0.0, 'nivel': 'minima'}
    assert edital['prova']['formato']['camada'] == 'config'
    assert edital['prova']['penalidade']['camada'] == 'nenhuma'


def test_arquivo_de_confirmacao_lista_o_que_foi_extraido_e_comenta_os_campos(projeto):
    assert main(['--all-candidates']) == 0

    texto = (pasta(projeto) / CONFIRMAR).read_text(encoding='utf-8')
    assert 'Nada foi extraído do edital' in texto
    assert '# data da prova objetiva (AAAA-MM-DD)\ndata_prova:\n' in texto


def test_preencher_aplica_com_fonte_config_e_reprocessa_todos_os_candidatos(projeto):
    assert main(['--all-candidates']) == 0
    antes = {c: saida(projeto, 'relatorio.md', c).stat().st_mtime_ns for c in ('ana', 'bia')}
    preenchido = 'data_prova: 2025-05-04\nalternativas: 4\nfator_penalidade: 1\nnota_corte: 2\n'
    (pasta(projeto) / CONFIRMAR).write_text(preenchido, encoding='utf-8')

    assert main(['--all-candidates']) == 0

    assert all(saida(projeto, 'relatorio.md', c).stat().st_mtime_ns != antes[c] for c in ('ana', 'bia'))
    correcao = ler_json(saida(projeto, 'correcao.json'))[0]
    assert (correcao['fonte'], correcao['fator_penalidade'], correcao['data_prova']) == (
        'config',
        1.0,
        '2025-05-04',
    )
    edital = ler_json(saida(projeto, 'edital_estruturado.json'))
    assert edital['prova']['alternativas']['valor'] == 4
    assert edital['prova']['alternativas']['fonte'] == 'config'
    assert [(c['escopo'], c['valor'], c['fonte']) for c in edital['cortes']] == [('conjunto', 2.0, 'config')]
    assert (pasta(projeto) / CONFIRMAR).read_text(encoding='utf-8') == preenchido


def test_arquivo_editado_nao_e_sobrescrito_e_so_ganha_campos_novos(projeto):
    assert main(['--all-candidates']) == 0
    editado = '# minha anotação\ndata_prova: 2025-05-04\n'
    (pasta(projeto) / CONFIRMAR).write_text(editado, encoding='utf-8')

    assert main(['--all-candidates']) == 0

    texto = (pasta(projeto) / CONFIRMAR).read_text(encoding='utf-8')
    assert texto.startswith(editado)
    assert yaml.safe_load(texto) == {
        'data_prova': date(2025, 5, 4),
        'alternativas': None,
        'fator_penalidade': None,
        'nota_corte': None,
    }


def test_sem_campos_faltando_nao_gera_o_arquivo(projeto):
    config = yaml.safe_load((pasta(projeto) / 'concurso.yaml').read_text(encoding='utf-8'))
    config.update(data_prova='2025-05-04', alternativas=4, correcao={'fator_penalidade': 0, 'nota_corte': 2})
    (pasta(projeto) / 'concurso.yaml').write_text(yaml.safe_dump(config), encoding='utf-8')

    assert main(['--all-candidates']) == 0

    assert not (pasta(projeto) / CONFIRMAR).exists()


def test_selo_do_edital_no_indice(projeto):
    assert main(['--candidate', 'ana']) == 0

    assert 'edital: mínima' in (projeto / 'analises' / 'ana' / 'index.html').read_text(encoding='utf-8')


def test_valor_invalido_na_confirmacao_cita_o_arquivo(tmp_path):
    (tmp_path / 'concurso.yaml').write_text(
        yaml.safe_dump(
            {
                'banca': 'generic',
                'formato': 'multipla_escolha',
                'provas': {'u': {'gabarito': 'g', 'itens': [1, 4]}},
            }
        ),
        encoding='utf-8',
    )
    (tmp_path / CONFIRMAR).write_text('data_prova: amanhã\n', encoding='utf-8')

    with pytest.raises(ConfiguracaoInvalidaError, match=CONFIRMAR):
        carregar_concurso(tmp_path)


def test_campo_desconhecido_na_confirmacao_e_erro(tmp_path):
    (tmp_path / 'concurso.yaml').write_text(
        yaml.safe_dump(
            {
                'banca': 'generic',
                'formato': 'multipla_escolha',
                'provas': {'u': {'gabarito': 'g', 'itens': [1, 4]}},
            }
        ),
        encoding='utf-8',
    )
    (tmp_path / CONFIRMAR).write_text('nota_minima: 5\n', encoding='utf-8')

    with pytest.raises(ConfiguracaoInvalidaError, match="'nota_minima'"):
        carregar_concurso(tmp_path)


def test_concurso_yaml_vence_a_confirmacao(tmp_path):
    dados = {
        'banca': 'generic',
        'formato': 'multipla_escolha',
        'alternativas': 5,
        'provas': {'u': {'gabarito': 'g', 'itens': [1, 4]}},
    }
    (tmp_path / 'concurso.yaml').write_text(yaml.safe_dump(dados), encoding='utf-8')
    (tmp_path / CONFIRMAR).write_text('alternativas: 4\nfator_penalidade: 0.25\n', encoding='utf-8')

    config = carregar_concurso(tmp_path)

    assert config.alternativas == 5
    assert config.correcao.fator_penalidade == 0.25


def test_edital_com_texto_tem_camada_heuristica_e_confianca_alta():
    config = validar_dados(
        Path('pf'),
        {
            'banca': 'cebraspe',
            'formato': 'certo_errado',
            'provas': {'u': {'gabarito': 'g', 'itens': [1, 120]}},
        },
    )

    regras = extrair_regras(config, {'edital.pdf': [PF_2025]})

    assert regras.confianca_edital.nivel is not NivelConfianca.MINIMA
    assert regras.prova.formato.fonte == 'edital'
