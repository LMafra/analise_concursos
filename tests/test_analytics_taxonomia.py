import pytest
import yaml

from concursos.analytics.taxonomia import (
    DisciplinaCanonica,
    TaxonomiaInvalidaError,
    carregar_taxonomia,
    chave_topico,
)
from concursos.modelo import Bloco


def gravar(tmp_path, dados):
    caminho = tmp_path / 'taxonomia.yaml'
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding='utf-8')
    return caminho


def test_cada_nome_bruto_e_o_proprio_nome_canonico_apontam_para_a_disciplina(tmp_path):
    caminho = gravar(
        tmp_path,
        {
            'Raciocínio Lógico': {
                'bloco': 'geral',
                'nomes': ['Raciocínio Lógico Matemático', 'Raciocínio Análitico'],
            },
            'Banco de Dados': {'bloco': 'especifico', 'nomes': ['Bancos de Dados']},
        },
    )

    taxonomia = carregar_taxonomia(caminho)

    logico = DisciplinaCanonica('Raciocínio Lógico', Bloco.GERAL)
    assert taxonomia['Raciocínio Lógico Matemático'] == logico
    assert taxonomia['Raciocínio Análitico'] == logico
    assert taxonomia['Raciocínio Lógico'] == logico
    assert taxonomia['Bancos de Dados'] == DisciplinaCanonica('Banco de Dados', Bloco.ESPECIFICO)


def test_disciplina_sem_lista_de_nomes_mapeia_so_o_proprio_nome(tmp_path):
    taxonomia = carregar_taxonomia(gravar(tmp_path, {'Atualidades': {'bloco': 'geral'}}))

    assert taxonomia == {'Atualidades': DisciplinaCanonica('Atualidades', Bloco.GERAL)}


@pytest.mark.parametrize(
    ('dados', 'mensagem'),
    [
        ({'Atualidades': {'bloco': 'basico'}}, "Atualidades: bloco 'basico' inválido"),
        ({'Atualidades': {}}, "Atualidades: bloco '' inválido"),
        (
            {'Informática': {'bloco': 'geral'}, 'TI': {'bloco': 'especifico', 'nomes': ['Informática']}},
            "nome 'Informática' mapeado em mais de uma disciplina",
        ),
        (['Atualidades'], 'esperado um mapa de disciplina canônica'),
    ],
)
def test_taxonomia_invalida_aponta_o_problema(tmp_path, dados, mensagem):
    with pytest.raises(TaxonomiaInvalidaError, match=mensagem):
        carregar_taxonomia(gravar(tmp_path, dados))


def test_taxonomia_ausente_e_vazia(tmp_path):
    assert carregar_taxonomia(tmp_path / 'taxonomia.yaml') == {}


def test_chave_de_topico_ignora_acento_caixa_e_palavras_vazias():
    chave = chave_topico('Língua Portuguesa', 'Emprego do sinal indicativo de crase')

    assert chave == chave_topico('Língua Portuguesa', 'EMPREGO DO SINAL INDICATIVO DA CRASE')
    assert chave == chave_topico('Língua Portuguesa', 'emprego sinal indicativo, crase')
    assert chave != chave_topico('Direito Administrativo', 'Emprego do sinal indicativo de crase')
    assert chave_topico('Ética', 'Concordância Verbal') == chave_topico('Ética', 'concordancia verbal')


def test_muitas_disciplinas_fora_da_lista_viram_contagem_com_exemplos(caplog):
    import logging

    import pandas as pd

    from concursos.analytics.taxonomia import classificar

    disciplinas = ['Arquivologia', 'Biologia', 'Contabilidade', 'Direito', 'Economia']
    questoes = pd.DataFrame({'disciplina': disciplinas, 'prova': ['unica'] * 5, 'topico': ['t'] * 5})

    with caplog.at_level(logging.WARNING):
        classificar(questoes, {})

    [registro] = caplog.records
    assert registro.getMessage().startswith('5 disciplinas estão fora da lista de disciplinas equivalentes')
    assert 'Arquivologia, Biologia e Contabilidade' in registro.getMessage()
    assert 'Economia' not in registro.getMessage()
    assert 'Economia' in registro.detalhe
