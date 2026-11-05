import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

from concursos.aplicacao import captura_tec, integracoes, pratica
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import ler_toml, resolver_contexto
from concursos.erros import ErroDoUsuario

ENTRADA = Path(__file__).parent / 'contrato_tec' / 'entrada'


@pytest.fixture
def contexto(tmp_path: Path):
    return resolver_contexto(cwd=tmp_path, data_dir=tmp_path / '.concurso')


def copias(tmp_path: Path, *nomes: str) -> list[Path]:
    destino = tmp_path / 'baixados'
    destino.mkdir(exist_ok=True)
    return [Path(shutil.copy2(ENTRADA / nome, destino / nome)) for nome in nomes]


def test_importar_exportacoes_sem_secao_cria_pratica_e_copia_para_tec(contexto, tmp_path):
    arquivos = copias(tmp_path, 'tec-erros-computador-2026-11-03.json', 'caderno-estado.json')

    copiados = pratica.importar_exportacoes(Opcoes(contexto), arquivos)

    assert ler_toml(contexto.config_projeto)['pratica'] == {'entrada_tec': 'tec'}
    assert copiados == [tmp_path / 'tec' / a.name for a in arquivos]
    assert all(c.is_file() for c in copiados)


def test_importar_exportacoes_usa_a_entrada_configurada(contexto, tmp_path):
    contexto.config_projeto.parent.mkdir(parents=True)
    contexto.config_projeto.write_text('[pratica]\nentrada_tec = "exportacoes"\n', encoding='utf-8')
    arquivos = copias(tmp_path, 'tec-erros-tablet-2026-11-04.json')

    copiados = pratica.importar_exportacoes(Opcoes(contexto), arquivos)

    assert copiados == [tmp_path / 'exportacoes' / 'tec-erros-tablet-2026-11-04.json']


def test_exportacao_invalida_nao_copia_nada_nem_grava_a_secao(contexto, tmp_path):
    arquivos = copias(tmp_path, 'tec-erros-computador-2026-11-03.json')
    invalido = tmp_path / 'baixados' / 'tec-erros-quebrado.json'
    invalido.write_text('{"app": "outro"}', encoding='utf-8')

    with pytest.raises(ErroDoUsuario) as erro:
        pratica.importar_exportacoes(Opcoes(contexto), [*arquivos, invalido])

    assert 'tec-erros-quebrado.json' in erro.value.causa
    assert erro.value.dica
    assert not (tmp_path / 'tec').exists()
    assert not contexto.config_projeto.exists()


def test_espera_cancelavel_para_quando_o_usuario_cancela(tmp_path):
    cancelar = threading.Event()
    esperar = integracoes.espera_cancelavel(cancelar)
    threading.Timer(0.1, cancelar.set).start()
    inicio = time.monotonic()

    with pytest.raises(integracoes.ImportacaoCanceladaError):
        esperar(tmp_path, ['prova.pdf'], 0.0, 30.0)

    assert time.monotonic() - inicio < 5


def test_espera_cancelavel_devolve_o_que_apareceu(tmp_path):
    (tmp_path / 'prova.pdf').write_bytes(b'%PDF-1.4')

    encontrados = integracoes.espera_cancelavel(threading.Event())(tmp_path, ['prova.pdf'], 0.0, 30.0)

    assert encontrados == {'prova.pdf': tmp_path / 'prova.pdf'}


def captura_falsa(pasta: Path) -> Path:
    (pasta / 'extensao-chrome').mkdir(parents=True)
    for nome in ('caderno.html', 'tec-erros.user.js', 'tec-erros-extensao-1.0.0.zip'):
        (pasta / nome).write_text('x', encoding='utf-8')
    return pasta


def test_captura_embutida_no_executavel(tmp_path, monkeypatch):
    captura_falsa(tmp_path / 'tec-erros')
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)

    captura = captura_tec.localizar()

    assert captura is not None
    assert captura.caderno == tmp_path / 'tec-erros' / 'caderno.html'
    assert captura.extensao == tmp_path / 'tec-erros' / 'extensao-chrome'
    assert captura.userscript == tmp_path / 'tec-erros' / 'tec-erros.user.js'
    assert captura.zip_extensao == tmp_path / 'tec-erros' / 'tec-erros-extensao-1.0.0.zip'


def test_sem_captura_gerada_devolve_none(tmp_path):
    assert captura_tec.localizar([tmp_path / 'nada']) is None
