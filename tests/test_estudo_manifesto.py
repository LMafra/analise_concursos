import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from concursos import atualizador
from concursos.erros import ErroDoAmbiente
from concursos.estudo import manifesto
from concursos.modelo import CanalAtualizacao

MODELO = {'nome': 'paraphrase-multilingual-MiniLM-L12-v2', 'revisao': 'abc', 'dimensoes': 384}


def pacotes(pasta, versao='1.15.1-1'):
    pasta.mkdir(exist_ok=True)
    (pasta / f'estudo-{versao}-windows-x64.zip').write_bytes(b'win')
    (pasta / f'estudo-{versao}-linux-x86_64.tar.xz').write_bytes(b'linux')
    return sorted(pasta.iterdir())


def test_monta_e_le_o_manifesto(tmp_path):
    conteudo = manifesto.montar_manifesto(
        open_notebook='1.15.1',
        revisao=1,
        app_minimo='0.7.0b1',
        publicado_em='2026-11-06',
        modelo=MODELO,
        arquivos=pacotes(tmp_path),
        extraidos={'windows-x64': 10, 'linux-x86_64': 20},
    )

    lido = manifesto.ler_manifesto(conteudo)

    assert lido.versao == '1.15.1-1'
    assert lido.canal is CanalAtualizacao.BETA
    assert lido.app_minimo == '0.7.0b1'
    assert lido.artefatos['linux-x86_64'].arquivo == 'estudo-1.15.1-1-linux-x86_64.tar.xz'
    assert lido.artefatos['linux-x86_64'].tamanho_extraido == 20
    assert manifesto.tag(lido.versao) == 'estudo-v1.15.1-1'


def test_app_minimo_estavel_vira_canal_stable(tmp_path):
    conteudo = manifesto.montar_manifesto(
        open_notebook='1.15.1',
        revisao=2,
        app_minimo='0.7.0',
        publicado_em='2026-11-06',
        modelo=MODELO,
        arquivos=pacotes(tmp_path, '1.15.1-2'),
        extraidos={'windows-x64': 1, 'linux-x86_64': 1},
    )

    assert manifesto.ler_manifesto(conteudo).canal is CanalAtualizacao.STABLE


@pytest.mark.parametrize(
    'arquivo',
    ['../estudo-1.15.1-1-linux-x86_64.tar.xz', 'estudo-1.15.1-1-windows-x64.zip', 'outro.tar.xz'],
)
def test_recusa_arquivo_fora_do_padrao_ou_de_outro_sistema(arquivo):
    dados = {
        'formato': 1,
        'versao': '1.15.1-1',
        'open_notebook': '1.15.1',
        'app_minimo': '0.7.0',
        'canal': 'stable',
        'publicado_em': '2026-11-06',
        'modelo': MODELO,
        'artefatos': {
            'linux-x86_64': {'arquivo': arquivo, 'sha256': 'a' * 64, 'tamanho': 1, 'tamanho_extraido': 1}
        },
    }

    with pytest.raises(ErroDoAmbiente):
        manifesto.ler_manifesto(json.dumps(dados).encode())


def test_compatibilidade_pelo_app_minimo(tmp_path):
    conteudo = manifesto.montar_manifesto(
        open_notebook='1.15.1',
        revisao=1,
        app_minimo='0.7.0',
        publicado_em='2026-11-06',
        modelo=MODELO,
        arquivos=pacotes(tmp_path),
        extraidos={'windows-x64': 1, 'linux-x86_64': 1},
    )
    lido = manifesto.ler_manifesto(conteudo)

    assert manifesto.compativel(lido, '0.7.0')
    assert manifesto.compativel(lido, '0.8.0')
    assert not manifesto.compativel(lido, '0.7.0b1')


def test_assinatura_com_a_chave_do_atualizador(tmp_path, monkeypatch):
    privada = Ed25519PrivateKey.generate()
    publica = privada.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    monkeypatch.setattr(atualizador, 'CHAVES_PUBLICAS', (base64.b64encode(publica).decode(),))
    conteudo = b'{"x": 1}'

    manifesto.conferir_assinatura(conteudo, atualizador.assinar(conteudo, privada))
    with pytest.raises(ErroDoAmbiente, match='biblioteca'):
        manifesto.conferir_assinatura(conteudo + b' ', atualizador.assinar(conteudo, privada))


def test_url_montada_pelo_app():
    artefato = manifesto.ArtefatoEstudo('estudo-1.15.1-1-linux-x86_64.tar.xz', 'a' * 64, 1, 1)

    url = manifesto.url_do_artefato('1.15.1-1', artefato)

    assert url == (
        'https://github.com/LMafra/analise_concursos/releases/download/'
        'estudo-v1.15.1-1/estudo-1.15.1-1-linux-x86_64.tar.xz'
    )
    atualizador.conferir_url(url)
