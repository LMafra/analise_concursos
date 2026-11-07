import hashlib
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from concursos import atualizador
from concursos.aplicacao import atualizador as aplicacao
from concursos.erros import ErroDoAmbiente, ErroDoUsuario
from concursos.modelo import CanalAtualizacao

CHAVE = Ed25519PrivateKey.generate()
AGORA = datetime(2026, 12, 1, 12, tzinfo=UTC)
SETUP = b'setup novo'
APPIMAGE = b'appimage novo'


@pytest.fixture(autouse=True)
def chave_de_teste(monkeypatch):
    import base64

    publica = base64.b64encode(CHAVE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    monkeypatch.setattr(atualizador, 'CHAVES_PUBLICAS', (publica,))


def manifesto(versao: str = '0.6.0', canal: str = 'stable') -> bytes:
    return json.dumps(
        {
            'formato': 1,
            'versao': versao,
            'canal': canal,
            'publicado_em': '2026-12-01',
            'notas': f'https://github.com/LMafra/analise_concursos/releases/tag/v{versao}',
            'artefatos': {
                'windows-x64': {
                    'arquivo': f'concurso-analise-{versao}-windows-x64-setup.exe',
                    'sha256': hashlib.sha256(SETUP).hexdigest(),
                    'tamanho': len(SETUP),
                },
                'linux-x86_64': {
                    'arquivo': f'concurso-analise-{versao}-linux-x86_64.AppImage',
                    'sha256': hashlib.sha256(APPIMAGE).hexdigest(),
                    'tamanho': len(APPIMAGE),
                },
            },
        }
    ).encode()


class TransporteFalso:
    def __init__(self, respostas: dict[str, bytes]) -> None:
        self.respostas = respostas
        self.pedidos: list[str] = []

    def baixar(self, url: str, limite: int) -> bytes:
        self.pedidos.append(url)
        if url not in self.respostas:
            raise ErroDoAmbiente(f'404 em {url}')
        return self.respostas[url][:limite]

    def baixar_para(self, url: str, destino: Path, limite: int, progresso=None) -> None:
        destino.write_bytes(self.baixar(url, limite))


def stable(
    conteudo: bytes | None = None, assinatura: bytes | None = None, **artefatos: bytes
) -> TransporteFalso:
    conteudo = conteudo or manifesto()
    return TransporteFalso(
        {
            atualizador.URL_STABLE: conteudo,
            f'{atualizador.URL_STABLE}.sig': assinatura or atualizador.assinar(conteudo, CHAVE),
            f'{atualizador.URL_DOWNLOAD}/v0.6.0/concurso-analise-0.6.0-windows-x64-setup.exe': artefatos.get(
                'setup', SETUP
            ),
            f'{atualizador.URL_DOWNLOAD}/v0.6.0/concurso-analise-0.6.0-linux-x86_64.AppImage': artefatos.get(
                'appimage', APPIMAGE
            ),
        }
    )


def test_stable_oferece_a_versao_nova_com_a_url_da_release():
    novidade = aplicacao.verificar(
        CanalAtualizacao.STABLE, transporte=stable(), instalada='0.5.0', sistema='linux'
    )

    assert novidade.versao == '0.6.0'
    assert novidade.url.endswith('/v0.6.0/concurso-analise-0.6.0-linux-x86_64.AppImage')


def test_stable_na_mesma_versao_nao_oferece():
    assert (
        aplicacao.verificar(CanalAtualizacao.STABLE, transporte=stable(), instalada='0.6.0', sistema='win32')
        is None
    )


def test_manifesto_com_assinatura_errada_e_erro_e_nada_e_baixado():
    outra = Ed25519PrivateKey.generate()
    transporte = stable(assinatura=atualizador.assinar(manifesto(), outra))

    with pytest.raises(ErroDoAmbiente, match='assinatura'):
        aplicacao.verificar(
            CanalAtualizacao.STABLE, transporte=transporte, instalada='0.5.0', sistema='linux'
        )
    assert all('download/v' not in url for url in transporte.pedidos)


def test_beta_usa_a_primeira_release_publicada_com_manifesto():
    beta = manifesto('0.7.0b1', 'beta')
    releases = [
        {
            'draft': True,
            'assets': [{'name': 'atualizacao.json', 'browser_download_url': 'https://github.com/x'}],
        },
        {'draft': False, 'assets': []},
        {
            'draft': False,
            'assets': [
                {'name': 'atualizacao.json', 'browser_download_url': 'https://github.com/b/atualizacao.json'},
                {
                    'name': 'atualizacao.json.sig',
                    'browser_download_url': 'https://github.com/b/atualizacao.json.sig',
                },
            ],
        },
    ]
    transporte = TransporteFalso(
        {
            atualizador.URL_RELEASES: json.dumps(releases).encode(),
            'https://github.com/b/atualizacao.json': beta,
            'https://github.com/b/atualizacao.json.sig': atualizador.assinar(beta, CHAVE),
        }
    )

    novidade = aplicacao.verificar(
        CanalAtualizacao.BETA, transporte=transporte, instalada='0.6.0', sistema='linux'
    )

    assert novidade.versao == '0.7.0b1'
    assert novidade.canal is CanalAtualizacao.BETA
    assert 'https://github.com/x' not in transporte.pedidos


def test_linux_troca_o_appimage_no_mesmo_caminho(tmp_path):
    atual = tmp_path / 'concurso-analise.AppImage'
    atual.write_bytes(b'antigo')
    transporte = stable()
    novidade = aplicacao.verificar(
        CanalAtualizacao.STABLE, transporte=transporte, instalada='0.5.0', sistema='linux'
    )

    instalacao = aplicacao.instalar(
        novidade, transporte=transporte, sistema='linux', ambiente={'APPIMAGE': str(atual)}
    )

    assert instalacao.caminho == atual
    assert not instalacao.setup_em_andamento
    assert atual.read_bytes() == APPIMAGE
    assert os.name == 'nt' or os.stat(atual).st_mode & 0o777 == 0o755
    assert sorted(p.name for p in tmp_path.iterdir()) == ['concurso-analise.AppImage']


def test_linux_com_sha256_errado_mantem_o_appimage_antigo(tmp_path):
    atual = tmp_path / 'concurso-analise.AppImage'
    atual.write_bytes(b'antigo')
    transporte = stable(appimage=b'adulterado!!!')
    novidade = aplicacao.verificar(
        CanalAtualizacao.STABLE, transporte=transporte, instalada='0.5.0', sistema='linux'
    )

    with pytest.raises(ErroDoAmbiente, match='diferente do publicado'):
        aplicacao.instalar(
            novidade, transporte=transporte, sistema='linux', ambiente={'APPIMAGE': str(atual)}
        )

    assert atual.read_bytes() == b'antigo'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['concurso-analise.AppImage']


def test_linux_nao_segue_link_plantado_na_pasta_do_appimage(tmp_path):
    atual = tmp_path / 'concurso-analise.AppImage'
    atual.write_bytes(b'antigo')
    alvo = tmp_path / 'alvo.txt'
    alvo.write_bytes(b'intacto')
    (tmp_path / '.concurso-analise.AppImage.atualizacao').symlink_to(alvo)
    transporte = stable()
    novidade = aplicacao.verificar(
        CanalAtualizacao.STABLE, transporte=transporte, instalada='0.5.0', sistema='linux'
    )

    aplicacao.instalar(novidade, transporte=transporte, sistema='linux', ambiente={'APPIMAGE': str(atual)})

    assert alvo.read_bytes() == b'intacto'
    assert atual.read_bytes() == APPIMAGE


def test_linux_fora_do_appimage_pede_o_download_manual():
    novidade = aplicacao.verificar(
        CanalAtualizacao.STABLE, transporte=stable(), instalada='0.5.0', sistema='linux'
    )

    with pytest.raises(ErroDoUsuario, match='AppImage') as erro:
        aplicacao.instalar(novidade, transporte=stable(), sistema='linux', ambiente={})
    assert 'releases' in erro.value.dica


def test_linux_sem_permissao_na_pasta_pede_outra_pasta(tmp_path, monkeypatch):
    atual = tmp_path / 'concurso-analise.AppImage'
    atual.write_bytes(b'antigo')
    monkeypatch.setattr(aplicacao.os, 'access', lambda caminho, modo: False)
    novidade = aplicacao.verificar(
        CanalAtualizacao.STABLE, transporte=stable(), instalada='0.5.0', sistema='linux'
    )

    with pytest.raises(ErroDoUsuario, match='permissão'):
        aplicacao.instalar(novidade, transporte=stable(), sistema='linux', ambiente={'APPIMAGE': str(atual)})
    assert atual.read_bytes() == b'antigo'


def assinaturas(**por_nome: tuple[str, str | None]):
    def ler(caminho: Path) -> tuple[str, str | None]:
        return por_nome.get(
            caminho.suffix.lstrip('.') if caminho.name != 'atual.exe' else 'atual', ('NotSigned', None)
        )

    return ler


def instalar_no_windows(tmp_path, ler_assinatura, **artefatos):
    abertos: list[list[str]] = []
    transporte = stable(**artefatos)
    novidade = aplicacao.verificar(
        CanalAtualizacao.STABLE, transporte=transporte, instalada='0.5.0', sistema='win32'
    )
    instalacao = aplicacao.instalar(
        novidade,
        transporte=transporte,
        sistema='win32',
        executavel=tmp_path / 'atual.exe',
        ler_assinatura=ler_assinatura,
        abrir=abertos.append,
        pasta_temporaria=tmp_path,
    )
    return instalacao, abertos


def test_windows_assinado_roda_o_setup_do_mesmo_signatario(tmp_path):
    titular = 'CN=SignPath Foundation, O=SignPath Foundation'
    ler = assinaturas(atual=('Valid', titular), exe=('Valid', titular))

    instalacao, abertos = instalar_no_windows(tmp_path, ler)

    assert instalacao.setup_em_andamento
    assert abertos == [
        atualizador.comando_do_setup(tmp_path / 'concurso-analise-0.6.0-windows-x64-setup.exe')
    ]


@pytest.mark.parametrize(
    'setup', [('Valid', 'CN=Outro'), ('NotSigned', None), ('HashMismatch', 'CN=SignPath')]
)
def test_windows_assinado_recusa_setup_de_outro_ou_sem_assinatura(tmp_path, setup):
    ler = assinaturas(atual=('Valid', 'CN=SignPath'), exe=setup)

    with pytest.raises(ErroDoAmbiente, match='não é o oficial') as erro:
        instalar_no_windows(tmp_path, ler)
    assert 'assinatura' in erro.value.detalhe
    assert not (tmp_path / 'concurso-analise-0.6.0-windows-x64-setup.exe').exists()


def test_windows_sem_assinatura_no_atual_confia_no_manifesto_e_no_sha256(tmp_path):
    _, abertos = instalar_no_windows(tmp_path, assinaturas())

    assert len(abertos) == 1


def test_windows_com_sha256_errado_nao_roda_nada(tmp_path):
    with pytest.raises(ErroDoAmbiente, match='diferente do publicado'):
        instalar_no_windows(tmp_path, assinaturas(), setup=b'outro setup')
    assert list(tmp_path.iterdir()) == []


def test_preferencias_padrao_e_gravadas(tmp_path):
    config = tmp_path / 'config.toml'
    assert aplicacao.ler_preferencias(config) == aplicacao.Preferencias(CanalAtualizacao.STABLE, False)

    aplicacao.gravar_preferencias(config, aplicacao.Preferencias(CanalAtualizacao.BETA, True))

    assert aplicacao.ler_preferencias(config) == aplicacao.Preferencias(CanalAtualizacao.BETA, True)


def test_ao_abrir_desligado_nao_consulta(tmp_path):
    transporte = stable()

    assert (
        aplicacao.verificar_ao_abrir(
            tmp_path / 'config.toml',
            tmp_path / 'estado.json',
            agora=AGORA,
            transporte=transporte,
            sistema='linux',
        )
        is None
    )
    assert transporte.pedidos == []


def test_ao_abrir_consulta_uma_vez_por_dia(tmp_path):
    config = tmp_path / 'config.toml'
    aplicacao.gravar_preferencias(config, aplicacao.Preferencias(verificar_ao_abrir=True))
    estado = tmp_path / 'estado.json'
    transporte = stable()

    primeira = aplicacao.verificar_ao_abrir(
        config, estado, agora=AGORA, transporte=transporte, instalada='0.5.0', sistema='linux'
    )
    segunda = aplicacao.verificar_ao_abrir(
        config,
        estado,
        agora=AGORA + timedelta(hours=1),
        transporte=transporte,
        instalada='0.5.0',
        sistema='linux',
    )

    assert primeira.versao == '0.6.0'
    assert segunda is None
    assert len(transporte.pedidos) == 2


def test_ao_abrir_falha_so_no_log(tmp_path, caplog):
    config = tmp_path / 'config.toml'
    aplicacao.gravar_preferencias(config, aplicacao.Preferencias(verificar_ao_abrir=True))

    with caplog.at_level(logging.INFO, logger='concursos.aplicacao.atualizador'):
        resultado = aplicacao.verificar_ao_abrir(
            config, tmp_path / 'estado.json', agora=AGORA, transporte=TransporteFalso({}), sistema='linux'
        )

    assert resultado is None
    assert 'falhou' in caplog.text


def test_reabrir_abre_o_appimage_novo_sem_as_variaveis_do_antigo(tmp_path, monkeypatch):
    monkeypatch.setenv('APPIMAGE', '/velho')
    chamadas = []
    instalacao = aplicacao.Instalacao('0.6.0', tmp_path / 'novo.AppImage', setup_em_andamento=False)

    aplicacao.reabrir(instalacao, abrir=lambda comando, **kwargs: chamadas.append((comando, kwargs)))

    comando, kwargs = chamadas[0]
    assert comando == [str(tmp_path / 'novo.AppImage')]
    assert 'APPIMAGE' not in kwargs['env']


def test_transporte_recusa_redirecionamento_para_fora_do_github():
    import urllib.request

    pedido = urllib.request.Request('https://github.com/LMafra/analise_concursos/releases/latest/download/x')

    with pytest.raises(ErroDoAmbiente, match='fora do GitHub'):
        aplicacao._SoGithub().redirect_request(pedido, None, 302, 'Found', {}, 'https://evil.example.com/x')


def test_transporte_recusa_url_sem_https_antes_de_abrir():
    with pytest.raises(ErroDoAmbiente, match='fora do GitHub'):
        aplicacao.TransporteHttps('0.5.0').baixar('http://github.com/x', 10)


def test_transporte_corta_resposta_maior_que_o_limite(monkeypatch, tmp_path):
    import io

    transporte = aplicacao.TransporteHttps('0.5.0')
    monkeypatch.setattr(transporte, '_abrir', lambda url: io.BytesIO(b'x' * 100))

    with pytest.raises(ErroDoAmbiente, match='grande demais'):
        transporte.baixar('https://github.com/x', 10)
    with pytest.raises(ErroDoAmbiente, match='maior que o esperado'):
        transporte.baixar_para('https://github.com/x', tmp_path / 'x', 10)
    assert transporte.baixar('https://github.com/x', 100) == b'x' * 100


def test_gravar_aviso_liga_so_o_aviso_e_mantem_o_canal(tmp_path):
    config_global = tmp_path / 'config.toml'
    aplicacao.gravar_preferencias(config_global, aplicacao.Preferencias(CanalAtualizacao.BETA, False))

    aplicacao.gravar_aviso(config_global, True)

    assert aplicacao.ler_preferencias(config_global) == aplicacao.Preferencias(CanalAtualizacao.BETA, True)
