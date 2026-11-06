import pandas as pd
import pytest

from concursos.aplicacao import estudo
from concursos.aplicacao.opcoes import Opcoes
from concursos.config.contexto import Contexto, gravar_secao
from concursos.erros import ErroDoUsuario
from concursos.integracoes.open_notebook import OpenNotebookIndisponivelError
from concursos.livros import fila, perguntas
from concursos.llm import ConfiguracaoLlm
from concursos.modelo import EstadoLivro, OndeProcurar

ADM = 'Licitação é o procedimento.\fA licitação é dispensável quando o valor é pequeno.\fContratos.'
PORT = 'A crase ocorre antes de palavra feminina.\fRegência verbal.'


@pytest.fixture
def contexto(tmp_path) -> Contexto:
    return Contexto(
        raiz=tmp_path,
        home=tmp_path / 'home',
        projeto=tmp_path / '.concurso',
        provas=tmp_path / 'provas',
        analises=tmp_path / 'analises',
    )


def lido(contexto, tmp_path, nome, conteudo, disciplina, source_id=''):
    pastas = estudo.biblioteca(contexto)
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding='utf-8')
    livro = fila.adicionar(pastas, caminho, disciplina=disciplina).livro
    fila.ler_livro(pastas.banco, livro.arquivo(pastas), livro.sha)
    if source_id:
        conexao = fila.conectar(pastas)
        fila.atualizar(
            conexao,
            livro.sha,
            source_id=source_id,
            notebook_id=f'notebook:{disciplina}',
            estado=EstadoLivro.PRONTO,
        )
        conexao.close()
    return livro


@pytest.fixture
def livros(contexto, tmp_path):
    return (
        lido(contexto, tmp_path, 'Manual de Adm.txt', ADM, 'Direito Administrativo', 'source:adm'),
        lido(contexto, tmp_path, 'Gramática.txt', PORT, 'Língua Portuguesa', 'source:port'),
    )


class ClienteFalso:
    def __init__(self, resposta='', falhar=False):
        self.resposta = resposta
        self.falhar = falhar
        self.perguntas = []
        self.modelos = []
        self.buscas = []

    def _talvez_falhar(self):
        if self.falhar:
            raise OpenNotebookIndisponivelError('fora do ar')

    def buscar_vetorial(self, consulta, notebook_ids=None, limite=20):
        self._talvez_falhar()
        self.buscas.append(sorted(notebook_ids or []))
        return [{'parent_id': 'source:adm'}]

    def buscar_texto(self, consulta, notebook_ids, limite=20):
        return []

    def listar_modelos(self, tipo=None):
        return list(self.modelos)

    def criar_modelo(self, nome, provedor, tipo, credencial=None):
        modelo = {'id': f'model:{len(self.modelos)}', 'name': nome, 'provider': provedor, 'type': tipo}
        self.modelos.append(modelo)
        return modelo

    def perguntar(self, pergunta, modelo_id):
        self.perguntas.append((pergunta, modelo_id))
        return {'answer': self.resposta}


def com_cliente(monkeypatch, cliente):
    monkeypatch.setattr(estudo, '_cliente_se_preparado', lambda contexto: cliente)


def ligar_ia(contexto, livros=True):
    gravar_secao(
        contexto.config_global,
        'llm',
        {
            'provedor': 'openai',
            'url': 'https://api.openai.com/v1',
            'modelo': 'gpt-4o-mini',
            'consentimento': True,
        },
    )
    if livros:
        estudo.ligar_ia_nos_livros(contexto, True)


def test_sem_ia_todo_trecho_traz_arquivo_e_pagina(contexto, livros):
    resposta = estudo.perguntar(Opcoes(contexto), 'quando a licitação é dispensável?')

    assert resposta.resposta_ia is None
    assert resposta.trechos
    assert all(t.de_livro and t.pagina and t.nome for t in resposta.trechos)
    primeiro = resposta.trechos[0]
    assert (primeiro.nome, primeiro.pagina) == ('Manual de Adm', 2)
    assert '«' in primeiro.texto
    assert primeiro.caminho.exists()


def test_open_notebook_aponta_o_livro_e_o_indice_acha_a_pagina(contexto, livros, monkeypatch):
    cliente = ClienteFalso()
    com_cliente(monkeypatch, cliente)

    resposta = estudo.perguntar(Opcoes(contexto), 'contratar sem licitar')

    assert cliente.buscas == [['notebook:Direito Administrativo', 'notebook:Língua Portuguesa']]
    assert resposta.trechos[0].nome == 'Manual de Adm'
    assert cliente.perguntas == []


