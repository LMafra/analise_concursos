from pathlib import Path

import pytest

from concursos.analytics.regras_edital import EscopoCorte, FonteRegra, UnidadeCorte, extrair_regras
from concursos.concurso_config import validar_dados

CAPA_TCU = """TRIBUNAL DE CONTAS DA UNIÃO
CONCURSO PÚBLICO PARA O PROVIMENTO DE VAGAS E A FORMAÇÃO DE CADASTRO DE RESERVA PARA
O CARGO DE AUDITOR FEDERAL DE CONTROLE EXTERNO
EDITAL Nº 1 – TCU/AUFC, DE 24 DE OUTUBRO DE 2025
Versão atualizada até a retificação do Edital nº 5 – TCU/AUFC, de 23 de janeiro de 2026.
A Diretora-Geral do Instituto Serzedello Corrêa, do Tribunal de Contas da União, torna pública a realização de
concurso público para o provimento de vagas e a formação de cadastro de reserva para o cargo de
Auditor Federal de Controle Externo – AUFC, mediante as condições estabelecidas neste edital.
"""

CARGOS_PF = """MINISTÉRIO DA JUSTIÇA E SEGURANÇA PÚBLICA (MJSP)
POLÍCIA FEDERAL
CONCURSO PÚBLICO PARA PROVIMENTO DE VAGAS NOS CARGOS DE DELEGADO DE POLÍCIA
FEDERAL, PERITO CRIMINAL FEDERAL, ESCRIVÃO DE POLÍCIA FEDERAL, AGENTE DE POLÍCIA FEDERAL E
PAPILOSCOPISTA POLICIAL FEDERAL
EDITAL Nº 1 – PF – POLICIAL, DE 20 DE MAIO DE 2025
2 DOS CARGOS
CARGO 1: DELEGADO DE POLÍCIA FEDERAL
REQUISITO: diploma, devidamente registrado, de conclusão de curso de bacharelado em Direito.
CARGO 4: PERITO CRIMINAL FEDERAL – ÁREA 3: INFORMÁTICA FORENSE
REQUISITO: diploma, devidamente registrado, de conclusão de curso de graduação em Ciências da Computação.
CARGO 16: AGENTE DE POLÍCIA FEDERAL
"""

CAPA_AGSUS = """AGÊNCIA BRASILEIRA DE APOIO À GESTÃO DO SUS
SHN - Quadra 1, Bloco E, Conj A, 2º andar - Brasília/DF, CEP 70701-050
EDITAL PSS/AgSUS DE 24 DE JULHO DE 2025
ABERTURA DO PROCESSO SELETIVO SIMPLIFICADO
A AGÊNCIA BRASILEIRA DE APOIO À GESTÃO DO SUS - AgSUS, no uso de suas atribuições, torna pública as normas e
inscrições relativas à realização do processo seletivo simplificado destinado ao preenchimento de
106 (cento e seis) vagas para o cargo de Analista de Gestão e 24 (vinte e quatro) vagas para o cargo de
Auxiliar de Gestão, e formação de cadastro de reserva, para contratação dos profissionais, nos termos deste Edital.
"""


CORTES_CD = """8.11.4 Será reprovado nas provas objetivas e eliminado do concurso público o candidato que
se enquadrar em pelo menos um dos itens a seguir:
a) obtiver nota inferior a 18,00 pontos na prova objetiva de conhecimentos gerais P ;
1
b) obtiver nota inferior a 27,00 pontos na prova objetiva de conhecimentos específicos P ;
2
c) obtiver nota inferior a 54,00 pontos no conjunto das provas objetivas.
9.7.8 Será aprovado nas provas discursivas o candidato que obtiver NPD ≥ 30,00 pontos.
"""

