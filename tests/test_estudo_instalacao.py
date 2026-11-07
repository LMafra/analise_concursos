import base64
import io
import json
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from concursos import atualizador
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.estudo import instalacao, manifesto
from concursos.estudo.instalacao import Pastas
from concursos.modelo import CanalAtualizacao

LINUX = 'linux'


@pytest.fixture
def chave(monkeypatch):
    privada = Ed25519PrivateKey.generate()
    publica = privada.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    monkeypatch.setattr(atualizador, 'CHAVES_PUBLICAS', (base64.b64encode(publica).decode(),))
    return privada


def pacote_tar(versao: str, conteudo: bytes = b'v') -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:xz') as tar:
        for nome, dados in (
            (f'estudo-{versao}/estudo.toml', f'versao = "{versao}"\n'.encode()),
            (f'estudo-{versao}/x', conteudo),
        ):
            info = tarfile.TarInfo(nome)
            info.size = len(dados)
            tar.addfile(info, io.BytesIO(dados))
    return buffer.getvalue()


class Transporte:
    def __init__(self):
        self.urls: dict[str, bytes] = {}
        self.pedidos: list[str] = []

    def baixar(self, url, limite):
        self.pedidos.append(url)
        return self.urls[url]

    def baixar_para(self, url, destino, limite, progresso=None):
        self.pedidos.append(url)
        dados = self.urls[url]
        destino.write_bytes(dados)
        if progresso:
            progresso(len(dados), limite)


def publicar(transporte, chave, tmp_path, versao, app_minimo='0.7.0', prerelease=False, dados=None):
    nome = f'estudo-{versao}-linux-x86_64.tar.xz'
    arquivo = tmp_path / nome
    arquivo.write_bytes(dados or pacote_tar(versao))
    base, revisao = versao.rsplit('-', 1)
    conteudo = manifesto.montar_manifesto(
        open_notebook=base,
        revisao=int(revisao),
        app_minimo=app_minimo,
        publicado_em='2026-11-06',
        modelo={'nome': 'm'},
        arquivos=[arquivo],
        extraidos={'linux-x86_64': 100},
    )
    transporte.urls[manifesto.url_do_manifesto(versao)] = conteudo
    transporte.urls[manifesto.url_do_manifesto(versao, True)] = atualizador.assinar(conteudo, chave)
    transporte.urls[manifesto.url_do_artefato(versao, manifesto.ArtefatoEstudo(nome, 'a' * 64, 1, 1))] = (
        arquivo.read_bytes()
    )
    releases = json.loads(transporte.urls.get(instalacao.URL_RELEASES, b'[]'))
    releases.append({'tag_name': f'estudo-v{versao}', 'draft': False, 'prerelease': prerelease})
    releases.append({'tag_name': 'v0.7.0', 'draft': False, 'prerelease': False})
    transporte.urls[instalacao.URL_RELEASES] = json.dumps(releases).encode()


def livre_a_vontade(_pasta):
    return 10**12


def test_escolhe_o_mais_novo_compativel_do_canal(chave, tmp_path):
    transporte = Transporte()
    publicar(transporte, chave, tmp_path, '1.15.1-1', app_minimo='0.7.0')
    publicar(transporte, chave, tmp_path, '1.15.1-2', app_minimo='0.8.0')
    publicar(transporte, chave, tmp_path, '1.16.0-1', app_minimo='0.7.0b1', prerelease=True)

    estavel = instalacao.procurar(CanalAtualizacao.STABLE, transporte, '0.7.0', LINUX)
    beta = instalacao.procurar(CanalAtualizacao.BETA, transporte, '0.7.0', LINUX)

    assert estavel.manifesto.versao == '1.15.1-1'
    assert beta.manifesto.versao == '1.16.0-1'


def test_assinatura_invalida_e_recusada(chave, tmp_path):
    transporte = Transporte()
    publicar(transporte, chave, tmp_path, '1.15.1-1')
    transporte.urls[manifesto.url_do_manifesto('1.15.1-1', True)] = atualizador.assinar(
        b'outro', Ed25519PrivateKey.generate()
    )

    with pytest.raises(ErroDoAmbiente, match='assinatura'):
        instalacao.procurar(CanalAtualizacao.STABLE, transporte, '0.7.0', LINUX)


def test_macos_ainda_nao_tem_pacote():
    with pytest.raises(ErroDoUsuario, match='ainda não está disponível'):
        instalacao.plataforma('darwin')


def test_nada_e_baixado_sem_consentimento_ou_offline(chave, tmp_path):
    transporte = Transporte()
    publicar(transporte, chave, tmp_path, '1.15.1-1')
    disponivel = instalacao.procurar(CanalAtualizacao.STABLE, transporte, '0.7.0', LINUX)
    transporte.pedidos.clear()
    pastas = Pastas(tmp_path / 'on')

    with pytest.raises(ErroDoUsuario):
        instalacao.instalar(pastas, disponivel, transporte, consentiu=False, livre=livre_a_vontade)
    with pytest.raises(ErroDoUsuario):
        instalacao.instalar(
            pastas, disponivel, transporte, consentiu=True, offline=True, livre=livre_a_vontade
        )

    assert transporte.pedidos == []


