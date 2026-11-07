import tomllib
from pathlib import Path

from nicegui.testing.user import User

from concursos.aplicacao import atualizador as atualizacao
from concursos.aplicacao import exemplo
from concursos.gui.estado import ESTADO
from concursos.onboarding import ARQUIVO_LEIA_ME


def elemento(user: User, marca: str):
    return next(iter(user.find(marker=marca).elements))


async def ate_os_opcionais(user: User) -> None:
    await user.open('/inicio')
    await user.should_see('Passo 1 de 4: Seu nome')
    user.find(marker='nome').clear().type('Ana Teste')
    user.find(marker='continuar').click()
    await user.should_see('Passo 2 de 4: Pasta')
    user.find(marker='continuar').click()
    await user.should_see('Passo 3 de 4: Opcionais')


async def test_quatro_passos_com_os_opcionais_desmarcados_e_pular(user: User, projeto, home_isolada):
    await ate_os_opcionais(user)
    assert elemento(user, 'usar-ia').value is False
    assert elemento(user, 'opcional-atualizacao').value is False
    await user.should_see(marker='pular')

    user.find(marker='pular').click()

    await user.should_see('Passo 4 de 4: Primeiro resultado')
    config = tomllib.loads((projeto / '.concurso' / 'config.toml').read_text(encoding='utf-8'))
    assert config['candidato'] == {'ultimo': 'ana_teste'}
    assert (projeto / 'provas' / ARQUIVO_LEIA_ME).is_file()
    assert ESTADO.candidato == 'ana_teste'
    assert not atualizacao.ler_preferencias(Path(home_isolada) / 'config.toml').verificar_ao_abrir
    await user.should_not_see(marker='continuar')


async def test_sem_nome_fica_no_primeiro_passo_com_erro_e_dica(user: User, projeto, home_isolada):
    await user.open('/inicio')
    user.find(marker='nome').clear()
    user.find(marker='continuar').click()

    await user.should_see('erro: Falta o seu nome.')
    await user.should_see('Passo 1 de 4: Seu nome')
    assert not (projeto / '.concurso' / 'config.toml').exists()


async def test_marcar_o_aviso_de_versao_grava_a_preferencia(user: User, projeto, home_isolada):
    await ate_os_opcionais(user)
    elemento(user, 'opcional-atualizacao').value = True

    user.find(marker='continuar').click()

    await user.should_see('Passo 4 de 4: Primeiro resultado')
    assert atualizacao.ler_preferencias(Path(home_isolada) / 'config.toml').verificar_ao_abrir


async def test_voltar_mantem_o_que_foi_digitado(user: User, projeto, home_isolada):
    await user.open('/inicio')
    user.find(marker='nome').clear().type('Ana Teste')
    user.find(marker='continuar').click()
    await user.should_see('Passo 2 de 4: Pasta')

    user.find(marker='voltar').click()

    await user.should_see('Passo 1 de 4: Seu nome')
    assert elemento(user, 'nome').value == 'Ana Teste'


async def test_ver_com_um_exemplo_mostra_o_relatorio_do_exemplo(
    user: User, projeto, home_isolada, tmp_path, monkeypatch
):
    indice = tmp_path / 'exemplo' / 'index.html'
    indice.parent.mkdir()
    indice.write_text('<html>exemplo</html>', encoding='utf-8')
    homes = []
    monkeypatch.setattr(exemplo, 'analisar_exemplo', lambda home: homes.append(home) or indice)
    await ate_os_opcionais(user)
    user.find(marker='pular').click()
    await user.should_see('Passo 4 de 4: Primeiro resultado')

    user.find(marker='ver-exemplo').click()

    await user.should_see(marker='exemplo-pronto', retries=60)
    await user.should_see(marker='relatorio')
    assert homes == [Path(home_isolada)]


async def test_indicador_marca_so_o_passo_atual_com_aria_current(user: User, projeto, home_isolada):
    await user.open('/inicio')
    user.find(marker='nome').clear().type('Ana Teste')
    user.find(marker='continuar').click()
    await user.should_see('Passo 2 de 4: Pasta')

    itens = elemento(user, 'etapas').default_slot.children
    atuais = [item for item in itens if item.props.get('aria-current') == 'step']

    assert len(atuais) == 1
    assert [filho.text for filho in atuais[0].default_slot.children if hasattr(filho, 'text')] == ['2. Pasta']
    await user.should_see(marker='passo-2')
    await user.should_not_see(marker='passo-1')