CORTES_PF = """8.11.4 Será reprovado na prova objetiva e eliminado do concurso público o candidato ao cargo de
Delegado de Polícia Federal que obtiver nota inferior a 50,00 pontos na prova objetiva P .
1
8.11.5 Será reprovado na prova objetiva e eliminado do concurso público o candidato ao cargo de Perito
Criminal Federal que se enquadrar em pelo menos um dos itens a seguir:
a) obtiver nota inferior a 10,00 pontos nos itens de conhecimentos básicos da prova objetiva P ;
1
b) obtiver nota inferior a 21,00 pontos nos itens de conhecimentos específicos da prova objetiva P ;
1
c) obtiver nota inferior a 48,00 pontos na prova objetiva P .
1
8.11.6 Será reprovado na prova objetiva e eliminado do concurso público o candidato aos cargos de
Escrivão de Polícia Federal, Agente de Polícia Federal e Papiloscopista Policial Federal que se enquadrar
em pelo menos um dos itens a seguir:
a) obtiver nota inferior a 6,00 pontos no bloco I da prova objetiva P ;
1
c) obtiver nota inferior a 40,00 pontos no conjunto dos três blocos da prova objetiva P .
1
9.9.8 Será aprovado na prova discursiva o candidato ao cargo de Delegado de Polícia Federal que obtiver
NFPD igual ou superior a 12,00 pontos.
9.9.10 Será aprovado na prova discursiva o candidato aos cargos de Perito Criminal Federal, Escrivão de
Polícia Federal, Agente de Polícia Federal e Papiloscopista Policial Federal que obtiver nota final na prova
discursiva (NFPD) igual ou superior a 10,00 pontos.
"""

CORTES_AGSUS = """9.14 Será considerado aprovado na Prova Objetiva, o candidato que, cumulativamente:
a) acertar, no mínimo, em Conhecimentos Gerais, 20 questões;
b) acertar, no mínimo, em Conhecimentos Específicos, 15 questões; e
c) não zerar nenhuma das disciplinas.
9.14.1 O candidato que não atender aos requisitos dos subitens 9.14 será eliminado do Processo Seletivo.
"""

CORTES_CPRM = """12.13 Para os Cargos de Pesquisador, Analista e Técnico em Geociências será considerado
aprovado na Prova Objetiva, o candidato que obtiver, cumulativamente:
12.13.1 Acertar 15 (quinze) questões do Módulo I (Conhecimentos Gerais);
12.13.2 Acertar ao menos 1 (uma) questão em cada disciplina que compõe o Módulo I
(Conhecimentos Gerais) e
12.13.3 Acertar 20 (vinte) questões do Módulo II (Conhecimentos Específicos).
13.1 Para todas as áreas de conhecimento do cargo de Pesquisador em Geociências, a Prova
Discursiva será composta por 1 (uma) questão dissertativa.
13.1.1 Será considerado aprovado na prova discursiva o candidato que obtiver nota final
igual ou superior a 14 (catorze) pontos.
13.2 Para todas as áreas de conhecimento do cargo de Analista em Geociências, a Prova Discursiva
será composta por 1 (uma) redação a ser respondida em, no máximo, 30 (trinta) linhas.
13.2.1 Será considerado aprovado na prova discursiva o candidato que obtiver nota final
igual ou superior a 12 (doze) pontos.
"""

CORTES_CPNU = """8.15. Será eliminada, e não constará na classificação final do certame, a pessoa candidata
que obtiver aproveitamento inferior a 36 (trinta e seis) acertos nas provas objetivas de Conhecimentos Gerais e de
Conhecimentos Específicos para os cargos de Nível Superior; e 28 (vinte e oito) acertos nas provas
objetivas de Conhecimentos Gerais e de Conhecimentos Específicos para os cargos de Nível Intermediário.
"""


def regua(regras) -> list[tuple]:
    return [(c.escopo, c.valor, c.unidade, c.bloco) for c in regras.cortes]


def config(cargo: str | None = None, **extra):
    dados = {
        'banca': 'cebraspe',
        'formato': 'certo_errado',
        'provas': {'unica': {'gabarito': 'g.txt', 'itens': [1, 10]}},
        **({'cargo': cargo} if cargo else {}),
        **extra,
    }
    return validar_dados(Path('sintetico'), dados)


