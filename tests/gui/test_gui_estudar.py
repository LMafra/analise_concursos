import pytest
from nicegui import ui
from nicegui.testing.user import User

from concursos.aplicacao import estudo
from concursos.aplicacao.estudo import Resposta, ResultadoAdicao, SituacaoEstudo, Sugestao, TrechoEncontrado
from concursos.config.contexto import gravar_secao
from concursos.gui.estado import ESTADO
from concursos.livros.fila import Livro
from concursos.modelo import EstadoLivro, OndeProcurar

PREPARADO = SituacaoEstudo(True, '1.15.1-1', True, False, 'Sua biblioteca está pronta.')
SEM_PACOTE = SituacaoEstudo(True, None, False, False, estudo.TEXTO_PREPARAR.format(mb=360))
SHA = 'a' * 64


def livro(estado: EstadoLivro = EstadoLivro.PRONTO, **campos) -> Livro:
    base = {
        'sha': SHA,
        'nome': 'Direito Constitucional Esquematizado.pdf',
        'extensao': '.pdf',
        'tamanho': 5 * 1024 * 1024,
        'disciplina': 'Direito Constitucional',
        'concursos': (),
        'estado': estado,
        'adicionado_em': '2026-11-06T10:00:00',
    }
    return Livro(**(base | campos))


@pytest.fixture
def biblioteca(monkeypatch):
    """A camada de aplicação falsa: sem leitura em segundo plano nem open-notebook."""
    estado = {'situacao': PREPARADO, 'livros': [], 'chamadas': []}
    monkeypatch.setattr(estudo, 'situacao_do_estudo', lambda contexto: estado['situacao'])
    monkeypatch.setattr(estudo, 'listar_livros', lambda contexto: list(estado['livros']))
    monkeypatch.setattr(estudo, 'iniciar_trabalho', lambda contexto, ao_mudar=None: None)
    monkeypatch.setattr(estudo, 'disciplinas_sugeridas', lambda contexto: ['Geral', 'Direito Constitucional'])
    monkeypatch.setattr(estudo, 'concursos_do_projeto', lambda contexto: ['sefaz-df-2026'])
    monkeypatch.setattr(estudo, 'sugestoes_de_pergunta', lambda contexto: list(estado['sugestoes']))
    estado['sugestoes'] = []
    return estado


async def test_biblioteca_vazia_convida_a_adicionar(user: User, projeto, biblioteca):
    await user.open('/estudar')

    await user.should_see(marker='biblioteca-vazia')
    await user.should_see('Sua biblioteca está vazia')
    await user.should_not_see(marker='estudo-preparar')


async def test_sem_pacote_mostra_o_texto_e_prepara_com_consentimento(
    user: User, projeto, biblioteca, monkeypatch
):
    biblioteca['situacao'] = SEM_PACOTE
    chamadas = []

    def preparar(opcoes, *, consentiu, progresso=None):
        chamadas.append(consentiu)
        biblioteca['situacao'] = PREPARADO
        return '1.15.1-1'

    monkeypatch.setattr(estudo, 'preparar_estudo', preparar)
    await user.open('/estudar')

    await user.should_see('download único de cerca de 360 MB')
    user.find(marker='preparar-estudo').click()
    await user.should_see('Biblioteca pronta')
    assert chamadas == [True]
    await user.should_not_see(marker='estudo-preparar')


async def test_lista_mostra_tamanho_data_e_situacao_com_texto(user: User, projeto, biblioteca):
    biblioteca['livros'] = [
        livro(),
        livro(EstadoLivro.LENDO, sha='b' * 64, nome='Português.epub', pagina=212, paginas=900),
    ]
    await user.open('/estudar')

    await user.should_see('Direito Constitucional Esquematizado.pdf')
    await user.should_see('5,0 MB')
    await user.should_see('Adicionado em 06/11/2026')
    await user.should_see('Pronto para perguntas')
    await user.should_see(marker='livros-preparando')
    await user.should_see('Português.epub: Lendo página 212 de 900 (já dá para buscar nas lidas)')


async def test_adicionar_envia_disciplina_e_concurso_e_avisa_duplicado(
    user: User, projeto, biblioteca, monkeypatch
):
    recebidos = {}

    def adicionar(opcoes, arquivos, *, disciplina=None, concursos=()):
        recebidos.update(nomes=[a.name for a in arquivos], disciplina=disciplina, concursos=concursos)
        biblioteca['livros'] = [livro(EstadoLivro.NA_FILA)]
        return [ResultadoAdicao('novo.pdf', True), ResultadoAdicao('repetido.pdf', False)]

    monkeypatch.setattr(estudo, 'adicionar_livros', adicionar)
    await user.open('/estudar')
    user.find(marker='livro-concurso').elements.pop().value = ['sefaz-df-2026']
    upload = next(iter(user.find(marker='soltar-livros').elements))
    await upload.handle_uploads(
        [
            ui.upload.SmallFileUpload('novo.pdf', 'application/pdf', b'%PDF-1.4'),
            ui.upload.SmallFileUpload('repetido.pdf', 'application/pdf', b'%PDF-1.4'),
        ]
    )

    await user.should_see('Este livro já está na sua biblioteca.')
    await user.should_see('Na fila')
    assert recebidos == {
        'nomes': ['novo.pdf', 'repetido.pdf'],
        'disciplina': 'Geral',
        'concursos': ['sefaz-df-2026'],
    }


