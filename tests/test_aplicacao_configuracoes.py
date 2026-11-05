import sys
from pathlib import Path

import pytest

from concursos.aplicacao import ia
from concursos.config.contexto import resolver_contexto
from concursos.erros import ErroDoUsuario


@pytest.fixture
def contexto(tmp_path: Path):
    return resolver_contexto(cwd=tmp_path, data_dir=tmp_path / '.concurso')


@pytest.fixture
def sem_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, 'keyring', None)


def test_ia_comeca_desligada(contexto):
    estado = ia.estado_da_ia(contexto)

    assert estado.ligada is False
    assert estado.provedor is None


def test_ligar_grava_o_consentimento_e_a_chave_nunca_vai_para_o_toml(contexto, sem_keyring, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)

    onde = ia.ligar_ia(contexto, 'openai', 'sk-segredo-de-teste')

    texto = contexto.config_global.read_text(encoding='utf-8')
    assert 'sk-segredo-de-teste' not in texto
    assert 'consentimento = true' in texto
    assert onde == str(contexto.home / '.env')
    estado = ia.estado_da_ia(contexto)
    assert estado.ligada is True
    assert estado.provedor == 'openai'
    assert estado.chave_em == str(contexto.home / '.env')


def test_ligar_sem_chave_avisa_onde_por_a_chave(contexto, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr('concursos.llm._do_keyring', lambda variavel: None)

    ia.ligar_ia(contexto, 'openai', None)

    estado = ia.estado_da_ia(contexto)
    assert estado.ligada is True
    assert estado.chave_em is None
    assert estado.variavel_chave == 'OPENAI_API_KEY'


def test_provedor_local_nao_pede_chave(contexto):
    ia.ligar_ia(contexto, 'ollama', None)

    assert ia.estado_da_ia(contexto).variavel_chave is None


def test_desligar_volta_ao_nenhum(contexto):
    ia.ligar_ia(contexto, 'ollama', None)

    ia.desligar_ia(contexto)

    assert ia.estado_da_ia(contexto).ligada is False


def test_provedor_desconhecido_e_erro_do_usuario(contexto):
    with pytest.raises(ErroDoUsuario):
        ia.ligar_ia(contexto, 'qualquer', None)


def test_aviso_diz_que_so_o_edital_sai_do_computador():
    assert 'edital' in ia.aviso('openai')
    assert 'respostas' in ia.aviso('openai')
