import asyncio

import yaml
from concurso_sintetico import ARQUIVOS_SIMPLES, config_simples, criar_concurso
from nicegui import ui
from nicegui.testing.user import User

from concursos.aplicacao import analise, cadastro
from concursos.aplicacao.opcoes import Opcoes
from concursos.candidatos import adicionar_arquivo
from concursos.deteccao import Papel
from concursos.gui.estado import ESTADO
from concursos.gui.paginas import novo_concurso
from concursos.modelo import Formato
from concursos.respostas import ler_respostas_csv

GABARITO_FGV = '# FGV - Gabarito definitivo\n1 A\n2 B\n'


async def esperar(condicao, segundos: float = 5.0) -> None:
    for _ in range(int(segundos / 0.05)):
        if condicao():
            return
        await asyncio.sleep(0.05)
    raise AssertionError('condição não atingida a tempo')


async def soltar(user: User, **arquivos: str) -> None:
    upload = next(iter(user.find(ui.upload).elements))
    await upload.handle_uploads(
        [
            ui.upload.SmallFileUpload(nome, 'text/plain', conteudo.encode())
            for nome, conteudo in arquivos.items()
        ]
    )


async def test_pasta_nova_leva_ao_onboarding(user: User, tmp_path):
    await user.open('/')
    user.find(marker='campo-pasta').clear().type(str(tmp_path / 'Concursos'))
    user.find(marker='usar-projeto').click()

    await user.should_see('Bem-vindo ao concurso-analise')


async def test_concursos_convida_ao_onboarding_quando_falta_configurar(user: User, projeto):
    await user.open('/')

    await user.should_see(marker='fazer-onboarding')


async def test_soltar_arquivos_mostra_o_papel_detectado_e_trocar_muda_o_cadastro(
    user: User, projeto, monkeypatch
):
    chamadas: list[tuple] = []
    monkeypatch.setattr(
        cadastro, 'cadastrar_envio', lambda opcoes, nome, papeis, candidato: chamadas.append((nome, papeis))
    )
    await user.open('/novo')
    user.find(marker='nome-concurso').type('alfa')
    await soltar(user, **{'gabarito.txt': GABARITO_FGV, 'minhas.txt': '1 A\n2 C\n'})

    await user.should_see('Detectamos: gabarito. Confirma?')
    await user.should_see('Detectamos: suas respostas digitadas. Confirma?')
    next(iter(user.find(marker='papel-minhas.txt').elements)).value = Papel.IGNORADO.value
    user.find(marker='cadastrar').click()

    await esperar(lambda: chamadas)
    nome, papeis = chamadas[0]
    assert nome == 'alfa'
    assert {caminho.name: papel for caminho, papel in papeis.items()} == {
        'gabarito.txt': Papel.GABARITO,
        'minhas.txt': Papel.IGNORADO,
    }


async def test_cadastrar_sem_nome_pede_o_nome_sem_tentar_cadastrar(user: User, projeto, monkeypatch):
    chamadas: list[str] = []
    monkeypatch.setattr(cadastro, 'cadastrar_envio', lambda opcoes, nome, *_: chamadas.append(nome))
    await user.open('/novo')
    await soltar(user, **{'gabarito.txt': GABARITO_FGV})
    await user.should_see('Detectamos: gabarito. Confirma?')

    user.find(marker='cadastrar').click()

    await user.should_see('Dê um nome ao concurso antes de cadastrar (ex.: tcu_2025).')
    assert chamadas == []


async def test_cadastro_pergunta_em_dialogo_e_grava_com_as_respostas_na_pasta_do_candidato(
    user: User, projeto
):
    await user.open('/novo')
    user.find(marker='nome-concurso').type('alfa')
    user.find(marker='candidato-envio').clear().type('Ana Teste')
    await soltar(user, **{'gabarito.txt': GABARITO_FGV, 'minhas.txt': '1 A\n2 C\n'})
    await user.should_see('Detectamos: gabarito. Confirma?')
    user.find(marker='cadastrar').click()

    await user.should_see('Gravar concurso.yaml?', retries=60)
    user.find(marker='sim').click()

    await user.should_see(marker='cadastrado', retries=60)
    pasta = projeto / 'provas' / 'alfa'
    assert yaml.safe_load((pasta / 'concurso.yaml').read_text(encoding='utf-8'))['banca'] == 'fgv'
    assert (pasta / 'candidatos' / 'ana_teste' / 'minhas.txt').is_file()
    assert not any((projeto / '.concurso' / 'envios').iterdir())


