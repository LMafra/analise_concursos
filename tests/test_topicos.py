from test_edital import PAGINAS

from concursos.edital import estruturar_edital
from concursos.topicos import sugerir_topicos

EDITAL = estruturar_edital(PAGINAS, 'Analista de TI - Ciência de Dados', 'edital.pdf')


def test_bloco_sobre_nosql_recebe_o_topico_correspondente():
    textos = {
        1: 'Acerca de bancos de dados NoSQL, julgue o item. O MongoDB armazena documentos em um banco NoSQL.',
        2: 'Julgue o item sobre ortografia. A palavra "exceção" está grafada corretamente segundo a ortografia.',
    }

    sugestoes = sugerir_topicos(EDITAL, textos, {})

    assert (sugestoes[1].disciplina, sugestoes[1].topico) == ('Banco de Dados', 'Bancos de dados NoSQL')
    assert sugestoes[1].score > 0.1
    assert (sugestoes[2].disciplina, sugestoes[2].topico) == ('Língua Portuguesa', 'Domínio da ortografia')


def test_disciplina_do_caderno_restringe_os_topicos_candidatos():
    textos = {1: 'Sobre o ciclo de vida, julgue: modelagem relacional de software ágil.'}

    sugestoes = sugerir_topicos(EDITAL, textos, {1: 'Engenharia de Software'})

    assert sugestoes[1].disciplina == 'Engenharia de Software'
    assert sugestoes[1].topico in {'Ciclo de vida do software', 'Metodologias ágeis'}


def test_disciplina_do_caderno_sem_correspondente_exclui_as_ja_casadas():
    textos = {1: 'Compreensão e interpretação de textos sobre modelagem relacional.'}

    sugestoes = sugerir_topicos(EDITAL, textos, {1: 'Tecnologia da Informação', 2: 'Língua Portuguesa'})

    assert sugestoes[1].disciplina == 'Tecnologia da Informação'
    assert sugestoes[1].topico == 'Modelagem relacional'


def test_questao_sem_texto_fica_sem_sugestao():
    sugestoes = sugerir_topicos(EDITAL, {1: ''}, {})

    assert sugestoes[1].topico == 'nao_mapeado'
    assert sugestoes[1].score == 0
