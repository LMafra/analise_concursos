import asyncio
import shutil
import threading
import tomllib
from pathlib import Path

import pytest
from concurso_sintetico import ARQUIVOS_SIMPLES, config_simples, criar_concurso
from nicegui import ui
from nicegui.testing.user import User

from concursos import doctor as diagnostico
from concursos import janela
from concursos.aplicacao import analise
from concursos.aplicacao import projeto as projeto_aplicacao
from concursos.aplicacao.opcoes import Opcoes
from concursos.cli import main
from concursos.erros import ErroDoUsuario
from concursos.gui import app as gui_app
from concursos.gui.estado import ESTADO
from concursos.modelo import DecisaoJanela, Etapa


async def esperar(condicao, segundos: float = 3.0) -> None:
    for _ in range(int(segundos / 0.05)):
        if condicao():
            return
        await asyncio.sleep(0.05)
    raise AssertionError('condição não atingida a tempo')


@pytest.fixture
def ao_subir(monkeypatch) -> list:
    """O que `executar` agendaria para a subida do servidor, sem registrar no app de verdade."""
    agendados: list = []
    monkeypatch.setattr(gui_app.app, 'on_startup', agendados.append)
    monkeypatch.setattr(gui_app.app, 'on_connect', agendados.append)
    monkeypatch.setattr(gui_app.app, 'on_shutdown', agendados.append)
    return agendados


@pytest.fixture
def reaberturas(monkeypatch) -> list[list[str]]:
    comandos: list[list[str]] = []
    monkeypatch.setattr(gui_app.subprocess, 'Popen', lambda comando, env: comandos.append((comando, env)))
    return comandos


@pytest.mark.parametrize(('plataforma', 'nativa'), [('linux', False), ('win32', True), ('darwin', True)])
def test_executar_so_escuta_no_proprio_computador(monkeypatch, tmp_path, ao_subir, plataforma, nativa):
    chamadas: list[dict] = []
    monkeypatch.setattr(gui_app.ui, 'run', lambda raiz, **kwargs: chamadas.append(kwargs))
    monkeypatch.setattr(gui_app.sys, 'platform', plataforma)
    monkeypatch.setattr(janela, 'ler_registro_windows', lambda raiz, chave: '130.0.2849.56')

    gui_app.executar(tmp_path / 'projeto')

    assert chamadas[0]['host'] == '127.0.0.1'
    assert chamadas[0]['reload'] is False
    assert chamadas[0]['native'] is nativa
    assert chamadas[0]['language'] == 'pt-BR'
    assert ESTADO.projeto == (tmp_path / 'projeto').resolve()


def test_browser_forca_o_navegador_mesmo_fora_do_linux(monkeypatch, tmp_path, ao_subir, navegador):
    chamadas: list[dict] = []
    monkeypatch.setattr(gui_app.ui, 'run', lambda raiz, **kwargs: chamadas.append(kwargs))
    monkeypatch.setattr(gui_app.sys, 'platform', 'win32')

    gui_app.executar(tmp_path, navegador=True, porta=8123)

    assert chamadas[0]['native'] is False
    assert 'window_size' not in chamadas[0]
    ao_subir[0]()
    assert navegador == ['http://127.0.0.1:8123/']


async def test_no_navegador_o_menu_fecha_o_app(user: User, monkeypatch):
    encerrado: list[bool] = []
    monkeypatch.setattr(gui_app.app, 'shutdown', lambda: encerrado.append(True))
    ESTADO.no_navegador = True

    await user.open('/')
    user.find(marker='fechar-app').click()

    await user.should_see('Pode fechar esta aba')
    await esperar(lambda: encerrado)


async def test_no_navegador_nao_fecha_no_meio_da_analise(user: User, monkeypatch):
    encerrado: list[bool] = []
    monkeypatch.setattr(gui_app.app, 'shutdown', lambda: encerrado.append(True))
    ESTADO.no_navegador = True
    ESTADO.ocupado = True

    await user.open('/')
    user.find(marker='fechar-app').click()

    await user.should_see('Espere a análise terminar')
    await asyncio.sleep(0.8)
    assert not encerrado