async def test_remover_pede_confirmacao(user: User, projeto, biblioteca, monkeypatch):
    biblioteca['livros'] = [livro()]
    removidos = []

    def remover(contexto, sha):
        removidos.append(sha)
        biblioteca['livros'] = []

    monkeypatch.setattr(estudo, 'remover_livro', remover)
    await user.open('/estudar')
    user.find(marker=f'remover-{SHA[:12]}').click()
    await user.should_see(marker='confirmar-remocao')
    user.find(marker='confirmar-remover').click()

    await user.should_see('Sua biblioteca está vazia')
    assert removidos == [SHA]


async def test_fora_do_ar_avisa_que_a_busca_continua(user: User, projeto, biblioteca):
    biblioteca['situacao'] = SituacaoEstudo(True, '1.15.1-1', False, True, estudo.TEXTO_FORA)
    await user.open('/estudar')

    await user.should_see(marker='estudo-fora')
    await user.should_see('A busca continua nos seus livros')


@pytest.fixture
def perguntas(monkeypatch, biblioteca, tmp_path):
    feitas = []
    arquivo = tmp_path / 'manual.pdf'
    arquivo.write_bytes(b'%PDF')

    def perguntar(opcoes, pergunta, *, onde=OndeProcurar.LIVROS, disciplina=None):
        feitas.append((pergunta, onde, disciplina))
        if pergunta == 'astronomia':
            return Resposta([], avisos=(estudo.TEXTO_NADA,))
        trechos = [TrechoEncontrado('Manual de Adm', 'a «licitação» é dispensável', arquivo, pagina=412)]
        if estudo.ia_nos_livros(opcoes.contexto):
            return Resposta(trechos, 'A dispensa ocorre quando o valor é pequeno.', ('Manual de Adm',))
        return Resposta(trechos)

    monkeypatch.setattr(estudo, 'perguntar', perguntar)
    biblioteca['livros'] = [livro()]
    return feitas


async def abrir_perguntar(user: User) -> None:
    await user.open('/estudar')
    user.find(marker='aba-perguntar').click()


async def test_perguntar_mostra_trecho_com_arquivo_e_pagina(user: User, projeto, perguntas):
    await abrir_perguntar(user)
    user.find(marker='campo-pergunta').type('licitação')
    user.find(marker='perguntar').click()

    await user.should_see('Manual de Adm, p. 412')
    await user.should_see('Para uma resposta escrita pela IA, ligue a IA em Configurações.')
    await user.should_not_see(marker='resposta-ia')
    assert perguntas == [('licitação', OndeProcurar.LIVROS, None)]


async def test_filtro_de_onde_e_disciplina(user: User, projeto, perguntas):
    await abrir_perguntar(user)
    user.find(marker='onde-procurar').elements.pop().value = 'tudo'
    user.find(marker='filtro-disciplina').elements.pop().value = 'Direito Constitucional'
    user.find(marker='campo-pergunta').type('licitação')
    user.find(marker='perguntar').click()

    await user.should_see('Manual de Adm, p. 412')
    assert perguntas == [('licitação', OndeProcurar.TUDO, 'Direito Constitucional')]


async def test_sugestao_preenche_e_pergunta(user: User, projeto, perguntas, biblioteca):
    biblioteca['sugestoes'] = [Sugestao('Revisar crase nos seus livros', 'crase')]
    await abrir_perguntar(user)

    await user.should_see('Revisar crase nos seus livros')
    user.find('Revisar crase nos seus livros').click()

    await user.should_see('Manual de Adm, p. 412')
    assert perguntas[-1][0] == 'crase'


async def test_nada_encontrado_oferece_adicionar(user: User, projeto, perguntas):
    await abrir_perguntar(user)
    user.find(marker='campo-pergunta').type('astronomia')
    user.find(marker='perguntar').click()

    await user.should_see('Não achei isso nos seus livros')
    await user.should_see(marker='nada-encontrado')


async def test_ia_pede_consentimento_proprio_e_responde_com_aviso(user: User, projeto, perguntas):
    gravar_secao(ESTADO.contexto().config_global, 'llm', {'provedor': 'openai', 'consentimento': True})
    await abrir_perguntar(user)
    user.find('Respostas escritas pela IA (opcional)').click()
    await user.should_see('trechos dos seus livros vão para openai')
    user.find(marker='ligar-ia-livros').click()
    user.find(marker='campo-pergunta').type('licitação')
    user.find(marker='perguntar').click()

    await user.should_see(marker='resposta-ia')
    await user.should_see('Resposta da IA — confira nos trechos')
    await user.should_see('Livros citados: Manual de Adm')
    await user.should_see('Manual de Adm, p. 412')


async def test_endereco_com_pergunta_abre_e_ja_pergunta(user: User, projeto, perguntas):
    await user.open('/estudar?aba=perguntar&pergunta=licita%C3%A7%C3%A3o')

    await user.should_see('Manual de Adm, p. 412')
    assert perguntas == [('licitação', OndeProcurar.LIVROS, None)]
