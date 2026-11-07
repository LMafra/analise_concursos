"""Embeddings compatíveis com a API da OpenAI (`POST /v1/embeddings`), só em 127.0.0.1 e com token.

Roda com o Python do pacote de estudo, que tem onnxruntime, tokenizers e numpy:

    python servidor_embeddings.py --porta 0 --modelo <pasta do modelo>

O token vem da variável `EMBEDDINGS_TOKEN`; sem ela, o servidor não sobe. A porta escolhida é
impressa na primeira linha da saída (`porta=<n>`), para quem passou `--porta 0`.
"""

import argparse
import contextlib
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = '127.0.0.1'
MAX_TOKENS = 128
LOTE = 32
LIMITE_CORPO = 8 * 1024 * 1024
LIMITE_TEXTOS = 2048
NOME_MODELO = 'paraphrase-multilingual-MiniLM-L12-v2'


def media_normalizada(saida, mascara):  # noqa: ANN001, ANN201
    """Média dos vetores dos tokens reais (mean pooling), normalizada para comprimento 1."""
    import numpy as np

    peso = mascara[..., None].astype(saida.dtype)
    soma = (saida * peso).sum(axis=1)
    contagem = np.clip(peso.sum(axis=1), 1e-9, None)
    media = soma / contagem
    norma = np.clip(np.linalg.norm(media, axis=1, keepdims=True), 1e-12, None)
    return media / norma


class CodificadorOnnx:
    def __init__(self, pasta: Path) -> None:
        import onnxruntime
        from tokenizers import Tokenizer

        self.tokenizador = Tokenizer.from_file(str(pasta / 'tokenizer.json'))
        self.tokenizador.enable_truncation(MAX_TOKENS)
        self.tokenizador.enable_padding()
        opcoes = onnxruntime.SessionOptions()
        opcoes.intra_op_num_threads = max(1, (os.cpu_count() or 2) // 2)
        self.sessao = onnxruntime.InferenceSession(
            str(pasta / 'model_optimized.onnx'), opcoes, providers=['CPUExecutionProvider']
        )
        self.entradas = {entrada.name for entrada in self.sessao.get_inputs()}

    def __call__(self, textos: list[str]) -> list[list[float]]:
        import numpy as np

        vetores = []
        for inicio in range(0, len(textos), LOTE):
            codificados = self.tokenizador.encode_batch(textos[inicio : inicio + LOTE])
            ids = np.array([c.ids for c in codificados], dtype=np.int64)
            mascara = np.array([c.attention_mask for c in codificados], dtype=np.int64)
            entrada = {'input_ids': ids, 'attention_mask': mascara}
            if 'token_type_ids' in self.entradas:
                entrada['token_type_ids'] = np.zeros_like(ids)
            saida = self.sessao.run(None, entrada)[0]
            vetores.extend(media_normalizada(saida, mascara).tolist())
        return vetores


def textos_da_requisicao(corpo: object) -> list[str]:
    if not isinstance(corpo, dict) or 'input' not in corpo:
        raise ValueError('falta input')
    entrada = corpo['input']
    textos = [entrada] if isinstance(entrada, str) else entrada
    if not isinstance(textos, list) or not all(isinstance(t, str) for t in textos):
        raise ValueError('input deve ser texto ou lista de textos')
    if len(textos) > LIMITE_TEXTOS:
        raise ValueError(f'no máximo {LIMITE_TEXTOS} textos por chamada')
    return textos


def resposta(vetores: list[list[float]], textos: list[str]) -> dict:
    return {
        'object': 'list',
        'data': [{'object': 'embedding', 'index': i, 'embedding': v} for i, v in enumerate(vetores)],
        'model': NOME_MODELO,
        'usage': {'prompt_tokens': sum(len(t.split()) for t in textos), 'total_tokens': 0},
    }


def criar_servidor(porta: int, token: str, codificar) -> ThreadingHTTPServer:  # noqa: ANN001
    if not token:
        raise SystemExit('defina EMBEDDINGS_TOKEN')
    esperado = f'Bearer {token}'.encode()

    class Tratador(BaseHTTPRequestHandler):
        def log_message(self, formato, *args):  # noqa: ANN001, ANN002
            pass

        def _responder(self, codigo: int, corpo: dict) -> None:
            dados = json.dumps(corpo).encode()
            self.send_response(codigo)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def _autorizado(self) -> bool:
            recebido = (self.headers.get('Authorization') or '').encode()
            return hmac.compare_digest(recebido, esperado)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == '/health':
                self._responder(200, {'status': 'ok'})
            elif self.path == '/v1/models' and self._autorizado():
                self._responder(200, {'object': 'list', 'data': [{'id': NOME_MODELO, 'object': 'model'}]})
            else:
                self._responder(404 if self._autorizado() else 401, {'error': 'não encontrado'})

        def do_POST(self) -> None:  # noqa: N802
            if not self._autorizado():
                self._responder(401, {'error': {'message': 'token inválido'}})
                return
            if self.path != '/v1/embeddings':
                self._responder(404, {'error': {'message': 'não encontrado'}})
                return
            tamanho = int(self.headers.get('Content-Length') or 0)
            if tamanho <= 0 or tamanho > LIMITE_CORPO:
                self._responder(413, {'error': {'message': 'corpo vazio ou grande demais'}})
                return
            try:
                textos = textos_da_requisicao(json.loads(self.rfile.read(tamanho)))
            except (ValueError, json.JSONDecodeError) as erro:
                self._responder(400, {'error': {'message': str(erro)}})
                return
            self._responder(200, resposta(codificar(textos) if textos else [], textos))

    return ThreadingHTTPServer((HOST, porta), Tratador)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--porta', type=int, default=0)
    parser.add_argument('--modelo', type=Path, required=True)
    args = parser.parse_args(argv)
    servidor = criar_servidor(
        args.porta, os.environ.get('EMBEDDINGS_TOKEN', ''), CodificadorOnnx(args.modelo)
    )
    sys.stdout.write(f'porta={servidor.server_address[1]}\n')
    sys.stdout.flush()
    with contextlib.suppress(KeyboardInterrupt):
        servidor.serve_forever()
    return 0


if __name__ == '__main__':
    sys.exit(main())
