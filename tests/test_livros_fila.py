import contextlib
from concurrent.futures.process import BrokenProcessPool

from livros_sinteticos import pdf

from concursos.livros import fila, indice
from concursos.modelo import EstadoLivro


def texto(tmp_path, nome='livro.txt', conteudo='pregão\fcontrato\fconvênio'):
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding='utf-8')
    return caminho


def test_adicionar_copia_e_poe_na_fila(tmp_path):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')

    adicao = fila.adicionar(
        pastas, texto(tmp_path), disciplina='Direito Administrativo', concursos=['tcu_2025']
    )

    assert adicao.novo
    assert adicao.livro.estado is EstadoLivro.NA_FILA
    assert adicao.livro.arquivo(pastas).read_text(encoding='utf-8').startswith('pregão')
    assert adicao.livro.nome == 'livro'


def test_mesmo_conteudo_atualiza_so_disciplina_e_concursos(tmp_path):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    fila.adicionar(pastas, texto(tmp_path), concursos=['a'])

    adicao = fila.adicionar(pastas, texto(tmp_path, 'copia.txt'), disciplina='Português', concursos=['b'])

    assert not adicao.novo
    assert adicao.livro.disciplina == 'Português'
    assert adicao.livro.concursos == ('a', 'b')
    assert adicao.livro.nome == 'livro'


def test_ler_indexa_pagina_a_pagina_e_retoma(tmp_path):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro = fila.adicionar(pastas, texto(tmp_path)).livro
    conexao = fila.conectar(pastas)
    fila.atualizar(conexao, livro.sha, pagina=1, paginas=3, estado=EstadoLivro.LENDO)
    indice.indexar_pagina(conexao, livro.sha, 1, 'pregão')

    fila.ler_livro(pastas.banco, livro.arquivo(pastas), livro.sha)

    lido = fila.obter(conexao, livro.sha)
    assert lido.estado is EstadoLivro.LIDO and lido.pagina == 3
    assert [p for p, _ in indice.paginas_do_livro(conexao, livro.sha)] == [1, 2, 3]


def test_busca_parcial_enquanto_le(tmp_path):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    arquivo = pdf(tmp_path / 'livro.pdf', ['controle externo do TCU', None])
    livro = fila.adicionar(pastas, arquivo).livro

    def ocr_que_interrompe(caminho, indice_pagina):
        raise RuntimeError('o app fechou')

    with contextlib.suppress(RuntimeError):
        fila.ler_livro(pastas.banco, livro.arquivo(pastas), livro.sha, ocr=ocr_que_interrompe)
    conexao = fila.conectar(pastas)

    assert fila.obter(conexao, livro.sha).pagina == 1
    assert indice.buscar(conexao, 'controle externo')


def test_fila_le_os_pendentes_em_outro_processo(tmp_path):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    fila.adicionar(pastas, texto(tmp_path, 'a.txt', 'um\fdois'))
    fila.adicionar(pastas, texto(tmp_path, 'b.txt', 'três'))
    avisos = []
    trabalho = fila.Fila(pastas, ao_mudar=[lambda: avisos.append(1)])

    try:
        trabalho.processar()
    finally:
        trabalho.encerrar()

    conexao = fila.conectar(pastas)
    assert {livro.estado for livro in fila.listar(conexao)} == {EstadoLivro.LIDO}
    assert len(avisos) == 2


class ExecutorQueQuebra:
    def __init__(self, contagem):
        self.contagem = contagem

    def submit(self, *args):
        self.contagem.append(1)
        raise BrokenProcessPool('caiu')

    def shutdown(self, **kwargs):
        pass


def test_livro_que_derruba_o_processo_vira_erro_e_a_fila_segue(tmp_path, monkeypatch):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro = fila.adicionar(pastas, texto(tmp_path)).livro
    contagem = []
    trabalho = fila.Fila(pastas)
    monkeypatch.setattr(trabalho, '_novo_executor', lambda: ExecutorQueQuebra(contagem))

    trabalho.processar()

    conexao = fila.conectar(pastas)
    assert fila.obter(conexao, livro.sha).estado is EstadoLivro.ERRO
    assert fila.obter(conexao, livro.sha).erro == fila.MENSAGEM_ILEGIVEL
    assert len(contagem) == fila.TENTATIVAS_LEITURA


def test_remover_apaga_catalogo_indice_e_arquivo(tmp_path):
    pastas = fila.PastasBiblioteca(tmp_path / 'bib')
    livro = fila.adicionar(pastas, texto(tmp_path)).livro
    fila.ler_livro(pastas.banco, livro.arquivo(pastas), livro.sha)

    fila.remover(pastas, livro.sha)

    conexao = fila.conectar(pastas)
    assert fila.listar(conexao) == []
    assert indice.buscar(conexao, 'pregão') == []
    assert not livro.arquivo(pastas).exists()