def test_instala_e_guarda_o_anterior(chave, tmp_path):
    transporte = Transporte()
    publicar(transporte, chave, tmp_path, '1.15.1-1')
    pastas = Pastas(tmp_path / 'on')
    primeiro = instalacao.procurar(CanalAtualizacao.STABLE, transporte, '0.7.0', LINUX)
    instalacao.instalar(pastas, primeiro, transporte, consentiu=True, livre=livre_a_vontade)
    publicar(transporte, chave, tmp_path, '1.15.1-2')
    segundo = instalacao.procurar(CanalAtualizacao.STABLE, transporte, '0.7.0', LINUX)
    assert instalacao.tem_atualizacao(pastas, segundo)

    raiz = instalacao.instalar(pastas, segundo, transporte, consentiu=True, livre=livre_a_vontade)

    assert raiz == instalacao.instalado(pastas)
    assert instalacao.ler_estado(pastas).anterior == '1.15.1-1'
    assert not instalacao.tem_atualizacao(pastas, segundo)


def test_sha_divergente_descarta(chave, tmp_path):
    transporte = Transporte()
    publicar(transporte, chave, tmp_path, '1.15.1-1')
    disponivel = instalacao.procurar(CanalAtualizacao.STABLE, transporte, '0.7.0', LINUX)
    transporte.urls[disponivel.url] = pacote_tar('1.15.1-1', b'adulterado')
    pastas = Pastas(tmp_path / 'on')

    with pytest.raises(ErroDoAmbiente, match='diferente do publicado'):
        instalacao.instalar(pastas, disponivel, transporte, consentiu=True, livre=livre_a_vontade)

    assert instalacao.instalado(pastas) is None
    assert not list(pastas.base.glob('.baixando-*'))


def test_falta_de_espaco_avisa_antes_de_baixar(chave, tmp_path):
    transporte = Transporte()
    publicar(transporte, chave, tmp_path, '1.15.1-1')
    disponivel = instalacao.procurar(CanalAtualizacao.STABLE, transporte, '0.7.0', LINUX)
    transporte.pedidos.clear()

    with pytest.raises(ErroDoUsuario, match='espaço no disco'):
        instalacao.instalar(
            Pastas(tmp_path / 'on'), disponivel, transporte, consentiu=True, livre=lambda _p: 10
        )

    assert transporte.pedidos == []


def test_zip_com_caminho_para_fora_e_recusado(tmp_path):
    arquivo = tmp_path / 'p.zip'
    with zipfile.ZipFile(arquivo, 'w') as pacote:
        pacote.writestr('../fora.txt', 'x')

    with pytest.raises(ErroDoAmbiente, match='caminho inválido'):
        instalacao.extrair(arquivo, tmp_path / 'destino')
    assert not (tmp_path / 'fora.txt').exists()


def preparar_instalado(tmp_path) -> Pastas:
    pastas = Pastas(tmp_path / 'on')
    for versao in ('1.15.1-1', '1.15.1-2'):
        arquivo = tmp_path / f'{versao}.tar.xz'
        arquivo.write_bytes(pacote_tar(versao))
        instalacao.instalar_arquivo(pastas, arquivo, versao)
    pastas.banco.mkdir(parents=True)
    (pastas.banco / 'dados.sst').write_bytes(b'banco-antigo')
    return pastas


def test_backup_verificado_e_rotacao_dos_dois_mais_novos(tmp_path):
    pastas = preparar_instalado(tmp_path)
    assert instalacao.precisa_de_backup(pastas)

    for dia in (1, 2, 3):
        instalacao.fazer_backup(pastas, '1.15.1-2', datetime(2026, 11, dia))

    copias = sorted(p.name for p in pastas.backups.iterdir())
    assert copias == ['20261102-000000-1.15.1-2', '20261103-000000-1.15.1-2']
    assert (pastas.backups / copias[-1] / 'banco' / 'dados.sst').read_bytes() == b'banco-antigo'
    instalacao.registrar_partida(pastas)
    assert not instalacao.precisa_de_backup(pastas)


def test_volta_ao_pacote_e_ao_banco_anteriores(tmp_path):
    pastas = preparar_instalado(tmp_path)
    instalacao.fazer_backup(pastas, '1.15.1-2', datetime(2026, 11, 1))
    (pastas.banco / 'dados.sst').write_bytes(b'migrado-e-quebrado')

    restaurada = instalacao.voltar_ao_anterior(pastas)

    assert restaurada == '1.15.1-1'
    assert instalacao.instalado(pastas) == instalacao.raiz_do_pacote(pastas, '1.15.1-1')
    assert (pastas.banco / 'dados.sst').read_bytes() == b'banco-antigo'


def test_sem_anterior_nao_volta(tmp_path):
    pastas = Pastas(tmp_path / 'on')
    arquivo = tmp_path / 'p.tar.xz'
    arquivo.write_bytes(pacote_tar('1.15.1-1'))
    instalacao.instalar_arquivo(pastas, arquivo, '1.15.1-1')

    assert instalacao.voltar_ao_anterior(pastas) is None
    assert isinstance(instalacao.instalado(pastas), Path)
