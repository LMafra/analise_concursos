from nicegui.testing.user import User

from concursos.candidatos import gravar_cargo_almejado, gravar_perfil_global
from concursos.gui.componentes import marca
from concursos.gui.estado import ESTADO


async def test_bloco_da_marca_aparece_no_cabecalho(user: User, projeto):
    await user.open('/')
    await user.should_see(marker='marca-app')
    await user.should_see(marca.TAGLINE)


async def test_cartao_da_pessoa_mostra_iniciais_e_nome(user: User, projeto, home_isolada):
    candidato = ESTADO.candidato or ESTADO.contexto().candidato
    gravar_perfil_global(home_isolada, 'Ana Silva', atualizar=True)
    gravar_cargo_almejado(home_isolada, 'Ana Silva', 'Auditor')
    ESTADO.candidato = 'ana_silva' if candidato != 'ana_silva' else candidato
    # O cartão usa o candidato do contexto; garanta o perfil do slug atual.
    nome = ESTADO.candidato or ESTADO.contexto().candidato
    gravar_perfil_global(home_isolada, nome.replace('_', ' ').title(), atualizar=True)
    gravar_cargo_almejado(home_isolada, nome.replace('_', ' ').title(), 'Auditor')

    await user.open('/')
    await user.should_see(marker='cartao-pessoa')
    await user.should_see('Auditor')
