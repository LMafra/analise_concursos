import base64
import importlib.util
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from concursos import atualizador

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def script():
    especificacao = importlib.util.spec_from_file_location(
        'assinar_manifesto', RAIZ / 'scripts' / 'assinar_manifesto.py'
    )
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def chave(monkeypatch) -> str:
    privada = Ed25519PrivateKey.generate()
    publica = privada.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    monkeypatch.setattr(atualizador, 'CHAVES_PUBLICAS', (base64.b64encode(publica).decode(),))
    return privada.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


def release(pasta: Path, versao: str = '0.6.0') -> Path:
    pasta.mkdir(exist_ok=True)
    (pasta / f'concurso-analise-{versao}-windows-x64-setup.exe').write_bytes(b'win')
    (pasta / f'concurso-analise-{versao}-linux-x86_64.AppImage').write_bytes(b'linux')
    (pasta / 'SHA256SUMS').write_text('x')
    return pasta


def test_assina_e_confere_a_release(script, chave, tmp_path):
    pasta = release(tmp_path / 'dist')

    script.assinar('0.6.0', pasta, chave, '2026-12-01')

    assert script.conferir(pasta) == '0.6.0 (stable): assinatura e SHA-256 conferem'


def test_recusa_chave_que_nao_esta_no_pacote(script, chave, tmp_path):
    outra = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )

    with pytest.raises(SystemExit, match='CHAVES_PUBLICAS'):
        script.assinar('0.6.0', release(tmp_path / 'dist'), outra.decode(), '2026-12-01')


def test_recusa_release_sem_os_dois_artefatos(script, chave, tmp_path):
    pasta = release(tmp_path / 'dist')
    (pasta / 'concurso-analise-0.6.0-linux-x86_64.AppImage').unlink()

    with pytest.raises(SystemExit, match='linux-x86_64'):
        script.assinar('0.6.0', pasta, chave, '2026-12-01')


def test_conferir_pega_artefato_trocado(script, chave, tmp_path):
    pasta = release(tmp_path / 'dist')
    script.assinar('0.6.0', pasta, chave, '2026-12-01')
    (pasta / 'concurso-analise-0.6.0-windows-x64-setup.exe').write_bytes(b'outro')

    with pytest.raises(Exception, match='SHA-256'):
        script.conferir(pasta)


def test_assina_o_manifesto_do_pacote_de_estudo(script, chave, tmp_path):
    from concursos.estudo import manifesto

    pasta = tmp_path / 'estudo'
    pasta.mkdir()
    arquivos = []
    for sufixo in manifesto.SUFIXOS.values():
        arquivo = pasta / f'estudo-1.15.1-1-{sufixo}'
        arquivo.write_bytes(sufixo.encode())
        arquivos.append(arquivo)
    (pasta / manifesto.ARQUIVO_MANIFESTO).write_bytes(
        manifesto.montar_manifesto(
            open_notebook='1.15.1',
            revisao=1,
            app_minimo='0.7.0b1',
            publicado_em='2026-11-06',
            modelo={'nome': 'm'},
            arquivos=arquivos,
            extraidos={'windows-x64': 1, 'linux-x86_64': 1},
        )
    )

    assinatura = script.assinar_estudo(pasta, chave)

    manifesto.conferir_assinatura((pasta / manifesto.ARQUIVO_MANIFESTO).read_bytes(), assinatura.read_bytes())
    arquivos[0].write_bytes(b'trocado')
    with pytest.raises(Exception, match='SHA-256'):
        script.assinar_estudo(pasta, chave)


def test_gerar_chave_nao_sobrescreve_e_fica_so_para_o_dono(script, tmp_path):
    destino = tmp_path / 'chave.pem'

    publica = script.gerar_chave(destino)

    assert len(base64.b64decode(publica)) == 32
    assert os.name == 'nt' or destino.stat().st_mode & 0o777 == 0o600
    with pytest.raises(SystemExit, match='já existe'):
        script.gerar_chave(destino)
