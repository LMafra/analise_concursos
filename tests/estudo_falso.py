"""Processo falso do open-notebook para os testes do supervisor: responde `/health` na porta pedida.

    python estudo_falso.py <porta|-> <arquivo de registro> [--falhar]

Grava no registro uma linha JSON com a porta, o host e as variáveis de ambiente recebidas. Com `-`, não
abre porta nenhuma (como o worker).
"""

import json
import os
import socketserver
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


class Tratador(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):  # noqa: N802
        if self.path == '/api/config':
            with open(sys.argv[2] + '.config', 'a') as arquivo:
                arquivo.write('chamado\n')
        self.send_response(200 if self.path == '/health' else 404)
        self.end_headers()


class Servidor(HTTPServer):
    def server_bind(self):
        # O HTTPServer chama socket.getfqdn, que leva dezenas de segundos nos runners do macOS.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


def main() -> None:
    porta, registro = sys.argv[1], sys.argv[2]
    if '--falhar' in sys.argv:
        sys.exit(3)
    servidor = None if porta == '-' else Servidor(('127.0.0.1', int(porta)), Tratador)
    with open(registro, 'a', encoding='utf-8') as arquivo:
        host = servidor.server_address[0] if servidor else None
        arquivo.write(
            json.dumps({'pid': os.getpid(), 'porta': porta, 'host': host, 'env': dict(os.environ)}) + '\n'
        )
    if servidor:
        servidor.serve_forever()
    while True:
        time.sleep(1)


if __name__ == '__main__':
    main()
