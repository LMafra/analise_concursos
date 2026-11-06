import pytest
from nicegui.testing.user import User

from concursos.aplicacao import conferencia
from concursos.aplicacao.conferencia import (
    CampoAConfirmar,
    GrupoDisciplinas,
    LinhaTopico,
    OpcaoTopico,
    Pendencias,
    Taxonomia,
)
from concursos.erros import ErroDoUsuario
from concursos.modelo import Bloco, TipoCampo
from concursos.topicos import NAO_MAPEADO

LINHAS = [
    LinhaTopico(1, 'unica', 'Assinale a crase.', 'Português', 'Crase', 0.4),
    LinhaTopico(2, 'unica', 'Sobre o texto, é correto.', 'Português', NAO_MAPEADO, 0.0),
]
OPCOES = [OpcaoTopico('Português', 'Crase'), OpcaoTopico('Português', 'Interpretação')]


@pytest.fixture
def conferir(monkeypatch):
    """A camada de aplicação falsa: grava em memória e a reanálise só registra o pedido."""
    estado = {'topicos': [], 'campos': [], 'reanalises': [], 'taxonomia': Taxonomia([], [])}
    monkeypatch.setattr(conferencia, 'topicos_para_conferir', lambda contexto, concurso: LINHAS)
    monkeypatch.setattr(conferencia, 'opcoes_de_topico', lambda contexto, concurso: OPCOES)
    monkeypatch.setattr(
        conferencia,
        'campos_a_confirmar',
        lambda contexto, concurso: [
            CampoAConfirmar('data_prova', 'Data da prova objetiva', 'O dia da prova.', TipoCampo.DATA)
        ],
    )

    def gravar_topicos(contexto, concurso, escolhas):
        estado['topicos'].append(escolhas)
        return True

    def gravar_campos(contexto, concurso, valores):
        if valores['data_prova'] == '31/02/2026':
            raise ErroDoUsuario('Data da prova objetiva: "31/02/2026" não é uma data', 'use DD/MM/AAAA')
        estado['campos'].append(valores)
        return True

    def reanalisar(opcoes, concurso=None):
        estado['reanalises'].append(concurso)
        return 0

    monkeypatch.setattr(conferencia, 'gravar_topicos', gravar_topicos)
    monkeypatch.setattr(conferencia, 'gravar_campos', gravar_campos)
    monkeypatch.setattr(conferencia, 'reanalisar_afetados', reanalisar)
    monkeypatch.setattr(conferencia, 'taxonomia', lambda contexto: estado['taxonomia'])

    def juntar(contexto, nomes, canonica, bloco):
        estado['taxonomia'] = Taxonomia([GrupoDisciplinas(canonica, bloco, tuple(nomes[1:]))], [])
        return True

    monkeypatch.setattr(conferencia, 'juntar_disciplinas', juntar)
    return estado


async def test_topicos_pendentes_primeiro_e_salvar_refaz_a_analise(user: User, projeto, conferir):
    await user.open('/conferir?concurso=tcu')

    await user.should_see('1 questões sem um tópico confiável')
    user.find(marker='topico-unica-2').elements.pop().value = '1'
    user.find(marker='salvar-topicos').click()

    await user.should_see('Análise refeita.')
    assert conferir['topicos'] == [{(2, 'unica'): OPCOES[1]}]
    assert conferir['reanalises'] == ['tcu']


async def test_salvar_sem_mudar_nao_grava(user: User, projeto, conferir):
    await user.open('/conferir?concurso=tcu')

    user.find(marker='salvar-topicos').click()

    await user.should_see('Nada mudou.')
    assert conferir['topicos'] == []


async def test_dados_do_edital_com_data_invalida_mostra_o_erro(user: User, projeto, conferir):
    await user.open('/conferir?concurso=tcu&aba=edital')

    user.find(marker='campo-data_prova').type('31/02/2026')
    user.find(marker='salvar-campos').click()
    await user.should_see('não é uma data')
    assert conferir['campos'] == []

    user.find(marker='campo-data_prova').clear().type('15/03/2026')
    user.find(marker='salvar-campos').click()
    await user.should_see('Análise refeita.')
    assert conferir['campos'] == [{'data_prova': '15/03/2026'}]


async def test_card_do_concurso_mostra_as_pendencias(user: User, projeto, monkeypatch):
    from concursos.aplicacao import analise
    from concursos.status import Situacao, StatusConcurso

    item = StatusConcurso('tcu', Situacao.COMPLETO, (), 'definitivo', None)
    monkeypatch.setattr(analise, 'situacoes', lambda provas, candidato=None: [item])
    monkeypatch.setattr(conferencia, 'pendencias', lambda contexto, nome: Pendencias(3, 1))
    (projeto / 'provas').mkdir(parents=True, exist_ok=True)

    await user.open('/')

    await user.should_see('Conferir (4)')
    user.find(marker='conferir-tcu').click()
    await user.should_see('Conferir tcu')


async def test_juntar_disciplinas(user: User, projeto, conferir):
    conferir['taxonomia'] = Taxonomia([], ['Língua Portuguesa', 'Português'])
    await user.open('/disciplinas')

    user.find(marker='solta-Língua Portuguesa').click()
    user.find(marker='solta-Português').click()
    user.find(marker='juntar-disciplinas').click()
    await user.should_see(marker='dialogo-juntar')
    user.find(marker='confirmar-juntar').click()

    await user.should_see('Também aparece como: Português')
    await user.should_see('Análise refeita.')
    assert conferir['reanalises'] == [None]
    assert user.find(marker='bloco-Língua Portuguesa').elements.pop().value == Bloco.GERAL.value


async def test_configuracoes_abre_disciplinas(user: User, projeto, conferir):
    await user.open('/configuracoes')

    user.find(marker='abrir-disciplinas').click()
    await user.should_see('Disciplinas e temas')
    await user.should_see(marker='sem-disciplinas')
