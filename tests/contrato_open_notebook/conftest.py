"""Contrato com o open-notebook real: o pacote de estudo montado em `ESTUDO_PACOTE` (arquivo `.tar.xz` ou
`.zip`, ou a pasta `estudo-<versão>` já extraída), instalado numa pasta temporária e aberto pelo supervisor
do app. Sem a variável, os testes pulam.

    ESTUDO_PACOTE=build/estudo/estudo-1.15.1-1-linux-x86_64.tar.xz uv run pytest -m open_notebook_real tests/contrato_open_notebook
"""

import json
import os
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from concursos.estudo import embeddings, instalacao
from concursos.estudo.instalacao import Pastas
from concursos.estudo.supervisor import Supervisor
from concursos.integracoes.open_notebook import ClienteOpenNotebook

PACOTE = os.environ.get('ESTUDO_PACOTE')


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.open_notebook_real)
        if not PACOTE:
            item.add_marker(pytest.mark.skip(reason='defina ESTUDO_PACOTE com o pacote de estudo montado'))


class LlmFalso:
    """Compatível com a OpenAI: a estratégia do Ask recebe JSON; as outras etapas, texto."""

    def __init__(self) -> None:
        llm = self
        self.chamadas: list[str] = []

        class Tratador(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):  # noqa: N802
                corpo = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                texto = json.dumps(corpo.get('messages', []), ensure_ascii=False)
                llm.chamadas.append(texto)
                ids = re.findall(r'source:[a-z0-9]+', texto)
                if ids:
                    conteudo = f'A licitação é dispensável [{ids[0]}].'
                else:
                    conteudo = json.dumps(
                        {
                            'reasoning': 'r',
                            'searches': [{'term': 'licitação dispensável', 'instructions': 'ache'}],
                        }
                    )
                resposta = {
                    'id': 'x',
                    'object': 'chat.completion',
                    'created': 0,
                    'model': corpo.get('model', 'falso'),
                    'choices': [
                        {
                            'index': 0,
                            'message': {'role': 'assistant', 'content': conteudo},
                            'finish_reason': 'stop',
                        }
                    ],
                    'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
                }
                dados = json.dumps(resposta).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Tratador)
        self.url = f'http://127.0.0.1:{self.http.server_port}/v1'
        threading.Thread(target=self.http.serve_forever, daemon=True).start()


@pytest.fixture(scope='session')
def llm_falso():
    llm = LlmFalso()
    yield llm
    llm.http.shutdown()


@pytest.fixture(scope='session')
def aberto(tmp_path_factory, llm_falso):
    base = tmp_path_factory.mktemp('estudo')
    pastas = Pastas(base / 'open-notebook')
    arquivo = Path(PACOTE).resolve()
    versao = re.match(r'estudo-(\d+\.\d+\.\d+-\d+)', arquivo.name).group(1)
    if arquivo.is_dir():
        destino = instalacao.raiz_do_pacote(pastas, versao)
        destino.parent.mkdir(parents=True)
        destino.symlink_to(arquivo, target_is_directory=True)
        instalacao.gravar_estado(pastas, instalacao.Estado(atual=versao))
    else:
        instalacao.instalar_arquivo(pastas, arquivo, versao)
    cifra = secrets.token_urlsafe(32)
    ia = {'OPENAI_COMPATIBLE_BASE_URL_LLM': llm_falso.url, 'OPENAI_COMPATIBLE_API_KEY_LLM': 'falsa'}
    supervisor = Supervisor(pastas, base / 'logs', chave_cifra=lambda: cifra, ambiente_ia=lambda: ia)
    sessao = supervisor.garantir()
    cliente = ClienteOpenNotebook(sessao.url, sessao.senha, timeout=300)
    embeddings.registrar(cliente)
    yield supervisor, sessao, cliente, base
    supervisor.parar()
