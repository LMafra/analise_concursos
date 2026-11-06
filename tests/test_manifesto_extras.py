from pathlib import Path

import pytest
from conftest import criar_concurso
from test_cli_comando_unico import ARQUIVOS, config

from concursos import manifesto
from concursos.aplicacao import conferencia
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import resolver_contexto


def test_sem_extras_o_manifesto_e_o_mesmo(tmp_path):
    pasta = tmp_path / 'alfa'
    pasta.mkdir()
    (pasta / 'concurso.yaml').write_text('nome: alfa\n', encoding='utf-8')
    ausente = tmp_path / 'taxonomia.yaml'

    assert manifesto.calcular(pasta, extras={'.concurso/taxonomia.yaml': ausente}) == manifesto.calcular(
        pasta
    )

    ausente.write_text('{}\n', encoding='utf-8')
    com_extra = manifesto.calcular(pasta, extras={'.concurso/taxonomia.yaml': ausente})
    assert '.concurso/taxonomia.yaml' in com_extra['arquivos']


@pytest.fixture
def raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / 'projeto'
    pasta.mkdir()
    monkeypatch.chdir(pasta)
    return pasta


def test_mudar_a_taxonomia_refaz_e_mudar_um_concurso_refaz_so_ele(raiz):
    for nome in ('alfa', 'beta'):
        criar_concurso(raiz / 'provas', nome, config(nome), ARQUIVOS)
    contexto = resolver_contexto(cwd=raiz)

    def reanalisar(concurso=None) -> list[str]:
        saida: list[str] = []
        opcoes = Opcoes(contexto, saida=saida.append)
        assert conferencia.reanalisar_afetados(opcoes, concurso) == 0
        return sorted(
            p.parent.name
            for p in contexto.analises.glob(f'**/{manifesto.ARQUIVO_MANIFESTO}')
            if p.stat().st_mtime_ns > marca
        )

    marca = 0
    assert reanalisar() == ['alfa', 'beta']

    marca = max(p.stat().st_mtime_ns for p in contexto.analises.glob(f'**/{manifesto.ARQUIVO_MANIFESTO}'))
    assert reanalisar() == []

    contexto.taxonomia.parent.mkdir(parents=True, exist_ok=True)
    contexto.taxonomia.write_text('Português:\n  bloco: geral\n', encoding='utf-8')
    assert reanalisar() == ['alfa', 'beta']

    marca = max(p.stat().st_mtime_ns for p in contexto.analises.glob(f'**/{manifesto.ARQUIVO_MANIFESTO}'))
    revisao = raiz / 'provas' / 'alfa' / 'revisao'
    revisao.mkdir(exist_ok=True)
    (revisao / 'nota.txt').write_text('x', encoding='utf-8')
    assert reanalisar() == ['alfa']
