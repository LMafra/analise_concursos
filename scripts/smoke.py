"""Smoke test de ponta a ponta num concurso sintético. Só usa a biblioteca padrão, para rodar antes da instalação.

Uso:
    python scripts/smoke.py                                   # usa o concurso-analise do PATH
    python scripts/smoke.py uvx --from . concurso-analise     # o que o candidato roda
    python scripts/smoke.py congelado <concurso-analise-cli>  # o executável do PyInstaller
    python scripts/smoke.py estudo <pacote> [comando...]      # a biblioteca com o pacote de estudo
    python scripts/smoke.py fixture <destino.pdf>             # só o PDF do modo estudo, para o checklist manual

Confere, num projeto temporário com espaço e acento no caminho:
- `--dry-run --yes` num projeto novo não grava nada;
- `--yes` faz o onboarding e gera o index.html em até LIMITE_SEGUNDOS;
- duas execuções seguidas, e duas com `--dry-run`, não alteram nenhum mtime em analises/.

No modo `congelado`, antes: `--smoke` do executável (versão, perfis, Tesseract com português e a GUI em
127.0.0.1) e `doctor` sem erro.

No modo `estudo`: instala o pacote de estudo do arquivo, adiciona um PDF de fixture (uma página de texto e
uma só com imagem), espera o envio ao open-notebook e pergunta; o trecho tem de vir com a página e sem o
aviso de open-notebook fora. A página escaneada é conferida com o executável (que traz o Tesseract) ou com
o Tesseract no PATH.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

LIMITE_SEGUNDOS = 300
CANDIDATO = 'ana'
CONCURSO_YAML = """\
banca: fgv
formato: multipla_escolha
pontuacao: simples
data_prova: {data}
edital:
  manual: edital_manual.yaml
provas:
  unica:
    gabarito: gabarito.txt
    itens: [1, 10]
