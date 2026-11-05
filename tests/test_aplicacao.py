import ast
import tomllib
from pathlib import Path

import pytest
from conftest import criar_concurso
from test_cli_comando_unico import ARQUIVOS, config

from concursos.aplicacao import analise, projeto
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.preferencias import (
    PreferenciasAnalise,
    gravar_analise,
    lembrar_projeto,
    ler_analise,
    ultimo_projeto,
)
from concursos.candidatos import adicionar_arquivo
from concursos.config.contexto import resolver_contexto
from concursos.erros import ErroDoUsuario

PACOTE = Path(__file__).resolve().parents[1] / 'src' / 'concursos'


@pytest.fixture
def raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / 'projeto'
    pasta.mkdir()
    monkeypatch.chdir(pasta)
    return pasta


def test_analisar_avisa_o_progresso_antes_de_cada_concurso_em_ordem(raiz):
    for nome in ('alfa', 'beta'):
        criar_concurso(raiz / 'provas', nome, config(nome), ARQUIVOS)
    avisos: list[tuple[str, int, int]] = []
    saida: list[str] = []
    opcoes = Opcoes(
        resolver_contexto(cwd=raiz),
        sim=True,
        abrir=False,
        saida=saida.append,
        ao_progresso=lambda concurso, indice, total: avisos.append((concurso, indice, total)),
    )

    assert analise.analisar(opcoes) == 0

    assert avisos == [('alfa', 1, 2), ('beta', 2, 2)]
    assert any(linha.startswith('relatório: ') for linha in saida)


def test_analisar_sem_ao_progresso_funciona_como_antes(raiz):
    criar_concurso(raiz / 'provas', 'alfa', config('alfa'), ARQUIVOS)

    assert analise.analisar(Opcoes(resolver_contexto(cwd=raiz), sim=True, abrir=False)) == 0


def test_escolher_candidato_recusa_quando_ha_mais_de_um_e_nenhum_foi_escolhido(raiz, tmp_path):
    pasta = criar_concurso(raiz / 'provas', 'alfa', config('alfa'), ARQUIVOS)
    respostas = tmp_path / 'respostas.txt'
    respostas.write_text('1 A\n2 B\n', encoding='utf-8')
    for nome in ('Ana Teste', 'Bruno Teste'):
        adicionar_arquivo(pasta, respostas, nome)
    contexto = resolver_contexto(cwd=raiz)

    with pytest.raises(ErroDoUsuario, match='mais de um candidato'):
        projeto.escolher_candidato(contexto)
    assert projeto.escolher_candidato(resolver_contexto(cwd=raiz, candidato='ana_teste')) == 'ana_teste'


def test_preferencias_gravam_analise_e_preservam_o_resto_do_config(raiz):
    contexto = resolver_contexto(cwd=raiz)
    contexto.config_projeto.parent.mkdir(parents=True)
    contexto.config_projeto.write_text(
        '[analise]\nincluir_simulados = false\n\n[candidato]\nultimo = "ana_teste"\n', encoding='utf-8'
    )

    gravar_analise(contexto, PreferenciasAnalise(0.8, 0.5, 'alfa'))

    dados = tomllib.loads(contexto.config_projeto.read_text(encoding='utf-8'))
    assert dados['candidato'] == {'ultimo': 'ana_teste'}
    assert dados['analise']['incluir_simulados'] is False
    assert ler_analise(contexto) == PreferenciasAnalise(0.8, 0.5, 'alfa')

    gravar_analise(contexto, PreferenciasAnalise(0.8, 0.5, None))
    assert (
        'concurso_alvo' not in tomllib.loads(contexto.config_projeto.read_text(encoding='utf-8'))['analise']
    )


def test_preferencias_recusam_limiar_fora_de_0_a_1_sem_gravar(raiz):
    contexto = resolver_contexto(cwd=raiz)

    with pytest.raises(ErroDoUsuario):
        gravar_analise(contexto, PreferenciasAnalise(1.5, 0.5, None))
    assert not contexto.config_projeto.exists()


def test_ultimo_projeto_fica_na_secao_gui_da_configuracao_global(raiz, home_isolada):
    config_global = home_isolada / 'config.toml'
    assert ultimo_projeto(config_global) is None

    lembrar_projeto(config_global, raiz)

    assert ultimo_projeto(config_global) == raiz
    assert tomllib.loads(config_global.read_text(encoding='utf-8'))['gui'] == {
        'ultimo_projeto': raiz.as_posix()
    }


@pytest.mark.parametrize('pasta', ['aplicacao', 'gui'])
def test_aplicacao_e_gui_nao_dependem_da_cli_nem_do_terminal(pasta):
    for arquivo in sorted((PACOTE / pasta).rglob('*.py')):
        arvore = ast.parse(arquivo.read_text(encoding='utf-8'))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                modulos = [alias.name for alias in no.names]
            elif isinstance(no, ast.ImportFrom):
                modulos = [no.module or '']
            else:
                modulos = []
            for modulo in modulos:
                assert not modulo.startswith(('typer', 'concursos.cli')), f'{arquivo.name} importa {modulo}'
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
                assert no.func.id not in {'print', 'input'}, f'{arquivo.name} chama {no.func.id}'
