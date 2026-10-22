from pathlib import Path

from concursos.analytics.catalogo_edital import gerar_catalogo
from concursos.analytics.regras_edital import FonteRegra, Metadado, RegrasEdital, StatusExtracao
from concursos.concurso_config import validar_dados


def test_valor_numerico_inteiro_sai_sem_casa_decimal():
    config = validar_dados(
        Path('cpnu'),
        {
            'banca': 'cebraspe',
            'formato': 'multipla_escolha',
            'provas': {'unica': {'gabarito': 'g.txt', 'itens': [1, 90]}},
        },
    )
    corte = Metadado(
        valor=36.0,
        fonte=FonteRegra.DESCOBERTA,
        trecho_origem='inferior a 36 (trinta e seis) acertos',
        documento_origem='edital.pdf',
        pagina_origem=30,
        confianca_extracao=0.6,
        chave='corte_em_acertos_com_nota_ponderada',
        status=StatusExtracao.ENCONTRADO,
    )

    catalogo = gerar_catalogo(config, RegrasEdital(metadados=(corte,)))

    assert '| Corte em acertos ao lado de nota ponderada (descoberta) | 36 |' in catalogo
