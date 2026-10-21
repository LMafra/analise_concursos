import logging
from datetime import date

import pytest
from test_analytics_correcao import DOCUMENTOS_CPNU, concurso, cpnu

from concursos.analytics.correcao import FonteCorrecao, extrair_data_prova, resolver_correcao

CRONOGRAMA_TCU = """Divulgação do edital que informará a
9/2/2026
disponibilização da consulta aos locais de provas
Aplicação das provas objetivas e discursiva 22/2/2026"""

CRONOGRAMA_PF = """Divulgação do edital que informará a
14/7/2025
disponibilização da consulta aos locais de provas
Aplicação da prova objetiva e discursiva 27/7/2025
29 a 31/7/2025
Consulta individual aos gabaritos preliminares da"""

CRONOGRAMA_CPNU = """Obtenção impressa do Cartão de Confirmação de Inscrição para realização da
22/09/2025
prova objetiva no endereço eletrônico https://conhecimento.fgv.br/cpnu2.
Aplicação das provas objetivas. 05/10/2025
Divulgação preliminar dos gabaritos das provas objetivas. 06/10/2025"""

AGSUS = """9. DA PROVA OBJETIVA
9.1 A Prova Objetiva de múltipla escolha, de caráter eliminatório e classificatório, para todos os cargos, será realizada
na cidade de Brasília-DF, no dia 12 de outubro de 2025, das 13h30 às 17h30."""

CPRM = """11.1 Para todas as áreas de conhecimento dos cargos de Pesquisador, Analista e Técnico em
Geociências, a Prova Objetiva e a Prova Discursiva, ambas de caráter eliminatório e
classificatório, serão realizadas no dia 30 de novembro de 2025, no turno da manhã, das 8h às
13h, segundo o horário oficial de Brasília/DF."""

INSCRICOES = """4.1 As inscrições para o Processo Seletivo estarão abertas no período das 16h do dia 28 de julho de 2025
até as 16h do dia 25 de agosto de 2025. 4.21. Na data provável de 31 de julho de 2025, será divulgada a relação."""


@pytest.mark.parametrize(
    ('texto', 'esperada'),
    [
        (CRONOGRAMA_TCU, date(2026, 2, 22)),
        (CRONOGRAMA_PF, date(2025, 7, 27)),
        (CRONOGRAMA_CPNU, date(2025, 10, 5)),
        (AGSUS, date(2025, 10, 12)),
        (CPRM, date(2025, 11, 30)),
    ],
)
def test_data_da_prova_no_cronograma_e_no_texto_corrido(texto, esperada):
    assert extrair_data_prova(['Capa', INSCRICOES, texto]) == esperada


def test_datas_de_inscricao_e_divulgacao_nao_sao_a_data_da_prova():
    assert extrair_data_prova([INSCRICOES, 'Aplicação das provas objetivas em data a definir.']) is None


def test_data_do_edital_vai_para_todas_as_variantes():
    documentos = {**DOCUMENTOS_CPNU, 'cronograma.pdf': [CRONOGRAMA_CPNU]}

    variantes = resolver_correcao(cpnu(), documentos)

    assert {(cfg.data_prova, cfg.fonte_data) for cfg in variantes} == {
        (date(2025, 10, 5), FonteCorrecao.EDITAL)
    }


def test_data_da_configuracao_prevalece_sobre_a_data_provavel_do_edital(caplog):
    config = concurso(data_prova='2026-03-01')

    with caplog.at_level(logging.WARNING):
        [cfg] = resolver_correcao(config, {'edital.pdf': [CRONOGRAMA_TCU]})

    assert (cfg.data_prova, cfg.fonte_data) == (date(2026, 3, 1), FonteCorrecao.CONFIG)
    assert 'data da prova' not in caplog.text


def test_sem_data_em_nenhuma_fonte_o_concurso_fica_sem_data_e_avisa(caplog):
    with caplog.at_level(logging.WARNING):
        [cfg] = resolver_correcao(concurso(), {'edital.pdf': [INSCRICOES]})

    assert (cfg.data_prova, cfg.fonte_data) == (None, None)
    assert 'sintetico: data da prova não encontrada' in caplog.text