def test_com_ia_responde_com_aviso_e_mapeia_as_citacoes(contexto, livros, monkeypatch):
    ligar_ia(contexto)
    cliente = ClienteFalso('A licitação é dispensável quando o valor é pequeno [source:adm].')
    com_cliente(monkeypatch, cliente)

    resposta = estudo.perguntar(Opcoes(contexto), 'quando a licitação é dispensável?')

    assert resposta.resposta_ia == 'A licitação é dispensável quando o valor é pequeno.'
    assert resposta.livros_citados == ('Manual de Adm',)
    assert resposta.trechos[0].nome == 'Manual de Adm'
    assert cliente.modelos == [
        {'id': 'model:0', 'name': 'gpt-4o-mini', 'provider': 'openai_compatible', 'type': 'language'}
    ]
    assert cliente.perguntas == [('quando a licitação é dispensável?', 'model:0')]


def test_sem_consentimento_dos_livros_a_ia_nunca_e_chamada(contexto, livros, monkeypatch):
    ligar_ia(contexto, livros=False)
    cliente = ClienteFalso('não devia')
    com_cliente(monkeypatch, cliente)

    resposta = estudo.perguntar(Opcoes(contexto), 'licitação')

    assert cliente.perguntas == []
    assert resposta.resposta_ia is None


def test_offline_nao_chama_a_ia(contexto, livros, monkeypatch):
    ligar_ia(contexto)
    cliente = ClienteFalso('não devia')
    com_cliente(monkeypatch, cliente)

    estudo.perguntar(Opcoes(contexto, rede=False), 'licitação')

    assert cliente.perguntas == []


def test_open_notebook_fora_avisa_e_busca_no_indice(contexto, livros, monkeypatch):
    com_cliente(monkeypatch, ClienteFalso(falhar=True))

    resposta = estudo.perguntar(Opcoes(contexto), 'crase')

    assert estudo.TEXTO_FORA in resposta.avisos
    assert [(t.nome, t.pagina) for t in resposta.trechos] == [('Gramática', 1)]


def test_filtro_por_disciplina(contexto, livros):
    resposta = estudo.perguntar(Opcoes(contexto), 'licitação crase', disciplina='Língua Portuguesa')

    assert {t.nome for t in resposta.trechos} == {'Gramática'}


def test_minhas_analises_e_tudo(contexto, livros):
    relatorio = contexto.analises / 'relatorio_evolucao.md'
    relatorio.parent.mkdir(parents=True)
    relatorio.write_text(
        '# Tópicos fracos\n\nLicitação: 40% (n=10).\n\n# Outros\n\nNada.\n', encoding='utf-8'
    )

    analises = estudo.perguntar(Opcoes(contexto), 'licitação', onde=OndeProcurar.ANALISES)
    tudo = estudo.perguntar(Opcoes(contexto), 'licitação', onde=OndeProcurar.TUDO)

    assert [(t.nome, t.secao, t.pagina) for t in analises.trechos] == [
        ('relatorio_evolucao.md', 'Tópicos fracos', None)
    ]
    assert {t.de_livro for t in tudo.trechos} == {True, False}


def test_nada_encontrado_e_pergunta_vazia(contexto, livros):
    assert estudo.perguntar(Opcoes(contexto), 'astronomia').avisos == (estudo.TEXTO_NADA,)
    with pytest.raises(ErroDoUsuario, match='vazia'):
        estudo.perguntar(Opcoes(contexto), '   ')


def test_ambiente_da_ia_so_com_consentimento_e_chave(contexto, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-teste')
    assert estudo.ambiente_da_ia(contexto) == {}
    ligar_ia(contexto)

    assert estudo.ambiente_da_ia(contexto) == {
        'OPENAI_COMPATIBLE_BASE_URL_LLM': 'https://api.openai.com/v1',
        'OPENAI_COMPATIBLE_API_KEY_LLM': 'sk-teste',
    }


def test_ambiente_da_anthropic():
    configuracao = ConfiguracaoLlm('anthropic', 'https://api.anthropic.com/v1', 'claude', 'ANTHROPIC_API_KEY')

    assert perguntas.ambiente_da_ia(configuracao, 'k') == {'ANTHROPIC_API_KEY': 'k'}
    assert perguntas.provedor_do_modelo(configuracao) == 'anthropic'


def test_citacoes():
    texto = 'A [source:abc] e B [source:source:def] e A de novo [source:abc].'

    assert perguntas.citacoes(texto) == ['abc', 'def']
    assert perguntas.sem_citacoes(texto) == 'A e B e A de novo.'


def test_sugestoes_pelos_topicos_fracos(contexto, monkeypatch):
    contexto.provas.mkdir()
    fracos = pd.DataFrame(
        {
            'disciplina': ['Direito Administrativo'],
            'topico': ['Licitações e contratos administrativos; dispensa e inexigibilidade'],
            'n': [10],
            'percentual': [0.4],
            'concursos_abaixo': [2],
        }
    )
    monkeypatch.setattr(estudo, 'topicos_fracos', lambda *args: (fracos, []))

    sugestoes = estudo.sugestoes_de_pergunta(contexto)

    assert sugestoes == [
        estudo.Sugestao(
            'Revisar Licitações e contratos administrativos nos seus livros',
            'Licitações e contratos administrativos',
        )
    ]