async def test_na_janela_o_menu_nao_tem_fechar(user: User):
    await user.open('/')
    await user.should_not_see(marker='fechar-app')


def test_executar_lembra_se_abriu_no_navegador(monkeypatch, tmp_path, ao_subir, navegador):
    monkeypatch.setattr(gui_app.ui, 'run', lambda raiz, **kwargs: None)

    gui_app.executar(tmp_path, navegador=True, porta=8123)

    assert ESTADO.no_navegador is True


def test_windows_sem_webview2_abre_no_navegador_e_guarda_o_motivo(monkeypatch, tmp_path, ao_subir, navegador):
    chamadas: list[dict] = []
    monkeypatch.setattr(gui_app.ui, 'run', lambda raiz, **kwargs: chamadas.append(kwargs))
    monkeypatch.setattr(gui_app.sys, 'platform', 'win32')
    monkeypatch.setattr(janela, 'ler_registro_windows', lambda raiz, chave: None)
    monkeypatch.setattr(janela, 'versao_pelo_loader_windows', lambda: None)

    gui_app.executar(tmp_path, porta=8123)

    assert chamadas[0]['native'] is False
    assert ESTADO.decisao_janela is DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2
    assert navegador == [] and ao_subir
    ao_subir[0]()
    assert navegador == ['http://127.0.0.1:8123/']


def test_janela_que_quebra_ao_abrir_reabre_no_navegador(monkeypatch, tmp_path, ao_subir, reaberturas):
    def quebra(raiz, **kwargs):
        raise RuntimeError('WebView2 corrompido')

    monkeypatch.setattr(gui_app.ui, 'run', quebra)
    monkeypatch.setattr(gui_app.sys, 'platform', 'darwin')

    gui_app.executar(tmp_path / 'projeto', porta=8123)

    comando, ambiente = reaberturas[0]
    assert comando[-3:] == ['--browser', '--project', str((tmp_path / 'projeto').resolve())]
    assert ambiente[janela.VARIAVEL_JANELA_FALHOU] == '1'


def test_janela_que_fecha_sem_carregar_reabre_uma_vez_so(monkeypatch, tmp_path, ao_subir, reaberturas):
    monkeypatch.setattr(gui_app.ui, 'run', lambda raiz, **kwargs: None)
    monkeypatch.setattr(gui_app.sys, 'platform', 'darwin')
    gui_app.executar(tmp_path, porta=8123)
    marcar, encerrar = ao_subir

    encerrar()
    encerrar()

    assert len(reaberturas) == 1
    assert marcar is gui_app.marcar_conexao


def test_janela_usada_e_fechada_nao_reabre(monkeypatch, tmp_path, ao_subir, reaberturas):
    monkeypatch.setattr(gui_app.ui, 'run', lambda raiz, **kwargs: None)
    monkeypatch.setattr(gui_app.sys, 'platform', 'darwin')
    gui_app.executar(tmp_path, porta=8123)
    marcar, encerrar = ao_subir

    marcar()
    encerrar()

    assert reaberturas == []


def test_reaberto_depois_da_falha_mostra_o_aviso(monkeypatch, tmp_path, ao_subir, navegador):
    monkeypatch.setattr(gui_app.ui, 'run', lambda raiz, **kwargs: None)
    monkeypatch.setenv(janela.VARIAVEL_JANELA_FALHOU, '1')

    gui_app.executar(tmp_path, navegador=True, porta=8123)

    assert ESTADO.janela_falhou is True


async def test_aviso_sem_webview2_tem_link_e_entendi_que_lembra(user: User, home_isolada):
    ESTADO.decisao_janela = DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2

    await user.open('/')
    await user.should_see(janela.TITULO_AVISO)
    await user.should_see(marker='link-webview2')
    user.find(marker='dispensar-aviso-janela').click()

    await user.should_not_see(janela.TITULO_AVISO)
    configuracao = tomllib.loads((home_isolada / 'config.toml').read_text(encoding='utf-8'))
    assert configuracao['gui']['aviso_webview2_dispensado'] is True


