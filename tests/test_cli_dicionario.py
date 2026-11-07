from pathlib import Path

import pandas as pd
import pytest
import yaml
from conftest import ler_csv
from test_cli_topicos import criar

from concursos.cli import main
from concursos.config.contexto import resolver_contexto
from concursos.migracao import candidato_padrao
from concursos.pipeline import COLUNAS_DICIONARIO

DICIONARIO = {
    'versao': 1,
    'banco_de_dados': {'nosql': {'termos': ['mongodb', 'documentos']}},
}


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    raiz.mkdir()
    monkeypatch.chdir(raiz)
    criar(raiz / 'provas')
    return raiz


def _questoes(projeto: Path) -> pd.DataFrame:
    return ler_csv(projeto / 'analises' / candidato_padrao() / 'sintetico' / 'questoes.csv')


def _mtimes(projeto: Path) -> dict[Path, int]:
    return {p: p.stat().st_mtime_ns for p in (projeto / 'analises').rglob('*') if p.is_file()}


def _gravar_dicionario(projeto: Path, dados: dict = DICIONARIO) -> None:
    caminho = projeto / '.concurso' / 'taxonomia_topicos.yaml'
    caminho.parent.mkdir(exist_ok=True)
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding='utf-8')


def test_sem_dicionario_nao_ha_colunas_novas(projeto):
    assert main(['--yes']) == 0
    assert not set(COLUNAS_DICIONARIO) & set(_questoes(projeto).columns)


def test_dicionario_reprocessa_acrescenta_colunas_e_fica_estavel(projeto):
    assert main(['--yes']) == 0
    _gravar_dicionario(projeto)

    assert main(['--yes']) == 0
    questoes = _questoes(projeto)
    assert set(COLUNAS_DICIONARIO) <= set(questoes.columns)
    nosql = questoes.set_index('questao').loc[1]
    assert nosql['topico_sugerido'] == 'Bancos de dados NoSQL'
    assert nosql['score_expandido'] == nosql['score']
    assert nosql['topico_tfidf'] == 'Bancos de dados NoSQL'
    assert nosql['score_tfidf'] != nosql['score']

    antes = _mtimes(projeto)
    assert main(['--yes']) == 0
    assert _mtimes(projeto) == antes


def test_desligar_o_dicionario_volta_a_saida_sem_ele(projeto):
    assert main(['--yes']) == 0
    sem = _questoes(projeto)
    _gravar_dicionario(projeto)
    assert main(['--yes']) == 0
    config = projeto / '.concurso' / 'config.toml'
    config.write_text(config.read_text(encoding='utf-8') + '\n[dicionario]\nusar = false\n', encoding='utf-8')

    assert main(['--yes']) == 0
    pd.testing.assert_frame_equal(_questoes(projeto), sem)


def test_dicionario_invalido_vira_erro_do_usuario(projeto, capsys):
    _gravar_dicionario(projeto, {'banco_de_dados': {'nosql': {'sinonimos': ['x']}}})
    assert main(['--yes']) == 1
    erro = capsys.readouterr().err
    assert 'sinonimos' in erro
    assert 'Traceback' not in erro


def test_iniciar_grava_o_inicial_e_liga(projeto):
    assert main(['dicionario', 'iniciar']) == 0
    contexto = resolver_contexto()
    assert contexto.dicionario.exists()
    assert contexto.dicionario_ligado
    dados = yaml.safe_load(contexto.dicionario.read_text(encoding='utf-8'))
    assert 'lingua_portuguesa' in dados

    antes = contexto.dicionario.read_bytes()
    assert main(['dicionario', 'iniciar']) == 0
    assert contexto.dicionario.read_bytes() == antes


def _revisar(projeto: Path) -> None:
    caminho = projeto / 'provas' / 'sintetico' / 'revisao' / 'questoes_revisado.csv'
    revisao = pd.read_csv(caminho, keep_default_na=False)
    revisao['topico'] = revisao['topico_sugerido']
    revisao.to_csv(caminho, index=False)


def test_avaliar_grava_o_relatorio_e_o_resumo(projeto, capsys):
    assert main(['--yes']) == 0
    _revisar(projeto)
    _gravar_dicionario(projeto)

    assert main(['dicionario', 'avaliar']) == 0
    assert 'acerto:' in capsys.readouterr().out
    assert (projeto / '.concurso' / 'ganho_dicionario.md').exists()
    config = (projeto / '.concurso' / 'config.toml').read_text(encoding='utf-8')
    assert '[dicionario]' in config and 'n = 3' in config


def test_avaliar_sem_dicionario_explica(projeto, capsys):
    assert main(['dicionario', 'avaliar']) == 1
    assert 'dica:' in capsys.readouterr().err


def test_sugerir_sem_revisoes_explica(projeto, capsys):
    assert main(['--yes']) == 0
    assert main(['dicionario', 'sugerir']) == 0
    assert 'nenhuma sugestão' in capsys.readouterr().out
    assert main(['dicionario', 'sugerir', '--aceitar', 'x/y/z']) == 1
