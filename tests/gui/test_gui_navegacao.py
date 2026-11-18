import pytest
from nicegui.testing.user import User

from concursos.gui.app import MENU, UTILITARIO


def test_menu_principal_tem_os_4_itens_e_utilitarios():
    assert [nome for _, nome, _ in MENU] == [
        'Minhas Provas',
        'Resultados',
        'Estudar',
        'Concursos',
    ]
    assert [nome for _, nome, _ in UTILITARIO] == ['Configurações', 'Sobre']


async def test_cabecalho_mostra_o_menu_lateral(user: User, projeto):
    await user.open('/')

    for marca in ('menu-provas', 'menu-estudar', 'menu-resultados', 'menu-concursos'):
        await user.should_see(marker=marca)
    await user.should_not_see('Integrações')
    await user.should_see(marker='menu-configuracoes')
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


async def test_aba_de_provas_pelo_endereco_dos_concursos(user: User, projeto):
    await user.open('/concursos?aba=provas')

    await user.should_see(marker='aviso-pci')