async def test_aviso_dispensado_nao_volta_mas_a_falha_da_janela_sim(user: User, home_isolada):
    home_isolada.mkdir(parents=True, exist_ok=True)
    (home_isolada / 'config.toml').write_text('[gui]\naviso_webview2_dispensado = true\n', encoding='utf-8')
    ESTADO.decisao_janela = DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2

    await user.open('/')
    await user.should_not_see(janela.TITULO_AVISO)

    ESTADO.janela_falhou = True
    await user.open('/')
    await user.should_see(janela.TITULO_AVISO)


async def test_navegador_pedido_nao_avisa(user: User):
    ESTADO.decisao_janela = DecisaoJanela.NAVEGADOR_PEDIDO

    await user.open('/')
    await user.should_not_see(janela.TITULO_AVISO)


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


async def test_concursos_com_um_candidato_le_as_respostas_da_pasta_dele(user: User, projeto):
    config = config_simples('alfa')
    del config['respostas']
    pasta = criar_concurso(projeto / 'provas', 'alfa', config, {'gabarito.txt': '1 A\n2 B\n'})
    (pasta / 'candidatos' / 'ana_teste').mkdir(parents=True)
    (pasta / 'candidatos' / 'ana_teste' / 'respostas.txt').write_text('1 A\n2 C\n', encoding='utf-8')

    await user.open('/')

    await user.should_see('completo')
    await user.should_not_see('respostas não configuradas')
    assert ESTADO.candidato == 'ana_teste'


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


async def test_analisar_mostra_a_etapa_atual_do_concurso(user: User, projeto, monkeypatch):
    liberar = threading.Event()

    def analisar_falso(opcoes: Opcoes) -> int:
        opcoes.ao_progresso('alfa', 1, 2)
        opcoes.ao_etapa('alfa', Etapa.LENDO_FOLHA)
        liberar.wait(5)
        return 0

    monkeypatch.setattr(analise, 'analisar', analisar_falso)

    await user.open('/analise')
    user.find(marker='iniciar').click()

    await user.should_see('Analisando alfa (1 de 2): Lendo a folha…', retries=60)
    liberar.set()
    await user.should_see('Análise concluída.', retries=60)


async def test_analisar_mostra_erro_e_dica_como_a_cli(user: User, projeto, monkeypatch):
    def analisar_falso(opcoes: Opcoes) -> int:
        raise ErroDoUsuario('pasta de provas não encontrada', 'crie uma subpasta por concurso')

    monkeypatch.setattr(analise, 'analisar', analisar_falso)

    await user.open('/analise')
    user.find(marker='iniciar').click()

    await user.should_see('erro: pasta de provas não encontrada', retries=60)
    await user.should_see('dica: crie uma subpasta por concurso')


async def test_botao_analisar_da_lista_ja_inicia_a_analise(user: User, projeto, monkeypatch):
    criar_concurso(projeto / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)
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


async def test_projeto_vazio_oferece_criar_o_primeiro_concurso(user: User, projeto):
    await user.open('/')

    user.find(marker='sem-concursos-acao').click()

    await user.should_see(marker='soltar')


async def test_situacao_do_concurso_tem_icone_e_texto(user: User, projeto):
    criar_concurso(projeto / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)

    await user.open('/')

    await user.should_see('completo')
    await user.should_see(kind=ui.icon, content='check_circle')


async def test_sobre_confere_o_ambiente_sem_sair_da_tela(user: User, projeto, monkeypatch):
    monkeypatch.setattr(projeto_aplicacao, 'diagnosticar', lambda contexto: [])
    monkeypatch.setattr(diagnostico, 'formatar', lambda itens: 'tudo certo no ambiente')
    await user.open('/sobre')

    user.find(marker='conferir-ambiente').click()

    await user.should_see('tudo certo no ambiente')
