import io
import tarfile
from pathlib import Path

import pytest

from concursos.aplicacao import estudo
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import Contexto
from concursos.erros import ErroDoUsuario


@pytest.fixture
def contexto(tmp_path) -> Contexto:
    return Contexto(
        raiz=tmp_path,
        home=tmp_path / 'home',
        projeto=tmp_path / '.concurso',
        provas=tmp_path / 'provas',
        analises=tmp_path / 'analises',
    )


def pacote(tmp_path: Path, versao='1.15.1-1') -> Path:
    arquivo = tmp_path / f'estudo-{versao}-linux-x86_64.tar.xz'
    with tarfile.open(arquivo, 'w:xz') as tar:
        info = tarfile.TarInfo(f'estudo-{versao}/estudo.toml')
        info.size = 0
        tar.addfile(info, io.BytesIO(b''))
    return arquivo


def test_antes_de_preparar_explica_o_download(contexto):
    situacao = estudo.situacao_do_estudo(contexto, 'linux')

    assert not situacao.preparado
    assert 'open-notebook' in situacao.mensagem and 'não saem do computador' in situacao.mensagem


def test_macos_diz_que_ainda_nao_esta_disponivel(contexto):
    situacao = estudo.situacao_do_estudo(contexto, 'darwin')

    assert not situacao.disponivel_no_sistema
    assert 'ainda não está disponível' in situacao.mensagem


def test_preparar_de_um_arquivo_local(contexto, tmp_path):
    versao = estudo.preparar_estudo(Opcoes(contexto), consentiu=False, arquivo=pacote(tmp_path))

    assert versao == '1.15.1-1'
    assert estudo.situacao_do_estudo(contexto, 'linux').versao == '1.15.1-1'


def test_baixar_exige_consentimento_e_rede(contexto):
    with pytest.raises(ErroDoUsuario, match='concordar'):
        estudo.preparar_estudo(Opcoes(contexto), consentiu=False)
    with pytest.raises(ErroDoUsuario, match='sem internet'):
        estudo.preparar_estudo(Opcoes(contexto, rede=False), consentiu=True)


def test_dry_run_nao_grava(contexto, tmp_path):
    estudo.preparar_estudo(Opcoes(contexto, dry_run=True), consentiu=True, arquivo=pacote(tmp_path))

    assert not estudo.pastas(contexto).base.exists()


def test_chave_de_cifra_gerada_uma_vez(contexto, monkeypatch):
    guardadas = {}
    monkeypatch.setattr(
        estudo, 'obter_chave_da_variavel', lambda v, h: (guardadas[v], 'x') if v in guardadas else None
    )
    monkeypatch.setattr(estudo, 'guardar_chave', lambda v, c, h: guardadas.__setitem__(v, c))

    primeira = estudo.chave_de_cifra(contexto.home)

    assert estudo.chave_de_cifra(contexto.home) == primeira
    assert len(primeira) >= 32
