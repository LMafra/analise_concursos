from pathlib import Path

import pytest

from concursos import exemplo
from concursos.aplicacao import analise
from concursos.aplicacao import exemplo as aplicacao_exemplo
from concursos.status import Situacao, avaliar


def test_criar_exemplo_grava_um_concurso_completo_da_candidata_ficticia(tmp_path):
    pasta = exemplo.criar_exemplo(tmp_path)

    assert pasta == tmp_path / 'provas' / exemplo.CONCURSO
    assert (pasta / 'candidatos' / exemplo.CANDIDATO / 'respostas.txt').is_file()
    assert avaliar(pasta, exemplo.CANDIDATO).situacao is Situacao.COMPLETO


@pytest.fixture
def projeto_do_usuario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / 'meus concursos'
    (pasta / 'provas').mkdir(parents=True)
    monkeypatch.chdir(pasta)
    return pasta


def test_analisar_exemplo_gera_o_relatorio_fora_do_projeto_do_usuario(tmp_path, projeto_do_usuario):
    home = tmp_path / 'home'

    indice = aplicacao_exemplo.analisar_exemplo(home)

    assert indice == home / 'exemplo' / 'analises' / exemplo.CANDIDATO / 'index.html'
    assert indice.is_file()
    assert not (projeto_do_usuario / 'analises').exists()
    assert not (projeto_do_usuario / '.concurso').exists()


def test_analisar_exemplo_recria_a_pasta_a_cada_uso(tmp_path, projeto_do_usuario):
    home = tmp_path / 'home'
    aplicacao_exemplo.analisar_exemplo(home)
    sobra = home / 'exemplo' / 'provas' / 'outro'
    sobra.mkdir()

    aplicacao_exemplo.analisar_exemplo(home)

    assert not sobra.exists()


def test_analisar_exemplo_sem_rede_sem_ia_e_sem_abrir_o_navegador(tmp_path, projeto_do_usuario, monkeypatch):
    recebidas = []

    def analisar_falso(opcoes, *argumentos, **nomeados):
        recebidas.append(opcoes)
        return 0

    monkeypatch.setattr(analise, 'analisar', analisar_falso)

    aplicacao_exemplo.analisar_exemplo(tmp_path / 'home')

    opcoes = recebidas[0]
    assert (opcoes.rede, opcoes.llm, opcoes.abrir, opcoes.interacao) == (False, False, False, None)
    assert opcoes.contexto.candidato == exemplo.CANDIDATO
    assert opcoes.contexto.provas == tmp_path / 'home' / 'exemplo' / 'provas'