"""
GABARITO = ''.join(f'{n} {letra}\n' for n, letra in enumerate('ABCDEABCDE', start=1))
RESPOSTAS = {
    'sintetico_2024': ('2024-03-10', 'ABCDEEDCBA'),
    'sintetico_2025': ('2025-03-09', 'ABCDEABCBA'),
}


def montar_projeto(raiz: Path) -> None:
    for nome, (data, respostas) in RESPOSTAS.items():
        pasta = raiz / 'provas' / nome
        (pasta / 'candidatos' / CANDIDATO).mkdir(parents=True)
        (pasta / 'concurso.yaml').write_text(CONCURSO_YAML.format(data=data), encoding='utf-8')
        (pasta / 'edital_manual.yaml').write_text('conhecimentos: []\n', encoding='utf-8')
        (pasta / 'gabarito.txt').write_text(GABARITO, encoding='utf-8')
        linhas = ''.join(f'{n} {letra}\n' for n, letra in enumerate(respostas, start=1))
        (pasta / 'candidatos' / CANDIDATO / 'respostas.txt').write_text(linhas, encoding='utf-8')


def rodar(comando: list[str], raiz: Path, *argumentos: str, limite: int = LIMITE_SEGUNDOS) -> float:
    ambiente = {**os.environ, 'CONCURSO_HOME': str(raiz / 'home'), 'CI': 'true', 'NO_COLOR': '1'}
    inicio = time.monotonic()
    resultado = subprocess.run([*comando, *argumentos], cwd=raiz, env=ambiente, timeout=limite, check=False)
    duracao = time.monotonic() - inicio
    if resultado.returncode != 0:
        falhar(f'{" ".join(argumentos)} saiu com código {resultado.returncode}')
    return duracao


def capturar(comando: list[str], raiz: Path, *argumentos: str, limite: int = LIMITE_SEGUNDOS) -> str:
    ambiente = {**os.environ, 'CONCURSO_HOME': str(raiz / 'home'), 'CI': 'true', 'NO_COLOR': '1'}
    resultado = subprocess.run(
        [*comando, *argumentos],
        cwd=raiz,
        env=ambiente,
        timeout=limite,
        check=False,
        capture_output=True,
        text=True,
        encoding='utf-8',
    )
    sys.stdout.write(resultado.stdout)
    if resultado.returncode != 0:
        sys.stderr.write(resultado.stderr)
        falhar(f'{" ".join(argumentos)} saiu com código {resultado.returncode}')
    return resultado.stdout


def mtimes(pasta: Path) -> dict[str, int]:
    return {str(p.relative_to(pasta)): p.stat().st_mtime_ns for p in sorted(pasta.rglob('*')) if p.is_file()}


def falhar(mensagem: str) -> None:
    sys.stderr.write(f'smoke: FALHOU: {mensagem}\n')
    sys.exit(1)


def main(comando: list[str]) -> None:
    base = Path(tempfile.mkdtemp())
    raiz = base / 'meus concursos ação'
    try:
        montar_projeto(raiz)

        rodar(comando, raiz, '--dry-run', '--yes')
        if (raiz / 'analises').exists() or (raiz / '.concurso').exists():
            falhar('--dry-run num projeto novo gravou arquivos')

        duracao = rodar(comando, raiz, '--yes', '--no-open', '--candidate', CANDIDATO)
        indice = raiz / 'analises' / CANDIDATO / 'index.html'
        if not indice.exists():
            falhar(f'{indice} não foi gerado')
        sys.stdout.write(f'smoke: onboarding e análise em {duracao:.1f}s\n')

        antes = mtimes(raiz / 'analises')
        rodar(comando, raiz, '--yes', '--no-open')
        rodar(comando, raiz, '--dry-run', '--yes')
        rodar(comando, raiz, '--dry-run', '--yes')
        mudados = sorted(k for k, v in mtimes(raiz / 'analises').items() if antes.get(k) != v)
        if mudados:
            falhar(f'reexecução alterou {", ".join(mudados)}')
        sys.stdout.write('smoke: ok\n')
    finally:
        shutil.rmtree(base, ignore_errors=True)


def congelado(executavel: str) -> None:
    if Path(executavel).exists():
        executavel = str(Path(executavel).resolve())
    base = Path(tempfile.mkdtemp())
    raiz = base / 'pré-checagem'
    raiz.mkdir()
    try:
        rodar([executavel], raiz, '--smoke')
        rodar([executavel], raiz, 'doctor')
    finally:
        shutil.rmtree(base, ignore_errors=True)
    main([executavel])


LIMITE_ESTUDO = 1800
TEXTO_DO_LIVRO = 'A autarquia e pessoa juridica de direito publico interno, criada por lei especifica.'
PALAVRA_ESCANEADA = 'LICITACAO'
AVISO_FORA = 'não abriu agora'
GLIFOS = {
    'A': ('01110', '10001', '10001', '11111', '10001', '10001', '10001'),
    'C': ('01111', '10000', '10000', '10000', '10000', '10000', '01111'),
    'I': ('11111', '00100', '00100', '00100', '00100', '00100', '11111'),
    'L': ('10000', '10000', '10000', '10000', '10000', '10000', '11111'),
    'O': ('01110', '10001', '10001', '10001', '10001', '10001', '01110'),
    'T': ('11111', '00100', '00100', '00100', '00100', '00100', '00100'),
}


def imagem_da_palavra(palavra: str, escala: int = 10, margem: int = 3) -> tuple[int, int, bytes]:
    """A palavra numa fonte de pixels, em tons de cinza de 8 bits: uma página "escaneada" sem texto."""
    colunas = len(palavra) * 6 - 1 + 2 * margem
    linhas = 7 + 2 * margem
    grade = [[255] * colunas for _ in range(linhas)]
    for indice, letra in enumerate(palavra):
        for y, linha in enumerate(GLIFOS[letra]):
            for x, ponto in enumerate(linha):
                if ponto == '1':
                    grade[margem + y][margem + indice * 6 + x] = 0
    pixels = bytearray()
    for linha in grade:
        expandida = bytes(v for v in linha for _ in range(escala))
        pixels += expandida * escala
    return colunas * escala, linhas * escala, bytes(pixels)


def pdf_de_fixture(destino: Path) -> None:
    """Página 1: capa; página 2: TEXTO_DO_LIVRO; página 3: só a imagem de PALAVRA_ESCANEADA."""
    objetos: list[bytes] = [b'', b'']

    def novo(conteudo: bytes) -> int:
        objetos.append(conteudo)
        return len(objetos)

    def fluxo(dados: bytes, dicionario: bytes = b'') -> bytes:
        return b'<< ' + dicionario + b' /Length %d >>\nstream\n' % len(dados) + dados + b'\nendstream'

    fonte = novo(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
    largura, altura, pixels = imagem_da_palavra(PALAVRA_ESCANEADA)
    imagem = novo(
        fluxo(
            zlib.compress(pixels),
            b'/Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray '
            b'/BitsPerComponent 8 /Filter /FlateDecode' % (largura, altura),
        )
    )
    desenho_w, desenho_h = 216, 216 * altura // largura
    conteudos = [
        b'BT /F1 18 Tf 72 720 Td (Livro de teste do smoke) Tj ET',
        b'BT /F1 12 Tf 72 720 Td (' + TEXTO_DO_LIVRO.encode('ascii') + b') Tj ET',
        b'q %d 0 0 %d 90 500 cm /Im1 Do Q' % (desenho_w, desenho_h),
    ]
    paginas = []
    for conteudo in conteudos:
        corpo = novo(fluxo(conteudo))
        paginas.append(
            novo(
                b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R '
                b'/Resources << /Font << /F1 %d 0 R >> /XObject << /Im1 %d 0 R >> >> >>'
                % (corpo, fonte, imagem)
            )
        )
    objetos[0] = b'<< /Type /Catalog /Pages 2 0 R >>'
    filhos = b' '.join(b'%d 0 R' % n for n in paginas)
    objetos[1] = b'<< /Type /Pages /Kids [' + filhos + b'] /Count %d >>' % len(paginas)
    saida = bytearray(b'%PDF-1.4\n')
    posicoes = []
    for numero, conteudo in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += b'%d 0 obj\n' % numero + conteudo + b'\nendobj\n'
    inicio_xref = len(saida)
    saida += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objetos) + 1)
    saida += b''.join(b'%010d 00000 n \n' % p for p in posicoes)
    saida += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (
        len(objetos) + 1,
        inicio_xref,
    )
    destino.write_bytes(bytes(saida))


def estudo(pacote: str, comando: list[str]) -> None:
    pacote_absoluto = str(Path(pacote).resolve())
    executavel = len(comando) == 1 and Path(comando[0]).is_file()
    if Path(comando[0]).exists():
        comando = [str(Path(comando[0]).resolve()), *comando[1:]]
    base = Path(tempfile.mkdtemp())
    raiz = base / 'estudo ação'
    raiz.mkdir()
    try:
        livro = raiz / 'livro de teste.pdf'
        pdf_de_fixture(livro)
        inicio = time.monotonic()
        rodar(
            comando, raiz, '--yes', 'estudo', 'preparar', '--arquivo', pacote_absoluto, limite=LIMITE_ESTUDO
        )
        sys.stdout.write(f'smoke: pacote de estudo instalado em {time.monotonic() - inicio:.1f}s\n')
        inicio = time.monotonic()
        saida = capturar(comando, raiz, 'livros', 'add', str(livro), limite=LIMITE_ESTUDO)
        if 'Pronto para perguntas' not in saida:
            falhar('o livro não chegou ao open-notebook ("Pronto para perguntas")')
        sys.stdout.write(f'smoke: livro lido e enviado em {time.monotonic() - inicio:.1f}s\n')
        saida = capturar(comando, raiz, 'livros', 'ask', 'autarquia pessoa juridica')
        if AVISO_FORA in saida:
            falhar('o open-notebook não respondeu à pergunta')
        if 'livro de teste, p. 2' not in saida:
            falhar('a pergunta não trouxe o trecho da página 2')
        if executavel or shutil.which('tesseract'):
            saida = capturar(comando, raiz, 'livros', 'ask', PALAVRA_ESCANEADA.lower())
            if 'livro de teste, p. 3' not in saida:
                falhar('a página escaneada (3) não foi lida pelo OCR')
        else:
            sys.stdout.write('smoke: página escaneada não conferida (sem Tesseract no PATH)\n')
        sys.stdout.write('smoke: estudo ok\n')
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == '__main__':
    argumentos = sys.argv[1:]
    if argumentos[:1] == ['congelado'] and len(argumentos) == 2:
        congelado(argumentos[1])
    elif argumentos[:1] == ['fixture'] and len(argumentos) == 2:
        pdf_de_fixture(Path(argumentos[1]))
    elif argumentos[:1] == ['estudo'] and len(argumentos) >= 2:
        estudo(argumentos[1], argumentos[2:] or ['concurso-analise'])
    else:
        main(argumentos or ['concurso-analise'])
