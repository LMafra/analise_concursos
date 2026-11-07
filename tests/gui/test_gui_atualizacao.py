from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from nicegui.testing.user import User

from concursos.aplicacao import atualizador as atualizacao
from concursos.atualizador import Artefato
from concursos.gui.estado import ESTADO
from concursos.modelo import CanalAtualizacao

NOVIDADE = atualizacao.Novidade(
    versao='9.0.0',
    canal=CanalAtualizacao.STABLE,
    notas='https://github.com/LMafra/analise_concursos/releases/tag/v9.0.0',
    plataforma='linux-x86_64',
    artefato=Artefato('concurso-analise-9.0.0-linux-x86_64.AppImage', 'a' * 64, 250_000_000),
    url='https://github.com/LMafra/analise_concursos/releases/download/v9.0.0/x',
)

PACOTE = SimpleNamespace(
    manifesto=SimpleNamespace(versao='1.16.0-1'), artefato=SimpleNamespace(tamanho=360_000_000)
)


def elemento(user: User, marca: str):
    return next(iter(user.find(marker=marca).elements))


@pytest.fixture
def executavel(monkeypatch, home_isolada):
    monkeypatch.setattr(atualizacao, 'no_executavel', lambda: True)


async def test_fora_do_executavel_o_sobre_mostra_o_comando_do_uv(user: User):
    await user.open('/sobre')

    await user.should_see(marker='atualizar-pelo-uv')
    await user.should_not_see(marker='verificar-atualizacoes')


async def test_sobre_so_consulta_no_clique_e_mostra_a_versao_nova(user: User, executavel, monkeypatch):
    consultas = []
    monkeypatch.setattr(atualizacao, 'verificar', lambda canal: consultas.append(canal) or NOVIDADE)

    await user.open('/sobre')
    assert consultas == []
    user.find(marker='verificar-atualizacoes').click()

    await user.should_see('Versão 9.0.0 disponível (stable).')
    await user.should_see(marker='instalar-atualizacao')
    assert consultas == [CanalAtualizacao.STABLE]
    assert ESTADO.novidade == NOVIDADE


async def test_sobre_sem_novidade_diz_que_esta_na_mais_nova(user: User, executavel, monkeypatch):
    monkeypatch.setattr(atualizacao, 'verificar', lambda canal: None)

    await user.open('/sobre')
    user.find(marker='verificar-atualizacoes').click()

    await user.should_see('Você já tem a versão mais nova do canal stable')


async def test_falha_na_consulta_aparece_como_erro_e_dica(user: User, executavel, monkeypatch):
    from concursos.erros import ErroDoAmbiente

    def falha(canal):
        raise ErroDoAmbiente('sem conexão com o GitHub para procurar a atualização', 'confira a internet')

    monkeypatch.setattr(atualizacao, 'verificar', falha)

    await user.open('/sobre')
    user.find(marker='verificar-atualizacoes').click()

    await user.should_see('erro: sem conexão com o GitHub para procurar a atualização')


async def test_o_detalhe_tecnico_do_erro_fica_fechado(user: User, executavel, monkeypatch):
    from nicegui import ui

    from concursos.erros import ErroDoAmbiente

    def falha(canal):
        raise ErroDoAmbiente(
            'Não consegui procurar a atualização.', 'confira a internet', 'HTTP 503 em api.github.com'
        )

    monkeypatch.setattr(atualizacao, 'verificar', falha)

    await user.open('/sobre')
    user.find(marker='verificar-atualizacoes').click()

    await user.should_see('erro: Não consegui procurar a atualização.')
    await user.should_see('dica: confira a internet')
    await user.should_see('Ver detalhes técnicos')
    (detalhes,) = user.find(marker='detalhes-tecnicos').elements
    assert isinstance(detalhes, ui.expansion)
    assert detalhes.value is False


async def test_instalar_pede_confirmacao_e_no_linux_oferece_reabrir(
    user: User, executavel, monkeypatch, tmp_path
):
    ESTADO.novidade = NOVIDADE
    instalados = []

    def instalar(novidade, progresso):
        progresso(1, 2)
        instalados.append(novidade)
        return atualizacao.Instalacao('9.0.0', tmp_path / 'x.AppImage', setup_em_andamento=False)

    monkeypatch.setattr(atualizacao, 'instalar', instalar)

    await user.open('/sobre')
    user.find(marker='instalar-atualizacao').click()
    await user.should_see('Baixar e instalar a 9.0.0?')
    assert instalados == []
    user.find(marker='confirmar-atualizacao').click()

    await user.should_see('Atualizado para 9.0.0. Reabrir agora?')
    assert instalados == [NOVIDADE]


async def test_chip_no_cabecalho_so_com_versao_nova(user: User):
    await user.open('/')
    await user.should_not_see('Versão 9.0.0 disponível')

    ESTADO.novidade = NOVIDADE
    await user.open('/')
    await user.should_see('Versão 9.0.0 disponível')


async def test_avancado_grava_canal_e_aviso_que_comecam_desligados(user: User, projeto, home_isolada):
    await user.open('/configuracoes')
    assert elemento(user, 'verificar-ao-abrir').value is False
    assert elemento(user, 'canal-atualizacao').value == 'stable'

    elemento(user, 'verificar-ao-abrir').value = True
    elemento(user, 'canal-atualizacao').value = 'beta'

    await user.should_see('Preferência de atualização gravada.')
    preferencias = atualizacao.ler_preferencias(Path(home_isolada) / 'config.toml')
    assert preferencias == atualizacao.Preferencias(CanalAtualizacao.BETA, True)


@pytest.fixture
def biblioteca_pronta(monkeypatch):
    from concursos.aplicacao import sobre

    original = sobre.resumo_do_app
    monkeypatch.setattr(
        sobre,
        'resumo_do_app',
        lambda home: replace(original(home), biblioteca='pronta', biblioteca_pronta=True),
    )
    return sobre


async def test_com_biblioteca_um_clique_confere_o_app_e_a_biblioteca(
    user: User, executavel, biblioteca_pronta, monkeypatch
):
    monkeypatch.setattr(atualizacao, 'verificar', lambda canal: None)
    monkeypatch.setattr(biblioteca_pronta, 'biblioteca_nova', lambda home: PACOTE)
    instalados = []
    monkeypatch.setattr(
        biblioteca_pronta,
        'atualizar_biblioteca',
        lambda home, progresso: instalados.append(home) or '1.16.0-1',
    )

    await user.open('/sobre')
    await user.should_see('Verificar atualizações do app e da biblioteca')
    user.find(marker='verificar-atualizacoes').click()

    await user.should_see('Biblioteca: versão 1.16.0-1 disponível.')
    user.find(marker='instalar-biblioteca').click()
    await user.should_see('Atualizar a biblioteca para a 1.16.0-1?')
    assert instalados == []
    user.find(marker='confirmar-biblioteca').click()

    await user.should_see('Biblioteca atualizada para a 1.16.0-1; seus livros continuam lá.')
    assert len(instalados) == 1


async def test_fora_do_executavel_com_biblioteca_confere_so_a_biblioteca(
    user: User, biblioteca_pronta, monkeypatch
):
    monkeypatch.setattr(
        atualizacao, 'verificar', lambda canal: pytest.fail('consultou o app fora do executável')
    )
    monkeypatch.setattr(biblioteca_pronta, 'biblioteca_nova', lambda home: None)

    await user.open('/sobre')
    await user.should_see(marker='atualizar-pelo-uv')
    user.find(marker='verificar-atualizacoes').click()

    await user.should_see('A biblioteca já está na versão mais nova.')