def test_edital_de_um_so_cargo_tira_o_cargo_do_edital_sem_cargo_na_configuracao():
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU]})

    identificacao = regras.identificacao
    assert identificacao.cargo.valor == 'Auditor Federal de Controle Externo'
    assert identificacao.cargo_casado
    assert identificacao.nome_oficial.valor == 'Tribunal de Contas da União'
    assert identificacao.edital.valor == 'EDITAL Nº 1 – TCU/AUFC, DE 24 DE OUTUBRO DE 2025'
    assert identificacao.cadastro_reserva.valor is True


def test_edital_de_varios_cargos_casa_o_cargo_da_configuracao_e_separa_a_especialidade():
    cargo = 'CARGO 4: PERITO CRIMINAL FEDERAL – ÁREA 3: INFORMÁTICA FORENSE'
    regras = extrair_regras(config(cargo), {'edital.pdf': [CARGOS_PF, 'ANEXO I']})

    identificacao = regras.identificacao
    assert (identificacao.cargo.valor, identificacao.especialidade.valor) == (
        'Perito Criminal Federal',
        'Informática Forense',
    )
    assert identificacao.cargo_casado
    assert identificacao.cargo.fonte is FonteRegra.EDITAL
    assert identificacao.cargo.documento_origem == 'edital.pdf'
    assert identificacao.cargo.pagina_origem == 1
    assert 'CARGO 4: PERITO CRIMINAL FEDERAL' in identificacao.cargo.trecho_origem
    assert identificacao.nome_oficial.valor == 'Ministério da Justiça e Segurança Pública (MJSP)'


def test_fgv_casa_o_cargo_pelo_nome_e_le_as_vagas_so_do_cargo():
    regras = extrair_regras(
        config('Analista de Gestão Tecnologia da Informação'), {'edital.pdf': [CAPA_AGSUS]}
    )

    identificacao = regras.identificacao
    assert identificacao.cargo.valor == 'Analista de Gestão'
    assert identificacao.especialidade.valor == 'Tecnologia da Informação'
    assert identificacao.vagas.valor == 106
    assert '106 (cento e seis)' in identificacao.vagas.trecho_origem
    assert identificacao.nome_oficial.valor == 'Agência Brasileira de Apoio à Gestão do SUS'


def test_edital_de_dois_cargos_le_so_o_trecho_do_cargo_da_configuracao():
    classificacao = (
        'Serão convocados para a avaliação de títulos os candidatos ao cargo de Delegado de Polícia Federal '
        'classificados até a posição 300; para os demais, os 120 candidatos mais bem classificados. '
        + 'Texto neutro sobre a forma de entrega dos documentos e a validade do concurso. '
        * 12
        + 'Os candidatos ao cargo de Perito Criminal Federal – Área 3 serão convocados quando '
        'estiverem entre os 45 candidatos mais bem classificados na prova objetiva.'
    )
    regras = extrair_regras(
        config('CARGO 4: PERITO CRIMINAL FEDERAL – ÁREA 3: INFORMÁTICA FORENSE'),
        {'edital.pdf': [CARGOS_PF, classificacao]},
    )

    teto = regras.identificacao.teto_classificados
    assert teto.valor == 45
    assert teto.pagina_origem == 2


def test_cargo_sem_casamento_fica_marcado_e_gera_aviso():
    regras = extrair_regras(config('CARGO 9: ESCRIVÃO'), {'edital.pdf': [CARGOS_PF]})

    assert not regras.identificacao.cargo_casado
    assert regras.identificacao.cargo.valor is None
    assert any('não casa com nenhum cargo do edital' in aviso for aviso in regras.avisos)


PONTOS, ACERTOS = UnidadeCorte.PONTOS, UnidadeCorte.ACERTOS