async def test_recusar_no_dialogo_nao_grava_nada(user: User, projeto):
    await user.open('/novo')
    user.find(marker='nome-concurso').type('alfa')
    await soltar(user, **{'gabarito.txt': GABARITO_FGV})
    await user.should_see('Detectamos: gabarito. Confirma?')
    user.find(marker='cadastrar').click()

    await user.should_see('Gravar concurso.yaml?', retries=60)
    user.find(marker='nao').click()

    await user.should_see('Nada foi gravado.', retries=60)
    await esperar(lambda: not ESTADO.ocupado)
    assert not (projeto / 'provas' / 'alfa').exists()


async def test_escolha_em_dialogo_volta_para_a_thread_do_cadastro(user: User, projeto, monkeypatch):
    escolhas: list[str] = []

    def cadastrar_falso(opcoes: Opcoes, nome, papeis, candidato):
        escolhas.append(opcoes.interacao.escolher('Qual é a banca?', ['fgv', 'cebraspe'], 'fgv'))
        return None

    monkeypatch.setattr(cadastro, 'cadastrar_envio', cadastrar_falso)
    await user.open('/novo')
    user.find(marker='nome-concurso').type('alfa')
    await soltar(user, **{'gabarito.txt': GABARITO_FGV})
    await user.should_see('Detectamos: gabarito. Confirma?')
    user.find(marker='cadastrar').click()

    await user.should_see('Qual é a banca?', retries=60)
    next(iter(user.find(marker='opcoes').elements)).value = 'cebraspe'
    user.find(marker='ok').click()

    await esperar(lambda: escolhas)
    assert escolhas == ['cebraspe']


async def test_cancelar_a_pergunta_cancela_o_cadastro(user: User, projeto, monkeypatch):
    def cadastrar_falso(opcoes: Opcoes, nome, papeis, candidato):
        opcoes.interacao.escolher('Qual é a banca?', ['fgv', 'cebraspe'])
        raise AssertionError('não devia continuar')

    monkeypatch.setattr(cadastro, 'cadastrar_envio', cadastrar_falso)
    await user.open('/novo')
    user.find(marker='nome-concurso').type('alfa')
    await soltar(user, **{'gabarito.txt': GABARITO_FGV})
    await user.should_see('Detectamos: gabarito. Confirma?')
    user.find(marker='cadastrar').click()

    await user.should_see('Qual é a banca?', retries=60)
    user.find(marker='cancelar').click()

    await user.should_see('Cadastro cancelado; nada foi gravado.', retries=60)


async def test_sem_tesseract_avisa_e_oferece_digitar(user: User, projeto, monkeypatch):
    monkeypatch.setattr(novo_concurso, 'ocr_disponivel', lambda: False)

    await user.open('/novo')

    await user.should_see(marker='sem-tesseract')


async def test_respostas_digitadas_gravam_csv_valido(user: User, projeto):
    pasta = criar_concurso(projeto / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)

    await user.open('/respostas?concurso=alfa')
    user.find(marker='candidato-respostas').clear().type('Ana Teste')
    await user.should_see(marker='q1')
    next(iter(user.find(marker='q1').elements)).value = 'A'
    next(iter(user.find(marker='q2').elements)).value = 'D'
    user.find(marker='gravar').click()

    await user.should_see(marker='gravado', retries=60)
    csv = pasta / 'candidatos' / 'ana_teste' / 'respostas.csv'
    lidas = ler_respostas_csv(csv.read_bytes(), Formato.MULTIPLA_ESCOLHA, [1, 2], 'respostas.csv')
    assert [(r.questao, r.alternativa) for r in lidas] == [(1, 'A'), (2, 'D')]


async def test_com_dois_candidatos_todos_analisa_com_todos(user: User, projeto, tmp_path, monkeypatch):
    pasta = criar_concurso(projeto / 'provas', 'alfa', config_simples('alfa'), ARQUIVOS_SIMPLES)
    respostas = tmp_path / 'respostas.txt'
    respostas.write_text('1 A\n2 B\n', encoding='utf-8')
    for nome in ('Ana Teste', 'Bruno Teste'):
        adicionar_arquivo(pasta, respostas, nome)
    chamadas: list[Opcoes] = []
    monkeypatch.setattr(analise, 'analisar', lambda opcoes: chamadas.append(opcoes) or 0)

    await user.open('/')
    await user.should_see(marker='candidato')
    user.find(marker='todos').click()
    user.find(marker='analisar').click()

    await user.should_see('Análise concluída.', retries=60)
    assert chamadas[0].todos is True
