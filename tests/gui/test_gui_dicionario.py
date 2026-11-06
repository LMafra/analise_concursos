import pytest
from nicegui.testing.user import User

from concursos.analytics.dicionario_topicos import EntradaTema, SugestaoTermo
from concursos.aplicacao import conferencia, dicionario
from concursos.aplicacao.dicionario import SituacaoDicionario, UltimoGanho

CRASE = EntradaTema('lingua_portuguesa', 'crase', ('Emprego da crase',), ('acento grave',))
SUGESTAO = SugestaoTermo('lingua_portuguesa', 'crase', 'Emprego da crase', 'fusao', 3, ('tcu',))


@pytest.fixture
def temas(monkeypatch):
    """O dicionário falso, em memória; a reanálise só registra o pedido."""
    estado = {
        'existe': False,
        'ligado': False,
        'entradas': [],
        'ultimo': None,
        'aceitas': [],
        'recusadas': [],
        'gravados': [],
        'reanalises': [],
    }

    def situacao(contexto):
        return SituacaoDicionario(
            estado['existe'], estado['ligado'], len(estado['entradas']), estado['ultimo']
        )

    def iniciar(contexto):
        estado.update(existe=True, ligado=True, entradas=[CRASE])
        return 1

    def ligar(contexto, usar):
        estado['ligado'] = usar

    def avaliar(contexto):
        estado['ultimo'] = UltimoGanho(0.61, 0.68, 210, '2026-11-06', False)

    def gravar_topico(contexto, disciplina, topico, termos, expressoes):
        estado['gravados'].append((disciplina, topico, termos, expressoes))
        return True

    def reanalisar(opcoes, concurso=None):
        estado['reanalises'].append(concurso)
        return 0

    monkeypatch.setattr(dicionario, 'situacao', situacao)
    monkeypatch.setattr(dicionario, 'temas', lambda contexto: estado['entradas'])
    monkeypatch.setattr(dicionario, 'iniciar', iniciar)
    monkeypatch.setattr(dicionario, 'ligar', ligar)
    monkeypatch.setattr(dicionario, 'avaliar', avaliar)
    monkeypatch.setattr(dicionario, 'sugestoes', lambda contexto: [SUGESTAO])
    monkeypatch.setattr(dicionario, 'aceitar', lambda contexto, s: estado['aceitas'].append(s) or True)
    monkeypatch.setattr(dicionario, 'recusar', lambda contexto, s: estado['recusadas'].append(s) or True)
    monkeypatch.setattr(dicionario, 'gravar_topico', gravar_topico)
    monkeypatch.setattr(conferencia, 'reanalisar_afetados', reanalisar)
    return estado


async def test_comecar_com_o_inicial_liga_e_refaz_a_analise(user: User, projeto, temas):
    await user.open('/disciplinas?aba=temas')

    await user.should_see('Ainda sem dicionário')
    user.find(marker='iniciar-dicionario').click()

    await user.should_see('Ligado, com 1 temas.')
    await user.should_see('Análise refeita.')
    assert temas['reanalises'] == [None]


async def test_testar_ganho_mostra_antes_e_depois(user: User, projeto, temas):
    temas.update(existe=True, ligado=True, entradas=[CRASE])
    await user.open('/disciplinas?aba=temas')

    user.find(marker='testar-ganho').click()

    await user.should_see('Último teste: acertos 61% → 68% (n = 210), em 06/11/2026')


async def test_alerta_oferece_desligar(user: User, projeto, temas):
    temas.update(
        existe=True, ligado=True, entradas=[CRASE], ultimo=UltimoGanho(0.7, 0.6, 30, '2026-11-06', True)
    )
    await user.open('/disciplinas?aba=temas')

    await user.should_see('O dicionário piorou a sugestão de tema')
    user.find(marker='desligar-dicionario').click()

    await user.should_see('Desligado (1 temas guardados).')
    await user.should_not_see('O dicionário piorou a sugestão de tema')
    assert temas['ligado'] is False


async def test_aceitar_sugestao_e_refazer_a_analise(user: User, projeto, temas):
    await user.open('/disciplinas?aba=temas')

    user.find(marker='sugerir-termos').click()
    await user.should_see('"fusao" → Emprego da crase (3 questões)')
    user.find(marker=f'aceitar-{SUGESTAO.chave}').click()

    await user.should_not_see('"fusao" → Emprego da crase (3 questões)')
    assert temas['aceitas'] == [SUGESTAO]
    assert temas['reanalises'] == []
    user.find(marker='refazer-analise').click()
    await user.should_see('Análise refeita.')


async def test_editar_termos_de_um_tema(user: User, projeto, temas):
    temas.update(existe=True, ligado=True, entradas=[CRASE])
    await user.open('/disciplinas?aba=temas')

    user.find(marker='tema-lingua_portuguesa/crase').click()
    user.find(marker='termos-lingua_portuguesa/crase').clear().type('acento grave; fusão')
    user.find(marker='salvar-lingua_portuguesa/crase').click()

    await user.should_see('Análise refeita.')
    assert temas['gravados'] == [('lingua_portuguesa', 'crase', ['acento grave', 'fusão'], [])]


async def test_configuracoes_resume_o_dicionario(user: User, projeto, temas):
    temas.update(
        existe=True, ligado=True, entradas=[CRASE], ultimo=UltimoGanho(0.61, 0.68, 210, '2026-11-06', False)
    )
    await user.open('/configuracoes')

    await user.should_see('Usado, com 1 temas.')
    await user.should_see('acertos 61% → 68%')
    user.find(marker='abrir-dicionario').click()
    await user.should_see(marker='aba-temas')
    await user.should_see('Testar ganho')
