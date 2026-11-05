import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from concursos import atualizador
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.modelo import CanalAtualizacao

CHAVE = Ed25519PrivateKey.generate()
OUTRA = Ed25519PrivateKey.generate()


def publica(chave: Ed25519PrivateKey) -> str:
    return base64.b64encode(chave.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


CHAVES = (publica(CHAVE),)


def manifesto(**mudancas) -> dict:
    dados = {
        'formato': 1,
        'versao': '0.6.0',
        'canal': 'stable',
        'publicado_em': '2026-12-01',
        'notas': 'https://github.com/LMafra/analise_concursos/releases/tag/v0.6.0',
        'artefatos': {
            'windows-x64': {
                'arquivo': 'concurso-analise-0.6.0-windows-x64-setup.exe',
                'sha256': 'a' * 64,
                'tamanho': 1000,
            },
            'linux-x86_64': {
                'arquivo': 'concurso-analise-0.6.0-linux-x86_64.AppImage',
                'sha256': 'b' * 64,
                'tamanho': 2000,
            },
        },
    }
    dados.update(mudancas)
    return dados


def bytes_de(dados: dict) -> bytes:
    return json.dumps(dados).encode()


def test_assinatura_valida_passa_e_qualquer_chave_da_lista_vale():
    conteudo = bytes_de(manifesto())
    assinatura = atualizador.assinar(conteudo, CHAVE)

    atualizador.conferir_assinatura(conteudo, assinatura, CHAVES)
    atualizador.conferir_assinatura(conteudo, assinatura, (publica(OUTRA), *CHAVES))


@pytest.mark.parametrize(
    'adulterar',
    [
        lambda conteudo, assinatura: (conteudo + b' ', assinatura),
        lambda conteudo, assinatura: (conteudo, atualizador.assinar(conteudo, OUTRA)),
        lambda conteudo, assinatura: (conteudo, b''),
        lambda conteudo, assinatura: (conteudo, b'nao e base64!!'),
        lambda conteudo, assinatura: (conteudo, base64.b64encode(b'x' * 10)),
    ],
)
def test_manifesto_adulterado_ou_sem_assinatura_e_recusado(adulterar):
    conteudo = bytes_de(manifesto())
    conteudo, assinatura = adulterar(conteudo, atualizador.assinar(conteudo, CHAVE))

    with pytest.raises(ErroDoAmbiente, match='assinatura'):
        atualizador.conferir_assinatura(conteudo, assinatura, CHAVES)


def test_chaves_publicas_do_pacote_sao_ed25519_validas():
    assert atualizador.CHAVES_PUBLICAS
    for chave in atualizador.CHAVES_PUBLICAS:
        assert len(base64.b64decode(chave)) == 32


def test_le_o_manifesto_valido():
    lido = atualizador.ler_manifesto(bytes_de(manifesto()))

    assert lido.versao == '0.6.0'
    assert lido.canal is CanalAtualizacao.STABLE
    assert lido.artefatos['linux-x86_64'].tamanho == 2000


@pytest.mark.parametrize(
    'mudancas',
    [
        {'formato': 2},
        {'canal': 'nightly'},
        {'versao': 'não é versão'},
        {'artefatos': {}},
        {'artefatos': {'windows-x64': {'arquivo': '../../evil.exe', 'sha256': 'a' * 64, 'tamanho': 1}}},
        {
            'artefatos': {
                'windows-x64': {
                    'arquivo': 'concurso-analise-0.6.0-windows-x64-setup.exe',
                    'sha256': 'zz',
                    'tamanho': 1,
                }
            }
        },
        {
            'artefatos': {
                'windows-x64': {
                    'arquivo': 'concurso-analise-0.6.0-windows-x64-setup.exe',
                    'sha256': 'a' * 64,
                    'tamanho': 0,
                }
            }
        },
        {
            'artefatos': {
                'windows-x64': {
                    'arquivo': 'concurso-analise-0.6.0-linux-x86_64.AppImage',
                    'sha256': 'a' * 64,
                    'tamanho': 1,
                }
            }
        },
    ],
)
def test_manifesto_invalido_e_recusado(mudancas):
    with pytest.raises(ErroDoAmbiente, match='manifesto'):
        atualizador.ler_manifesto(bytes_de(manifesto(**mudancas)))


def test_manifesto_que_nao_e_json_e_recusado():
    with pytest.raises(ErroDoAmbiente, match='manifesto'):
        atualizador.ler_manifesto(b'<html>')


def test_campo_faltando_e_recusado():
    dados = manifesto()
    del dados['versao']

    with pytest.raises(ErroDoAmbiente, match='manifesto'):
        atualizador.ler_manifesto(bytes_de(dados))


@pytest.mark.parametrize(
    ('instalada', 'oferece'),
    [('0.5.0', True), ('0.6.0b2', True), ('0.6.0', False), ('0.6.1', False), ('1.0.0', False)],
)
def test_so_oferece_versao_maior_que_a_instalada(instalada, oferece):
    lido = atualizador.ler_manifesto(bytes_de(manifesto()))

    escolhido = atualizador.escolher(lido, instalada, CanalAtualizacao.STABLE, 'linux-x86_64')

    assert (escolhido is not None) is oferece


def test_cliente_stable_recusa_manifesto_beta():
    lido = atualizador.ler_manifesto(bytes_de(manifesto(canal='beta', versao='0.7.0b1')))

    with pytest.raises(ErroDoAmbiente, match='beta'):
        atualizador.escolher(lido, '0.6.0', CanalAtualizacao.STABLE, 'linux-x86_64')
    assert atualizador.escolher(lido, '0.6.0', CanalAtualizacao.BETA, 'linux-x86_64') is not None


def test_sistema_sem_artefato_nao_oferece():
    dados = manifesto()
    del dados['artefatos']['windows-x64']
    lido = atualizador.ler_manifesto(bytes_de(dados))

    assert atualizador.escolher(lido, '0.5.0', CanalAtualizacao.STABLE, 'windows-x64') is None


def test_url_do_artefato_vem_da_base_da_release_e_do_arquivo():
    lido = atualizador.ler_manifesto(bytes_de(manifesto()))

    url = atualizador.url_do_artefato(lido, lido.artefatos['windows-x64'])

    assert url == (
        'https://github.com/LMafra/analise_concursos/releases/download/v0.6.0/'
        'concurso-analise-0.6.0-windows-x64-setup.exe'
    )


@pytest.mark.parametrize(
    'url',
    [
        'https://github.com/LMafra/analise_concursos/releases/latest/download/atualizacao.json',
        'https://objects.githubusercontent.com/github-production-release-asset/1',
        'https://release-assets.githubusercontent.com/github-production-release-asset/1',
        'https://api.github.com/repos/LMafra/analise_concursos/releases',
    ],
)
def test_urls_do_github_em_https_sao_aceitas(url):
    atualizador.conferir_url(url)


@pytest.mark.parametrize(
    'url',
    [
        'http://github.com/LMafra/analise_concursos/releases/latest/download/atualizacao.json',
        'https://evil.example.com/atualizacao.json',
        'https://github.com.evil.example.com/x',
        'file:///etc/passwd',
        'https://user@evil.example.com/',
    ],
)
def test_url_fora_do_github_ou_sem_https_e_recusada(url):
    with pytest.raises(ErroDoAmbiente):
        atualizador.conferir_url(url)


def test_sha256_confere_o_arquivo(tmp_path):
    arquivo = tmp_path / 'setup.exe'
    arquivo.write_bytes(b'conteudo')
    atualizador.conferir_sha256(arquivo, hashlib.sha256(b'conteudo').hexdigest())

    with pytest.raises(ErroDoAmbiente, match='SHA-256'):
        atualizador.conferir_sha256(arquivo, 'c' * 64)


@pytest.mark.parametrize(('sistema', 'plataforma'), [('win32', 'windows-x64'), ('linux', 'linux-x86_64')])
def test_plataforma_do_sistema(sistema, plataforma):
    assert atualizador.plataforma(sistema) == plataforma


def test_macos_nao_tem_atualizacao_pelo_app():
    with pytest.raises(ErroDoUsuario, match='Windows e no Linux'):
        atualizador.plataforma('darwin')


def test_comando_do_setup_e_silencioso_e_reabre(tmp_path):
    setup = tmp_path / 'setup.exe'

    assert atualizador.comando_do_setup(setup) == [
        str(setup),
        '/SILENT',
        '/SUPPRESSMSGBOXES',
        '/CLOSEAPPLICATIONS',
        '/REABRIR=1',
    ]


def test_consulta_diaria_no_maximo_uma_vez_em_24_horas(tmp_path):
    estado = tmp_path / 'atualizacao.json'
    agora = datetime(2026, 12, 1, 12, tzinfo=UTC)

    assert atualizador.consulta_vencida(estado, agora)
    atualizador.registrar_consulta(estado, agora)
    assert not atualizador.consulta_vencida(estado, agora + timedelta(hours=23))
    assert atualizador.consulta_vencida(estado, agora + timedelta(hours=24))


def test_estado_corrompido_conta_como_vencido(tmp_path):
    estado = tmp_path / 'atualizacao.json'
    estado.write_text('{não é json', encoding='utf-8')

    assert atualizador.consulta_vencida(estado, datetime(2026, 12, 1, tzinfo=UTC))


def test_montar_manifesto_le_os_arquivos_da_release(tmp_path):
    setup = tmp_path / 'concurso-analise-0.6.0b1-windows-x64-setup.exe'
    setup.write_bytes(b'windows')
    appimage = tmp_path / 'concurso-analise-0.6.0b1-linux-x86_64.AppImage'
    appimage.write_bytes(b'linux!')
    (tmp_path / 'concurso-analise-0.6.0b1-macos-arm64.dmg').write_bytes(b'mac')

    conteudo = atualizador.montar_manifesto('0.6.0b1', '2026-12-01', sorted(tmp_path.iterdir()))

    lido = atualizador.ler_manifesto(conteudo)
    assert lido.canal is CanalAtualizacao.BETA
    assert set(lido.artefatos) == {'windows-x64', 'linux-x86_64'}
    assert lido.artefatos['linux-x86_64'].sha256 == hashlib.sha256(b'linux!').hexdigest()
    assert lido.artefatos['linux-x86_64'].tamanho == 6
    assert lido.notas.endswith('/releases/tag/v0.6.0b1')
