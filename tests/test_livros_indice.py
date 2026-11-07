from concursos.livros import indice


def test_busca_por_radical_sem_acento_com_trecho_e_pagina(tmp_path):
    conexao = indice.abrir(tmp_path / 'b.sqlite')
    indice.indexar_pagina(conexao, 'aaa', 1, 'Introdução ao direito.')
    indice.indexar_pagina(
        conexao, 'aaa', 7, 'Os atos administrativos vinculados não admitem discricionariedade.'
    )
    indice.indexar_pagina(conexao, 'bbb', 2, 'Licitação na modalidade pregão.')

    trechos = indice.buscar(conexao, 'o que é ato administrativo vinculado?')

    assert trechos[0].sha == 'aaa' and trechos[0].pagina == 7
    assert '«' in trechos[0].trecho


def test_filtra_por_livro_e_localiza_trechos(tmp_path):
    conexao = indice.abrir(tmp_path / 'b.sqlite')
    indice.indexar_pagina(conexao, 'aaa', 3, 'pregão eletrônico')
    indice.indexar_pagina(conexao, 'bbb', 4, 'pregão presencial')

    assert [t.sha for t in indice.localizar_trechos(conexao, 'bbb', 'pregão')] == ['bbb']
    assert indice.buscar(conexao, 'pregão', shas=[]) == []


def test_termos_extra_entram_como_frase(tmp_path):
    conexao = indice.abrir(tmp_path / 'b.sqlite')
    indice.indexar_pagina(conexao, 'aaa', 1, 'A Lei 14.133 trata das contratações públicas.')

    assert indice.buscar(conexao, 'nova lei de licitações', termos_extra=['contratações públicas'])
    assert indice.buscar(conexao, 'de que o') == []


def test_remover_e_reabrir_mantem_o_resto(tmp_path):
    banco = tmp_path / 'b.sqlite'
    conexao = indice.abrir(banco)
    indice.indexar_pagina(conexao, 'aaa', 1, 'controle externo')
    indice.indexar_pagina(conexao, 'bbb', 1, 'controle interno')
    indice.remover(conexao, 'aaa')
    conexao.close()

    reaberta = indice.abrir(banco)

    assert [t.sha for t in indice.buscar(reaberta, 'controle')] == ['bbb']
    assert indice.paginas_do_livro(reaberta, 'bbb') == [(1, 'controle interno')]


def test_aspas_e_operadores_da_consulta_nao_quebram_a_busca(tmp_path):
    conexao = indice.abrir(tmp_path / 'b.sqlite')
    indice.indexar_pagina(conexao, 'aaa', 1, 'princípio da legalidade')

    assert indice.buscar(conexao, 'legalidade" OR NEAR(*) AND -')
