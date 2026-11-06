import zipfile
from pathlib import Path

from concursos.erros import ErroDoUsuario

EXTENSOES = ('.pdf', '.epub', '.docx', '.txt')
LIMITE_BYTES = 300 * 1024 * 1024
LIMITE_EXTRAIDO = 1024 * 1024 * 1024
TAXA_MAXIMA_COMPRESSAO = 100
AMOSTRA_TEXTO = 64 * 1024
DICA_FORMATOS = 'envie um PDF, EPUB, DOCX ou TXT de até 300 MB'


def _recusar(caminho: Path, motivo: str) -> ErroDoUsuario:
    return ErroDoUsuario(f'{caminho.name}: {motivo}', DICA_FORMATOS)


def _conferir_zip(caminho: Path, obrigatorio: str) -> None:
    try:
        with zipfile.ZipFile(caminho) as arquivo:
            nomes = set(arquivo.namelist())
            extraido = sum(info.file_size for info in arquivo.infolist())
            comprimido = sum(info.compress_size for info in arquivo.infolist()) or 1
    except zipfile.BadZipFile as erro:
        raise _recusar(caminho, 'o arquivo está corrompido') from erro
    if obrigatorio not in nomes:
        raise _recusar(caminho, 'o conteúdo não corresponde à extensão')
    if extraido > LIMITE_EXTRAIDO or extraido / comprimido > TAXA_MAXIMA_COMPRESSAO:
        raise _recusar(caminho, 'o arquivo descompactado ficaria grande demais')


def validar(caminho: Path) -> str:
    """Confere extensão, conteúdo e tamanho antes de copiar o livro; devolve a extensão em minúsculas."""
    extensao = caminho.suffix.lower()
    if extensao not in EXTENSOES:
        raise _recusar(caminho, 'formato não aceito')
    tamanho = caminho.stat().st_size
    if tamanho == 0:
        raise _recusar(caminho, 'o arquivo está vazio')
    if tamanho > LIMITE_BYTES:
        raise _recusar(caminho, f'tem {tamanho // (1024 * 1024)} MB, acima do limite de 300 MB')
    with caminho.open('rb') as arquivo:
        inicio = arquivo.read(AMOSTRA_TEXTO)
    if extensao == '.pdf':
        if b'%PDF-' not in inicio[:1024]:
            raise _recusar(caminho, 'o conteúdo não é de um PDF')
    elif extensao in ('.epub', '.docx'):
        if not inicio.startswith(b'PK\x03\x04'):
            raise _recusar(caminho, 'o conteúdo não corresponde à extensão')
        _conferir_zip(caminho, 'mimetype' if extensao == '.epub' else 'word/document.xml')
    elif b'\x00' in inicio:
        raise _recusar(caminho, 'o conteúdo não é de um texto')
    return extensao