def test_cebraspe_tem_cortes_em_pontos_por_bloco_e_no_conjunto_e_o_da_discursiva():
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU, CORTES_CD]})

    assert regua(regras) == [
        (EscopoCorte.GERAL, 18.0, PONTOS, None),
        (EscopoCorte.ESPECIFICO, 27.0, PONTOS, None),
        (EscopoCorte.CONJUNTO, 54.0, PONTOS, None),
        (EscopoCorte.DISCURSIVA, 30.0, PONTOS, None),
    ]
    for corte in regras.cortes:
        assert corte.fonte is FonteRegra.EDITAL
        assert corte.documento_origem == 'edital.pdf'
        assert corte.pagina_origem == 2
        assert corte.trecho_origem
        assert 0 < corte.confianca_extracao <= 1
    assert 'conhecimentos gerais' in regras.cortes[0].trecho_origem


def test_dois_cargos_com_cortes_diferentes_saem_os_do_cargo_da_configuracao():
    cargo = 'CARGO 4: PERITO CRIMINAL FEDERAL – ÁREA 3: INFORMÁTICA FORENSE'
    regras = extrair_regras(config(cargo), {'edital.pdf': [CARGOS_PF, CORTES_PF]})

    assert regua(regras) == [
        (EscopoCorte.GERAL, 10.0, PONTOS, None),
        (EscopoCorte.ESPECIFICO, 21.0, PONTOS, None),
        (EscopoCorte.CONJUNTO, 48.0, PONTOS, None),
        (EscopoCorte.DISCURSIVA, 10.0, PONTOS, None),
    ]


def test_fgv_tem_cortes_em_acertos_por_bloco_e_nao_zerar_disciplina():
    regras = extrair_regras(
        config('Analista de Gestão Tecnologia da Informação'), {'edital.pdf': [CAPA_AGSUS, CORTES_AGSUS]}
    )

    assert regua(regras) == [
        (EscopoCorte.GERAL, 20.0, ACERTOS, None),
        (EscopoCorte.ESPECIFICO, 15.0, ACERTOS, None),
        (EscopoCorte.DISCIPLINA, 1.0, ACERTOS, None),
    ]
    assert 'não zerar' in regras.cortes[2].trecho_origem


def test_cprm_tem_minimo_por_disciplina_do_modulo_i_e_a_discursiva_do_cargo():
    regras = extrair_regras(
        config('Analista em Geociências - Análise e Desenvolvimento de Sistemas'),
        {'edital.pdf': [CORTES_CPRM]},
    )

    assert regua(regras) == [
        (EscopoCorte.GERAL, 15.0, ACERTOS, None),
        (EscopoCorte.DISCIPLINA, 1.0, ACERTOS, EscopoCorte.GERAL),
        (EscopoCorte.ESPECIFICO, 20.0, ACERTOS, None),
        (EscopoCorte.DISCURSIVA, 12.0, PONTOS, None),
    ]


@pytest.mark.parametrize(('escolaridade', 'corte'), [('superior', 36.0), ('medio', 28.0)])
def test_cpnu_tem_corte_em_acertos_no_conjunto_pelo_nivel_do_cargo(escolaridade, corte):
    regras = extrair_regras(config(escolaridade=escolaridade), {'edital.pdf': [CORTES_CPNU]})

    assert regua(regras) == [(EscopoCorte.CONJUNTO, corte, ACERTOS, None)]


def test_sem_corte_no_edital_vale_o_da_configuracao():
    regras = extrair_regras(config(correcao={'nota_corte': 40}), {'edital.pdf': [CAPA_TCU]})

    [corte] = regras.cortes
    assert (corte.escopo, corte.valor, corte.unidade, corte.fonte) == (
        EscopoCorte.CONJUNTO,
        40.0,
        PONTOS,
        FonteRegra.CONFIG,
    )
    assert corte.trecho_origem is None


def test_corte_no_default_com_palavra_gatilho_no_edital_gera_aviso():
    texto = 'O candidato precisa atingir a nota mínima definida pela comissão.'
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU, texto]})

    assert regras.cortes == ()
    assert any('nota de corte' in aviso and 'nota mínima' in aviso for aviso in regras.avisos)
