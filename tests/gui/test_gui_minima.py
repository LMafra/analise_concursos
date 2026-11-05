import asyncio
import shutil
import tomllib
from pathlib import Path

import pytest
from concurso_sintetico import ARQUIVOS_SIMPLES, config_simples, criar_concurso
from nicegui.testing.user import User

from concursos.aplicacao import analise
from concursos.aplicacao.opcoes import Opcoes
from concursos.cli import main
from concursos.erros import ErroDoUsuario
from concursos.gui import app as gui_app
from concursos.gui.estado import ESTADO


async def esperar(condicao, segundos: float = 3.0) -> None:
    for _ in range(int(segundos / 0.05)):
        if condicao():
            return
        await asyncio.sleep(0.05)
    raise AssertionError('condição não atingida a tempo')


@pytest.mark.parametrize(('plataforma', 'nativa'), [('linux', False), ('win32', True), ('darwin', True)])
def test_executar_so_escuta_no_proprio_computador(monkeypatch, tmp_path, plataforma, nativa):
    chamadas: list[dict] = []
    monkeypatch.setattr(gui_app.ui, 'run', lambda raiz, **kwargs: chamadas.append(kwargs))
    monkeypatch.setattr(gui_app.sys, 'platform', plataforma)

    gui_app.executar(tmp_path / 'projeto')

    assert chamadas[0]['host'] == '127.0.0.1'
    assert chamadas[0]['reload'] is False
    assert chamadas[0]['native'] is nativa
    assert ESTADO.projeto == (tmp_path / 'projeto').resolve()


def test_browser_forca_o_navegador_mesmo_fora_do_linux(monkeypatch, tmp_path):
    chamadas: list[dict] = []
    monkeypatch.setattr(gui_app.ui, 'run', lambda raiz, **kwargs: chamadas.append(kwargs))
    monkeypatch.setattr(gui_app.sys, 'platform', 'win32')

    gui_app.executar(tmp_path, navegador=True)

    assert chamadas[0]['native'] is False
    assert 'window_size' not in chamadas[0]


async def test_sem_projeto_pede_a_pasta_e_lembra_dela(user: User, tmp_path, home_isolada):
    await user.open('/')
    await user.should_see('Pasta do projeto')

    destino = tmp_path / 'Concursos ação'
    user.find(marker='campo-pasta').clear().type(str(destino))
    user.find(marker='usar-projeto').click()

    await esperar(lambda: ESTADO.projeto == destino.resolve())
    assert Path.cwd() == destino.resolve()
    config = tomllib.loads((home_isolada / 'config.toml').read_text(encoding='utf-8'))
    assert config['gui']['ultimo_projeto'] == destino.resolve().as_posix()


async def test_concursos_mostra_situacao_gabarito_e_motivos(user: User, projeto):
    criar_concurso(projeto / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)
    (projeto / 'provas' / 'beta').mkdir()

    await user.open('/')

    await user.should_see('alfa')
    await user.should_see('completo')
    await user.should_see('beta')
    await user.should_see('incompleto')
    await user.should_see('Resolver')


async def test_projeto_vazio_explica_o_que_fazer(user: User, projeto):
    await user.open('/')
    await user.should_see(marker='sem-concursos')


async def test_analisar_avanca_a_barra_por_concurso_e_preenche_o_log(user: User, projeto, monkeypatch):
    recebidas: list[Opcoes] = []

    def analisar_falso(opcoes: Opcoes) -> int:
        recebidas.append(opcoes)
        opcoes.ao_progresso('alfa', 1, 2)
        opcoes.saida('linha do relatório de teste')
        opcoes.ao_progresso('beta', 2, 2)
        return 0

    monkeypatch.setattr(analise, 'analisar', analisar_falso)

    await user.open('/analise')
    user.find(marker='iniciar').click()

    await user.should_see('Análise concluída.', retries=60)
    await user.should_see('linha do relatório de teste')
    assert recebidas[0].abrir is False
    assert recebidas[0].contexto.raiz == projeto.resolve()
    assert recebidas[0].ao_progresso is not None


async def test_analisar_mostra_erro_e_dica_como_a_cli(user: User, projeto, monkeypatch):
    def analisar_falso(opcoes: Opcoes) -> int:
        raise ErroDoUsuario('pasta de provas não encontrada', 'crie uma subpasta por concurso')

    monkeypatch.setattr(analise, 'analisar', analisar_falso)

    await user.open('/analise')
    user.find(marker='iniciar').click()

    await user.should_see('erro: pasta de provas não encontrada', retries=60)
    await user.should_see('dica: crie uma subpasta por concurso')


async def test_botao_analisar_da_lista_ja_inicia_a_analise(user: User, projeto, monkeypatch):
    chamadas: list[Opcoes] = []
    monkeypatch.setattr(analise, 'analisar', lambda opcoes: chamadas.append(opcoes) or 0)

    await user.open('/')
    user.find(marker='analisar').click()

    await user.should_see('Análise concluída.', retries=60)
    assert len(chamadas) == 1


def retrato(raiz: Path) -> dict[str, bytes]:
    return {
        caminho.relative_to(raiz).as_posix(): caminho.read_bytes()
        for caminho in sorted(raiz.rglob('*'))
        if caminho.is_file() and caminho.name not in {'.manifesto.json', 'index.html'}
    }


async def test_analisar_pela_gui_gera_as_mesmas_saidas_que_a_cli(user: User, tmp_path, monkeypatch):
    pela_cli = tmp_path / 'cli'
    for nome in ('alfa', 'beta'):
        criar_concurso(pela_cli / 'provas', nome, config_simples(nome), ARQUIVOS_SIMPLES)
    pela_gui = tmp_path / 'gui'
    shutil.copytree(pela_cli, pela_gui)
    monkeypatch.chdir(pela_cli)
    assert main(['--yes', '--no-open', 'analyze']) == 0
    ESTADO.abrir_projeto(pela_gui)

    await user.open('/analise')
    user.find(marker='iniciar').click()
    await user.should_see('Análise concluída.', retries=200)

    gui, cli = retrato(pela_gui / 'analises'), retrato(pela_cli / 'analises')
    assert gui.keys() == cli.keys()
    assert [nome for nome in gui if gui[nome] != cli[nome]] == []


async def test_sobre_mostra_versao_e_caminho_do_log(user: User):
    await user.open('/sobre')

    await user.should_see(marker='versao')
    await user.should_see('concurso-analise')
    await user.should_see('Log:')
    await user.should_see('127.0.0.1')
