import pytest
from nicegui import ui
from nicegui.testing.user import User

from concursos.gui.app import MENU, UTILITARIO


def test_menu_principal_tem_os_5_itens_e_o_utilitario_tem_configuracoes_e_sobre():
    assert [nome for _, nome, _ in MENU] == [
        'Concursos',
        'Estudar',
        'Analisar',
        'Resultados',
        'Importar do TEC',
    ]
    assert [nome for _, nome, _ in UTILITARIO] == ['Configurações', 'Sobre']


async def test_cabecalho_mostra_o_menu_e_esconde_configuracoes_no_utilitario(user: User, projeto):
    await user.open('/')

    for marca in ('menu-concursos', 'menu-estudar', 'menu-analise', 'menu-resultados', 'menu-tec'):
        await user.should_see(marker=marca)
    await user.should_not_see('Integrações')
    await user.should_not_see(kind=ui.button, content='Configurações')
    user.find(marker='menu-utilitario').click()
    user.find(marker='menu-sobre').click()

    await user.should_see(marker='versao')


@pytest.mark.parametrize(
    ('antigo', 'marca'),
    [
        ('/integracoes', 'aviso-pci'),
        ('/integracoes?aba=descobrir', 'aviso-pci'),
        ('/descobrir', 'aviso-pci'),
        ('/integracoes?aba=provas', 'aviso-pci'),
        ('/integracoes?aba=tec', 'soltar-tec'),
        ('/integracoes?aba=notebook', 'url-notebook'),
    ],
)
async def test_enderecos_antigos_redirecionam(user: User, projeto, antigo, marca):
    await user.open(antigo)

    await user.should_see(marker=marca)


async def test_aba_da_lista_e_de_provas_pelo_endereco(user: User, projeto):
    await user.open('/?aba=provas')

    await user.should_see(marker='aviso-pci')
    await user.should_see('Meus concursos')
