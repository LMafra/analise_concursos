import io
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import tomli_w
import yaml

from concursos.cli import main
from concursos.llm import ARQUIVO_ENV, guardar_chave

EDITAL = (
    'EDITAL Nº 1, DE 2 DE JANEIRO DE 2025\n'
    'CONCURSO PÚBLICO PARA O CARGO DE ANALISTA\n'
    'A prova objetiva terá 4 questões, cada uma com quatro respostas possíveis, '
    'identificadas pelas letras A, B, C e D.\n'
)
RESPOSTAS_DA_ANA = '1 A\n2 B\n3 C\n4 C\n'


class Servidor:
    """Um provedor compatível com OpenAI que grava os corpos recebidos e devolve `resposta`."""

    def __init__(self) -> None:
        self.corpos: list[dict] = []
        self.resposta: dict = {}
        servidor = self

        class Tratador(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                tamanho = int(self.headers['Content-Length'])
                servidor.corpos.append(json.loads(self.rfile.read(tamanho)))
                corpo = json.dumps({'choices': [{'message': {'content': json.dumps(servidor.resposta)}}]})
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(corpo.encode('utf-8'))

            def log_message(self, *_args) -> None:
                pass

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Tratador)
        self.url = f'http://127.0.0.1:{self.http.server_port}/v1'
        threading.Thread(target=self.http.serve_forever, daemon=True).start()


@pytest.fixture
def servidor():
    servidor = Servidor()
    yield servidor
    servidor.http.shutdown()


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, home_isolada: Path, servidor: Servidor) -> Path:
    raiz = tmp_path / 'projeto'
    pasta = raiz / 'provas' / 'ficticia'
    (pasta / 'candidatos' / 'ana').mkdir(parents=True)
    (pasta / 'concurso.yaml').write_text(
        yaml.safe_dump(
            {
                'banca': 'generic',
                'formato': 'multipla_escolha',
                'edital': 'edital.txt',
                'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
            }
        ),
        encoding='utf-8',
    )
    (pasta / 'gabarito.txt').write_text('1 A\n2 B\n3 C\n4 D\n', encoding='utf-8')
    (pasta / 'edital.txt').write_text(EDITAL, encoding='utf-8')
    (pasta / 'candidatos' / 'ana' / 'respostas.txt').write_text(RESPOSTAS_DA_ANA, encoding='utf-8')
    (raiz / '.concurso').mkdir()
    (raiz / '.concurso' / 'config.toml').write_text('[candidato]\nultimo = "ana"\n', encoding='utf-8')
    home_isolada.mkdir(parents=True, exist_ok=True)
    configurar(
        home_isolada,
        {
            'provedor': 'openai',
            'url': servidor.url,
            'modelo': 'teste',
            'variavel_chave': 'OPENAI_API_KEY',
            'consentimento': True,
        },
    )
    monkeypatch.setenv('OPENAI_API_KEY', 'chave-de-teste')
    monkeypatch.chdir(raiz)
    return raiz


def configurar(home: Path, llm: dict) -> None:
    (home / 'config.toml').write_text(tomli_w.dumps({'llm': llm}), encoding='utf-8')


def regras(projeto: Path) -> dict:
    caminho = projeto / 'analises' / 'ana' / 'ficticia' / 'edital_estruturado.json'
    return json.loads(caminho.read_text(encoding='utf-8'))


def test_trecho_literal_preenche_com_fonte_llm_e_so_o_edital_e_enviado(projeto, servidor):
    servidor.resposta = {
        'alternativas': {'valor': 4, 'trecho_origem': 'cada uma com quatro respostas possiveis'},
        'penalidade': {'valor': 0.25, 'trecho_origem': 'cada errada desconta um quarto'},
        'data_prova': None,
    }

    assert main(['analyze', '--no-open']) == 0

    assert len(servidor.corpos) == 1
    corpo = json.dumps(servidor.corpos[0], ensure_ascii=False)
    assert 'quatro respostas possíveis' in corpo
    assert 'candidatos' not in corpo and RESPOSTAS_DA_ANA.replace('\n', '\\n') not in corpo
    prova = regras(projeto)['prova']
    assert prova['alternativas']['valor'] == 4
    assert prova['alternativas']['fonte'] == 'llm'
    assert prova['alternativas']['camada'] == 'llm'
    assert prova['alternativas']['documento_origem'] == 'edital.txt'
    assert prova['penalidade']['fonte'] == 'default'


@pytest.mark.parametrize('flag', ['--offline', '--no-llm'])
def test_offline_ou_no_llm_nao_fazem_requisicao(projeto, servidor, flag):
    assert main([flag, 'analyze', '--no-open']) == 0

    assert servidor.corpos == []
    assert regras(projeto)['prova']['alternativas']['fonte'] == 'default'


def test_sem_chave_avisa_qual_variavel_definir_e_segue_sem_llm(projeto, servidor, monkeypatch, caplog):
    monkeypatch.delenv('OPENAI_API_KEY')

    with caplog.at_level(logging.WARNING):
        assert main(['analyze', '--no-open']) == 0

    assert 'OPENAI_API_KEY' in caplog.text and 'dica:' in caplog.text
    assert servidor.corpos == []


def test_sem_consentimento_nao_chama_o_provedor(projeto, servidor, home_isolada):
    configurar(home_isolada, {'provedor': 'openai', 'url': servidor.url, 'variavel_chave': 'OPENAI_API_KEY'})

    assert main(['analyze', '--no-open']) == 0

    assert servidor.corpos == []


def test_doctor_aponta_a_chave_ausente(projeto, monkeypatch, capsys):
    monkeypatch.delenv('OPENAI_API_KEY')

    assert main(['doctor']) != 0

    saida = capsys.readouterr().out
    assert '✗ LLM' in saida and 'OPENAI_API_KEY' in saida


def test_doctor_com_chave_presente(projeto, capsys):
    main(['doctor'])

    assert '✓ LLM: openai' in capsys.readouterr().out


@pytest.mark.skipif(os.name == 'nt', reason='permissão POSIX')
def test_sem_keyring_a_chave_vai_para_env_600_com_aviso(tmp_path, monkeypatch, caplog):
    monkeypatch.setitem(__import__('sys').modules, 'keyring', None)

    with caplog.at_level(logging.WARNING):
        onde = guardar_chave('OPENAI_API_KEY', 'segredo', tmp_path)

    caminho = tmp_path / ARQUIVO_ENV
    assert onde == str(caminho)
    assert (caminho.stat().st_mode & 0o777) == 0o600
    assert 'texto plano' in caplog.text


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_consentimento_e_pedido_uma_vez_e_gravado_na_configuracao_global(
    tmp_path, monkeypatch, home_isolada, capsys
):
    raiz = tmp_path / 'novo'
    (raiz / 'provas').mkdir(parents=True)
    monkeypatch.chdir(raiz)
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.setenv('CONCURSO_DOCTOR', '0')
    monkeypatch.setattr('sys.stdin', Terminal('\n\n\n\nollama\ns\n\n'))

    assert main(['init']) == 0

    primeira = capsys.readouterr().out
    assert 'Só o texto do edital' in primeira
    global_ = (home_isolada / 'config.toml').read_text(encoding='utf-8')
    assert 'consentimento = true' in global_ and 'provedor = "ollama"' in global_

    monkeypatch.setattr('sys.stdin', Terminal('\n' * 8))
    assert main(['init']) == 0
    assert 'Só o texto do edital' not in capsys.readouterr().out
