import zipfile

import pytest
from livros_sinteticos import docx, epub

from concursos.erros import ErroDoUsuario
from concursos.livros import validacao


def test_aceita_os_quatro_formatos(tmp_path):
    pdf = tmp_path / 'a.PDF'
    pdf.write_bytes(b'%PDF-1.7\n...')
    txt = tmp_path / 'b.txt'
    txt.write_text('texto', encoding='utf-8')

    assert validacao.validar(pdf) == '.pdf'
    assert validacao.validar(txt) == '.txt'
    assert validacao.validar(epub(tmp_path / 'c.epub', ['x'])) == '.epub'
    assert validacao.validar(docx(tmp_path / 'd.docx', ['x'])) == '.docx'


@pytest.mark.parametrize(
    ('nome', 'conteudo', 'motivo'),
    [
        ('a.exe', b'MZ', 'formato não aceito'),
        ('b.pdf', b'', 'vazio'),
        ('c.pdf', b'<html>', 'não é de um PDF'),
        ('d.epub', b'%PDF-1.4', 'não corresponde'),
        ('e.txt', b'\x00\x01\x02', 'não é de um texto'),
    ],
)
def test_recusa_com_mensagem_leiga(tmp_path, nome, conteudo, motivo):
    caminho = tmp_path / nome
    caminho.write_bytes(conteudo)

    with pytest.raises(ErroDoUsuario, match=motivo) as erro:
        validacao.validar(caminho)
    assert 'PDF, EPUB, DOCX ou TXT' in erro.value.dica


def test_recusa_acima_de_300_mb(tmp_path, monkeypatch):
    caminho = tmp_path / 'grande.pdf'
    caminho.write_bytes(b'%PDF-1.7')
    monkeypatch.setattr(validacao, 'LIMITE_BYTES', 4)

    with pytest.raises(ErroDoUsuario, match='limite de 300 MB'):
        validacao.validar(caminho)


def test_recusa_zip_bomba(tmp_path):
    caminho = tmp_path / 'bomba.docx'
    with zipfile.ZipFile(caminho, 'w', zipfile.ZIP_DEFLATED) as arquivo:
        arquivo.writestr('word/document.xml', b'0' * 10_000_000)

    with pytest.raises(ErroDoUsuario, match='grande demais'):
        validacao.validar(caminho)


def test_docx_sem_documento_nao_e_docx(tmp_path):
    caminho = tmp_path / 'falso.docx'
    with zipfile.ZipFile(caminho, 'w') as arquivo:
        arquivo.writestr('outra/coisa.xml', 'x')

    with pytest.raises(ErroDoUsuario, match='não corresponde'):
        validacao.validar(caminho)
