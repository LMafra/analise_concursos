"""Um open-notebook falso, com estado em memória, que responde como a API da versão 1.15."""

import json
import re
import threading
from dataclasses import dataclass, field
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse


@dataclass
class Pedido:
    metodo: str
    caminho: str
    cabecalhos: dict[str, str]
    corpo: bytes

    @property
    def escrita(self) -> bool:
        return self.metodo in {'POST', 'PUT', 'DELETE'} and self.caminho != '/api/search'


@dataclass
class ServidorOpenNotebook:
    senha: str | None = None
    notebooks: dict[str, dict] = field(default_factory=dict)
    sources: dict[str, dict] = field(default_factory=dict)
    notas: dict[str, dict] = field(default_factory=dict)
    vinculos: set[tuple[str, str]] = field(default_factory=set)
    vinculos_notas: set[tuple[str, str]] = field(default_factory=set)
    pedidos: list[Pedido] = field(default_factory=list)
    falhas: dict[tuple[str, str], int] = field(default_factory=dict)
    """(método, regex do caminho) → status devolvido no lugar da resposta."""
    modelos: dict[str, dict] = field(default_factory=dict)
    padroes: dict[str, str | None] = field(default_factory=dict)
    resposta_ask: str = 'Resposta [source:source:0001].'
    status_sources: dict[str, str] = field(default_factory=dict)
    reprocessados: list[str] = field(default_factory=list)
    _contador: int = 0

    def __post_init__(self) -> None:
        servidor = self

        class Tratador(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                servidor._tratar(self, 'GET')

            def do_POST(self) -> None:  # noqa: N802
                servidor._tratar(self, 'POST')

            def do_PUT(self) -> None:  # noqa: N802
                servidor._tratar(self, 'PUT')

            def do_DELETE(self) -> None:  # noqa: N802
                servidor._tratar(self, 'DELETE')

            def log_message(self, *_args) -> None:
                pass

        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Tratador)
        self.url = f'http://127.0.0.1:{self.http.server_port}'
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def desligar(self) -> None:
        self.http.shutdown()
        self.http.server_close()

    @property
    def escritas(self) -> list[Pedido]:
        return [p for p in self.pedidos if p.escrita]

    def sources_do_notebook(self, notebook_id: str) -> list[dict]:
        return [self.sources[s] for s, n in sorted(self.vinculos) if n == notebook_id and s in self.sources]

    def notas_do_notebook(self, notebook_id: str) -> list[dict]:
        return [self.notas[s] for s, n in sorted(self.vinculos_notas) if n == notebook_id]

    def criar_notebook(self, nome: str, criado: str | None = None) -> dict:
        notebook = self._novo('notebook', {'name': nome, 'description': '', 'archived': False})
        if criado:
            notebook['created'] = criado
        self.notebooks[notebook['id']] = notebook
        return notebook

    def _novo(self, tabela: str, dados: dict) -> dict:
        self._contador += 1
        return {
            'id': f'{tabela}:{self._contador:04d}',
            'created': f'2026-11-03T00:00:{self._contador:02d}',
            **dados,
        }

    def _tratar(self, http: BaseHTTPRequestHandler, metodo: str) -> None:
        tamanho = int(http.headers.get('Content-Length') or 0)
        corpo = http.rfile.read(tamanho) if tamanho else b''
        url = urlparse(http.path)
        caminho = unquote(url.path)
        self.pedidos.append(Pedido(metodo, caminho, dict(http.headers), corpo))
        if (
            caminho != '/health'
            and self.senha
            and http.headers.get('Authorization') != f'Bearer {self.senha}'
        ):
            return _responder(http, 401, {'detail': 'Missing authorization header'})
        for (metodo_falha, padrao), status in self.falhas.items():
            if metodo_falha == metodo and re.fullmatch(padrao, caminho):
                return _responder(http, status, {'detail': 'falha simulada'})
        consulta = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            status, resposta = self._rota(
                metodo, caminho, consulta, corpo, http.headers.get('Content-Type', '')
            )
        except KeyError:
            status, resposta = 404, {'detail': 'Not found'}
        _responder(http, status, resposta)

    def _rota(self, metodo: str, caminho: str, consulta: dict, corpo: bytes, tipo: str) -> tuple[int, object]:
        partes = caminho.strip('/').split('/')
        if caminho == '/health':
            return 200, {'status': 'healthy'}
        if partes[:2] == ['api', 'notebooks']:
            return self._notebooks(metodo, partes[2:], corpo)
        if partes[:2] == ['api', 'sources']:
            return self._sources(metodo, partes[2:], consulta, corpo, tipo)
        if partes[:2] == ['api', 'notes']:
            return self._notas(metodo, partes[2:], consulta, corpo)
        if caminho == '/api/search' and metodo == 'POST':
            pedido = json.loads(corpo)
            if pedido.get('type') == 'vector' and not self.padroes.get('default_embedding_model'):
                return 400, {'detail': 'Vector search requires an embedding model.'}
            return 200, self._buscar(pedido)
        if caminho == '/api/search/ask/simple' and metodo == 'POST':
            pedido = json.loads(corpo)
            for papel in ('strategy_model', 'answer_model', 'final_answer_model'):
                self.modelos[pedido[papel]]
            return 200, {'answer': self.resposta_ask, 'question': pedido['question']}
        if caminho == '/api/embed' and metodo == 'POST':
            pedido = json.loads(corpo)
            if not self.padroes.get('default_embedding_model'):
                return 400, {'detail': 'No embedding model configured.'}
            self.sources[pedido['item_id']]
            self.reprocessados.append(pedido['item_id'])
            return 200, {
                'success': True,
                'message': 'queued',
                'item_id': pedido['item_id'],
                'item_type': 'source',
            }
        if caminho == '/api/models/defaults':
            if metodo == 'PUT':
                self.padroes.update(json.loads(corpo))
            return 200, dict(self.padroes)
        if partes[:2] == ['api', 'models']:
            return self._modelos(metodo, partes[2:], consulta, corpo)
        return 404, {'detail': 'Not found'}

    def _modelos(self, metodo: str, resto: list[str], consulta: dict, corpo: bytes) -> tuple[int, object]:
        if not resto and metodo == 'GET':
            tipo = consulta.get('type')
            return 200, [m for m in self.modelos.values() if not tipo or m['type'] == tipo]
        if not resto and metodo == 'POST':
            dados = json.loads(corpo)
            if any(
                (m['name'].lower(), m['provider'], m['type'])
                == (dados['name'].lower(), dados['provider'], dados['type'])
                for m in self.modelos.values()
            ):
                return 400, {'detail': 'already exists'}
            modelo = self._novo(
                'model', {k: dados.get(k) for k in ('name', 'provider', 'type', 'credential')}
            )
            self.modelos[modelo['id']] = modelo
            return 200, modelo
        if len(resto) == 1 and metodo == 'DELETE':
            del self.modelos[resto[0]]
            return 200, {'message': 'deleted'}
        return 404, {'detail': 'Not found'}

    def _notebooks(self, metodo: str, resto: list[str], corpo: bytes) -> tuple[int, object]:
        if not resto and metodo == 'GET':
            ordenados = sorted(self.notebooks.values(), key=lambda n: n['created'])
            return 200, [n for n in ordenados if not n['archived']]
        if not resto and metodo == 'POST':
            dados = json.loads(corpo)
            notebook = self.criar_notebook(dados['name'])
            notebook['description'] = dados.get('description', '')
            return 200, notebook
        notebook = self.notebooks[resto[0]]
        if len(resto) == 1 and metodo == 'GET':
            return 200, notebook
        if len(resto) == 3 and resto[1] == 'sources':
            self.sources[resto[2]]
            if metodo == 'POST':
                self.vinculos.add((resto[2], notebook['id']))
            else:
                self.vinculos.discard((resto[2], notebook['id']))
            return 200, {'message': 'ok'}
        return 404, {'detail': 'Not found'}

    def _sources(
        self, metodo: str, resto: list[str], consulta: dict, corpo: bytes, tipo: str
    ) -> tuple[int, object]:
        if not resto and metodo == 'GET':
            lista = self.sources_do_notebook(consulta['notebook_id'])
            inicio = int(consulta.get('offset', 0))
            fim = inicio + int(consulta.get('limit', 50))
            return 200, [{k: v for k, v in s.items() if k != 'full_text'} for s in lista[inicio:fim]]
        if not resto and metodo == 'POST':
            campos, arquivo = _ler_multipart(corpo, tipo)
            notebooks = json.loads(campos.get('notebooks', '[]'))
            for notebook_id in notebooks:
                self.notebooks[notebook_id]
            texto = (
                campos.get('content')
                if campos['type'] == 'text'
                else (arquivo or b'').decode('utf-8', 'replace')
            )
            source = self._novo(
                'source', {'title': campos.get('title'), 'full_text': texto, 'campos': campos}
            )
            self.sources[source['id']] = source
            for notebook_id in notebooks:
                self.vinculos.add((source['id'], notebook_id))
            return 200, source
        source = self.sources[resto[0]]
        if len(resto) == 2 and resto[1] == 'status':
            status = self.status_sources.get(source['id'], 'completed')
            return 200, {'status': status, 'message': 'ok', 'processing_info': None, 'command_id': None}
        if metodo == 'GET':
            return 200, source
        if metodo == 'PUT':
            source['title'] = json.loads(corpo).get('title', source['title'])
            return 200, source
        if metodo == 'DELETE':
            del self.sources[source['id']]
            self.vinculos = {(s, n) for s, n in self.vinculos if s != source['id']}
            return 200, {'message': 'deleted'}
        return 404, {'detail': 'Not found'}

    def _notas(self, metodo: str, resto: list[str], consulta: dict, corpo: bytes) -> tuple[int, object]:
        if not resto and metodo == 'GET':
            return 200, self.notas_do_notebook(consulta['notebook_id'])
        if not resto and metodo == 'POST':
            dados = json.loads(corpo)
            nota = self._novo('note', {k: dados.get(k) for k in ('title', 'content', 'note_type')})
            self.notas[nota['id']] = nota
            if dados.get('notebook_id'):
                self.notebooks[dados['notebook_id']]
                self.vinculos_notas.add((nota['id'], dados['notebook_id']))
            return 200, nota
        nota = self.notas[resto[0]]
        if metodo == 'PUT':
            nota.update({k: v for k, v in json.loads(corpo).items() if v is not None})
            return 200, nota
        return 404, {'detail': 'Not found'}

    def _buscar(self, pedido: dict) -> dict:
        termos = pedido['query'].lower().split()
        escopo = set(pedido.get('notebook_ids') or [])
        resultados = []
        for source in self.sources.values():
            if escopo and not any((source['id'], n) in self.vinculos for n in escopo):
                continue
            texto = f'{source.get("title") or ""} {source.get("full_text") or ""}'.lower()
            relevancia = sum(texto.count(termo) for termo in termos)
            if relevancia:
                resultados.append(
                    {
                        'id': source['id'],
                        'parent_id': source['id'],
                        'title': source['title'],
                        'relevance': relevancia,
                    }
                )
        resultados.sort(key=lambda r: -r['relevance'])
        return {
            'results': resultados[: pedido.get('limit', 100)],
            'total_count': len(resultados),
            'search_type': 'text',
        }


def _ler_multipart(corpo: bytes, tipo: str) -> tuple[dict[str, str], bytes | None]:
    mensagem = BytesParser(policy=HTTP).parsebytes(f'Content-Type: {tipo}\r\n\r\n'.encode() + corpo)
    campos: dict[str, str] = {}
    arquivo = None
    for parte in mensagem.iter_parts():
        nome = parte.get_param('name', header='content-disposition')
        conteudo = parte.get_payload(decode=True)
        if parte.get_filename():
            arquivo = conteudo
        else:
            campos[nome] = conteudo.decode('utf-8')
    return campos, arquivo


def _responder(http: BaseHTTPRequestHandler, status: int, corpo: object) -> None:
    dados = json.dumps(corpo).encode('utf-8')
    http.send_response(status)
    http.send_header('Content-Type', 'application/json')
    http.send_header('Content-Length', str(len(dados)))
    http.end_headers()
    http.wfile.write(dados)
