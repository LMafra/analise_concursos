import os
from pathlib import Path

import pytest

from concursos.integracoes import download_assistido
from concursos.integracoes.download_assistido import casa, esperar_downloads, importar, pasta_de_downloads

INICIO = 1_800_000_000.0


class Tempo:
    """Relógio e `dormir` falsos; a cada espera, `acoes` simula o que o navegador faz na pasta."""

    def __init__(self, acoes: list) -> None:
        self.agora = 0.0
        self.acoes = acoes

    def relogio(self) -> float:
        return self.agora

    def dormir(self, segundos: float) -> None:
        self.agora += segundos
        if self.acoes:
            self.acoes.pop(0)()


def gravar(pasta: Path, nome: str, conteudo: bytes = b'%PDF-1.4', mtime: float = INICIO + 10) -> Path:
    caminho = pasta / nome
    caminho.write_bytes(conteudo)
    os.utime(caminho, (mtime, mtime))
    return caminho


@pytest.mark.parametrize(
    ('baixado', 'esperado', 'igual'),
    [
        ('gabaritos.pdf', 'gabaritos.pdf', True),
        ('gabaritos (1).pdf', 'gabaritos.pdf', True),
        ('prova1-auditor-fiscal.pdf', 'prova1_auditor_fiscal.pdf', True),
        ('Gabaritos.PDF', 'gabaritos.pdf', True),
        ('gabaritos.pdf.crdownload', 'gabaritos.pdf', False),
        ('gabaritos2.pdf', 'gabaritos.pdf', False),
    ],
)
def test_casa_o_nome_do_navegador(baixado: str, esperado: str, igual: bool):
    assert casa(baixado, esperado) is igual


def test_espera_o_crdownload_virar_pdf(tmp_path: Path):
    parcial = gravar(tmp_path, 'gabaritos.pdf.crdownload')
    tempo = Tempo(
        [
            lambda: None,
            lambda: parcial.rename(tmp_path / 'gabaritos.pdf'),
            lambda: gravar(tmp_path, 'prova1_auditor_fiscal (1).pdf'),
        ]
    )
    encontrados = esperar_downloads(
        tmp_path,
        ['gabaritos.pdf', 'prova1_auditor_fiscal.pdf'],
        INICIO,
        60,
        relogio=tempo.relogio,
        dormir=tempo.dormir,
    )
    assert {nome: caminho.name for nome, caminho in encontrados.items()} == {
        'gabaritos.pdf': 'gabaritos.pdf',
        'prova1_auditor_fiscal.pdf': 'prova1_auditor_fiscal (1).pdf',
    }
    assert tempo.agora == 6


def test_arquivo_antigo_nao_conta_e_o_timeout_devolve_o_que_achou(tmp_path: Path):
    gravar(tmp_path, 'gabaritos.pdf', mtime=INICIO - 3600)
    gravar(tmp_path, 'prova.pdf')
    tempo = Tempo([])
    encontrados = esperar_downloads(
        tmp_path, ['gabaritos.pdf', 'prova.pdf'], INICIO, 10, relogio=tempo.relogio, dormir=tempo.dormir
    )
    assert list(encontrados) == ['prova.pdf']
    assert tempo.agora >= 10


def test_para_depois_de_um_silencio_sem_arquivo_novo(tmp_path: Path):
    gravar(tmp_path, 'gabaritos.pdf')
    tempo = Tempo([])
    encontrados = esperar_downloads(
        tmp_path,
        ['gabaritos.pdf', 'prova.pdf'],
        INICIO,
        300,
        relogio=tempo.relogio,
        dormir=tempo.dormir,
        silencio=20,
    )
    assert list(encontrados) == ['gabaritos.pdf']
    assert tempo.agora == 20


def test_importar_copia_com_o_nome_da_pagina(tmp_path: Path):
    origem = gravar(tmp_path, 'gabaritos (2).pdf', b'conteudo')
    destino = tmp_path / 'simulado'
    copiados = importar({'gabaritos.pdf': origem}, destino)
    assert copiados == [destino / 'gabaritos.pdf']
    assert (destino / 'gabaritos.pdf').read_bytes() == b'conteudo'
    assert origem.exists()


def test_pasta_configurada_vence(tmp_path: Path):
    assert pasta_de_downloads(str(tmp_path / 'dl')) == tmp_path / 'dl'


def test_no_wsl_usa_a_downloads_do_usuario_do_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(download_assistido.relatorio_html, '_no_wsl', lambda: True)
    for usuario in ('Public', 'maria'):
        (tmp_path / usuario / 'Downloads').mkdir(parents=True)
    assert pasta_de_downloads('', tmp_path) == tmp_path / 'maria' / 'Downloads'
