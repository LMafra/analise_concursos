from datetime import date
from pathlib import Path

import pytest
from test_analytics_correcao import AGSUS, CEBRASPE, DATAPREV, DOCUMENTOS_CPNU, cpnu, pesos_cpnu

from concursos.analytics.candidatos_edital import CANDIDATOS
from concursos.analytics.regras_edital import (
    EscopoCorte,
    FonteRegra,
    StatusExtracao,
    TipoPeso,
    UnidadeCorte,
    extrair_regras,
)
from concursos.concurso_config import PesoItens, validar_dados

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
Auxiliar de Gestão, e formação de cadastro de reserva, para contratação dos profissionais, nos termos
deste Edital.
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
que obtiver aproveitamento inferior a 36 (trinta e seis) acertos nas provas objetivas de Conhecimentos
Gerais e de Conhecimentos Específicos para os cargos de Nível Superior; e 28 (vinte e oito) acertos nas provas
objetivas de Conhecimentos Gerais e de Conhecimentos Específicos para os cargos de Nível Intermediário.
"""


QUADRO_CD = """7.1 Será aplicado exame de habilidades e conhecimentos, mediante aplicação de provas objetivas e de
prova discursiva, de caráter eliminatório e classificatório, conforme o quadro a seguir:
PROVA/TIPO ÁREA DE CONHECIMENTO NÚMERO DE ITENS CARÁTER
Prova objetiva (P ) Conhecimentos gerais 90
1PROVA/TIPO ÁREA DE CONHECIMENTO NÚMERO DE ITENS CARÁTER
Prova objetiva (P ) Conhecimentos específicos 90 Eliminatório e
2
Prova discursiva (P ) – – classificatório
3
7.2 As provas objetivas terão a duração de 5 horas.
8.11.2 A nota em cada item será igual a: 1,00 ponto, caso a resposta do candidato esteja em concordância com
o gabarito oficial definitivo; os itens serão julgados CERTO ou ERRADO.
"""

QUADRO_TCU = """7.1 As etapas do concurso estão descritas no quadro a seguir:
ÁREA DE NÚMERO DE
ETAPA PROVA/TIPO CARÁTER
CONHECIMENTO ITENS
Conhecimentos
(P ) Objetiva 100
1
básicos
Conhecimentos
(P ) Objetiva 100
2
específicos Eliminatório e
Primeira etapa
três questões classificatório
–
discursivas
(P ) Discursiva
3
7.2 As provas objetivas terão a duração de 4 horas.
"""

QUADRO_PF = """7.1 A primeira etapa do concurso está descrita nos quadros a seguir.
7.1.1 PARA O CARGO DE DELEGADO DE POLÍCIA FEDERAL
NÚMERO DE
PROVA/TIPO ÁREA DE CONHECIMENTO CARÁTER
ITENS
(P ) Objetiva Conhecimentos específicos 120
1
7.1.2 PARA OS CARGOS DE PERITO CRIMINAL FEDERAL
NÚMERO DE
PROVA/TIPO ÁREA DE CONHECIMENTO CARÁTER
ITENS
Conhecimentos básicos 50
(P ) Objetiva
1
Conhecimentos específicos 70
7.1.3 PARA OS CARGOS DE ESCRIVÃO DE POLÍCIA FEDERAL, AGENTE DE POLÍCIA FEDERAL E DE
PAPILOSCOPISTA POLICIAL FEDERALNÚMERO DE
PROVA/TIPO ÁREA DE CONHECIMENTO CARÁTER
ITENS
Conhecimentos básicos – Bloco I 60
(P ) Objetiva Conhecimentos básicos – Bloco II 36
1
Conhecimentos específicos – Bloco III 24 Eliminatório e
7.2 A prova objetiva terá a duração de 4 horas.
"""

QUADROS_AGSUS = """9.5 A Prova Objetiva totalizará 70 (setenta) pontos e será composta por 70 (setenta) questões de
múltipla escolha, valendo 1 (um) ponto cada questão. As questões serão numeradas sequencialmente, contendo
5 (cinco) alternativas cada e apenas uma resposta correta.
9.5.1 A Prova Objetiva será composta por 40 (quarenta) questões de Conhecimentos Gerais e 30 (trinta)
questões de Conhecimentos Específicos, para todos os cargos, e será aplicada da seguinte forma:
9.5.1.1 Para o cargo de Analista de Gestão – AgSUS / Administrativo:
CARGO: ANALISTA DE GESTÃO – AgSUS / ADMINISTRATIVO
CONHECIMENTOS DISCIPLINAS TOTAL DE QUESTÕES PONTUAÇÃO
MÁXIMA
Língua Portuguesa 15 15
GERAIS Raciocínio Lógico e Matemático 10 10
Legislação 05 05
Noções de Informática 10 10
ESPECÍFICOS Conforme conteúdo programático de cada 30 30
cargo/especialidade, constante no Anexo I
Total: 70 70
9.5.1.2 Para os cargos de Analista de Gestão – AgSUS / Demais Especialidades:
CARGO: ANALISTA DE GESTÃO – AgSUS / DEMAIS ESPECIALIDADES
CONHECIMENTOS DISCIPLINAS TOTAL DE QUESTÕES PONTUAÇÃOMÁXIMA
Língua Portuguesa 15 15
GERAIS Raciocínio Lógico e Matemático 05 05
Legislação 10 10
Noções de Informática 10 10
ESPECÍFICOS Conforme conteúdo programático de cada 30 30
cargo/especialidade, constante no Anexo I
Total: 70 70
9.5.1.3 Para o cargo de Auxiliar de Gestão – AgSUS:
CARGO: AUXILIAR DE GESTÃO - AgSUS
CONHECIMENTOS DISCIPLINAS TOTAL DE QUESTÕES PONTUAÇÃO
MÁXIMA
Língua Portuguesa 15 15
GERAIS Raciocínio Lógico e Matemático 10 10
Legislação 05 05
Noções de Informática 10 10
ESPECÍFICOS Conforme conteúdo programático de cada 30 30
cargo/especialidade, constante no Anexo I
Total: 70 70
9.6 A Prova Objetiva não admite consulta de qualquer natureza.
"""

QUADROS_CPRM = """12.1 Para todas as áreas de conhecimento dos cargos de Pesquisador, Analista e Técnico em
Geociências, a Prova Objetiva será composta por 70 (setenta) questões de múltipla escolha,
numeradas sequencialmente, com 5 (cinco) alternativas e apenas 1 (uma) resposta correta, com
os Módulos I (Conhecimentos Gerais) com 30 (trinta) questões e Módulo II (Conhecimentos
Específicos) com 40 (quarenta) questões.
12.3 Para todas as áreas de conhecimento do Cargo de Analista em Geociências, o Módulo I
(Conhecimentos Gerais) será comum a todas.
12.3.1 Analista em Geociências – Área: Administração. O quadro a seguir apresenta as
disciplinas:
Nº
Prova Objetiva Disciplina
Questões
Língua Portuguesa 10
Módulo I: Conhecimentos Gerais Raciocínio Lógico Matemático 10
Atualidades 10
Módulo II: Conhecimentos Específicos Administração 40
Total 70
12.3.2 Analista em Geociências – Área: Análise e Desenvolvimento de Sistemas. O quadro
a seguir apresenta as disciplinas:
Nº
Prova Objetiva Disciplina
Questões
Língua Portuguesa 12
Módulo I: Conhecimentos Gerais Raciocínio Lógico Matemático 8
Atualidades 10
Módulo II: Conhecimentos Específicos Análise e Desenvolvimento de 40
Sistemas
Total 70
"""


def distribuicao(regras) -> tuple:
    d = regras.distribuicao
    return d.total.valor, d.geral.valor, d.especifico.valor, d.por_disciplina.valor


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


def test_nota_inline_de_retificacao_marca_a_fonte_do_subitem_retificado():
    retificado = CORTES_CD.replace(
        'conjunto das provas objetivas.',
        'conjunto das provas objetivas.\n(Retificado por meio do Edital nº 2 – TCU/AUFC, de 29 de outubro '
        'de 2025, divulgado no endereço eletrônico http://www.cebraspe.org.br/concursos/tcu_25_aufc)',
    )
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU, retificado]})

    fontes = {corte.escopo: corte.fonte for corte in regras.cortes}
    assert fontes[EscopoCorte.CONJUNTO] is FonteRegra.RETIFICACAO
    assert fontes[EscopoCorte.GERAL] is FonteRegra.RETIFICACAO
    assert fontes[EscopoCorte.DISCURSIVA] is FonteRegra.EDITAL
    conjunto = next(c for c in regras.cortes if c.escopo is EscopoCorte.CONJUNTO)
    assert conjunto.documento_origem == 'edital.pdf'


def test_cebraspe_distribui_so_por_prova_e_deixa_a_disciplina_vazia_sem_aviso():
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU, QUADRO_CD]})

    assert distribuicao(regras) == (180, 90, 90, None)
    d = regras.distribuicao
    assert d.por_disciplina.fonte is FonteRegra.DEFAULT
    assert (d.geral.fonte, d.geral.documento_origem, d.geral.pagina_origem) == (
        FonteRegra.EDITAL,
        'edital.pdf',
        2,
    )
    assert 'Conhecimentos gerais 90' in d.geral.trecho_origem
    assert d.por_tipo.valor == {'certo_errado': 180}
    assert not any('distribui' in aviso for aviso in regras.avisos)


def test_tcu_le_as_provas_objetivas_na_ordem_do_quadro_e_as_questoes_discursivas():
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU, QUADRO_TCU]})

    assert distribuicao(regras) == (200, 100, 100, None)
    assert regras.distribuicao.por_tipo.valor == {'discursiva': 3}


def test_quadro_de_provas_do_cargo_da_configuracao_num_edital_de_varios_cargos():
    cargo = 'CARGO 4: PERITO CRIMINAL FEDERAL – ÁREA 3: INFORMÁTICA FORENSE'
    regras = extrair_regras(config(cargo), {'edital.pdf': [CARGOS_PF, QUADRO_PF]})

    assert distribuicao(regras) == (120, 50, 70, None)


def test_fgv_distribui_por_disciplina_pelo_quadro_do_cargo():
    regras = extrair_regras(
        config('Analista de Gestão Tecnologia da Informação'), {'edital.pdf': [CAPA_AGSUS, QUADROS_AGSUS]}
    )

    assert distribuicao(regras) == (
        70,
        40,
        30,
        {
            'Língua Portuguesa': 15,
            'Raciocínio Lógico e Matemático': 5,
            'Legislação': 10,
            'Noções de Informática': 10,
        },
    )
    por_disciplina = regras.distribuicao.por_disciplina
    assert por_disciplina.fonte is FonteRegra.EDITAL
    assert 'DEMAIS ESPECIALIDADES' in por_disciplina.trecho_origem
    assert regras.distribuicao.por_tipo.valor == {'multipla_escolha': 70}


def test_cprm_distribui_por_modulo_e_pelo_quadro_da_area_do_cargo():
    regras = extrair_regras(
        config('Analista em Geociências - Análise e Desenvolvimento de Sistemas'),
        {'edital.pdf': [QUADROS_CPRM]},
    )

    assert distribuicao(regras) == (
        70,
        30,
        40,
        {'Língua Portuguesa': 12, 'Raciocínio Lógico Matemático': 8, 'Atualidades': 10},
    )


def test_corte_no_default_com_palavra_gatilho_no_edital_gera_aviso():
    texto = 'O candidato precisa atingir a nota mínima definida pela comissão.'
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU, texto]})

    assert regras.cortes == ()
    assert any('nota de corte' in aviso and 'nota mínima' in aviso for aviso in regras.avisos)


def test_cpnu_tem_pesos_por_faixa_de_itens_por_variante_e_a_soma_declarada_dos_eixos():
    regras = extrair_regras(cpnu(), DOCUMENTOS_CPNU)

    pesos = regras.pesos
    assert pesos.tipo.valor is TipoPeso.POR_FAIXA_DE_ITENS
    assert {variante: campo.valor for variante, campo in pesos.faixas.items()} == {
        'B3-08-A': pesos_cpnu(1, 1, 2, 4, 2),
        'B3-10-A': pesos_cpnu(1, 2, 3, 3, 1),
        'B3-07-C': pesos_cpnu(1, 2, 1, 4, 2),
    }
    inss = pesos.faixas['B3-08-A']
    assert (inss.fonte, inss.documento_origem, inss.pagina_origem) == (
        FonteRegra.EDITAL,
        'anexo_bloco3.pdf',
        3,
    )
    assert inss.trecho_origem.startswith('B3-08-A')
    assert pesos.soma_dos_eixos.valor == 10
    assert 'totalizando, em conjunto, o valor de 10' in pesos.soma_dos_eixos.trecho_origem


def test_cebraspe_tem_peso_uniforme():
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU, CEBRASPE]})

    pesos = regras.pesos
    assert (pesos.tipo.valor, pesos.tipo.fonte, pesos.tipo.pagina_origem) == (
        TipoPeso.UNIFORME,
        FonteRegra.EDITAL,
        2,
    )
    assert pesos.tipo.trecho_origem.startswith('8.11.2')
    assert pesos.faixas == {}
    assert pesos.soma_dos_eixos.valor is None


def test_pontos_diferentes_por_modulo_sao_peso_por_bloco():
    regras = extrair_regras(
        validar_dados(
            Path('sintetico'),
            {
                'banca': 'fgv',
                'formato': 'multipla_escolha',
                'provas': {'unica': {'gabarito': 'g', 'itens': [1, 70]}},
            },
        ),
        {'edital.pdf': [DATAPREV]},
    )

    assert regras.pesos.tipo.valor is TipoPeso.POR_BLOCO
    assert regras.pesos.faixas[''].valor == (PesoItens(1, 40, 1.0), PesoItens(41, 70, 2.5))


CRONOGRAMA_CD = """ANEXO I
CRONOGRAMA PREVISTO
Atividade Datas previstas
Divulgação do edital que informará a
23/2/2026
disponibilização da consulta aos locais de provas
Aplicação das provas objetivas e discursiva 8/3/2026
10 a 12/3/2026
Consulta individual aos gabaritos oficiais
Das 19 horas do primeiro dia às 18 horas do último
preliminares das provas objetivas
dia (horário oficial de Brasília/DF)
Prazo para a interposição de recursos quanto às
11 e 12/3/2026
questões formuladas, aos gabaritos oficiais
Das 10 horas do primeiro dia às 18 horas do último
preliminares divulgados e(ou) ao padrão de
dia (horário oficial de Brasília/DF)
respostas da prova discursiva
Divulgação dos gabaritos oficiais preliminares das
13/3/2026
provas objetivasDivulgação do edital de resultado final nas provas
objetivas e de resultado provisório no procedimento 8/4/2026
de caracterização da deficiência (etapa documental)
"""

CRONOGRAMA_CPNU = """ANEXO X
CRONOGRAMA
EVENTOS BÁSICOS - CONCURSO PÚBLICO NACIONAL UNIFICADO 2 DATAS
Aplicação das provas objetivas. 05/10/2025
Divulgação preliminar dos gabaritos das provas objetivas. 06/10/2025
Prazo para interposição de eventuais recursos quanto às questões formuladas
07/10 e 08/10/2025
e/ou aos gabaritos divulgados.
Divulgação das notas finais das Provas Objetivas.
12/11/2025
Aplicação da Prova Discursiva. 07/12/2025
"""

PROVAS_CPRM = """11.1 Para todas as áreas de conhecimento dos cargos de Pesquisador, Analista e Técnico em
Geociências, a Prova Objetiva e a Prova Discursiva, ambas de caráter eliminatório e classificatório, serão
realizadas no dia 30 de novembro de 2025, no turno da manhã, das 8h às 13h.
"""

PROVA_AGSUS = """9.1 A Prova Objetiva de múltipla escolha, de caráter eliminatório e classificatório, para todos os
cargos, será realizada na cidade de Brasília-DF, no dia 12 de outubro de 2025, das 13h30 às 17h30.
"""


def datas(regras) -> tuple:
    c = regras.cronograma
    return (
        c.objetiva.valor,
        c.discursiva.valor,
        c.discursiva_no_mesmo_dia,
        c.resultado_final.valor,
        c.recurso.valor,
    )


def test_anexo_i_do_cebraspe_tem_objetiva_e_discursiva_no_mesmo_dia():
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU, CRONOGRAMA_CD]})

    assert datas(regras) == (
        date(2026, 3, 8),
        date(2026, 3, 8),
        True,
        date(2026, 4, 8),
        {'inicio': date(2026, 3, 11), 'fim': date(2026, 3, 12)},
    )
    objetiva = regras.cronograma.objetiva
    assert (objetiva.fonte, objetiva.documento_origem, objetiva.pagina_origem) == (
        FonteRegra.EDITAL,
        'edital.pdf',
        2,
    )
    assert 'Aplicação das provas objetivas e discursiva 8/3/2026' in objetiva.trecho_origem


def test_discursiva_em_outro_dia_sai_com_a_propria_data():
    regras = extrair_regras(config(), {'edital.pdf': [CRONOGRAMA_CPNU]})

    assert datas(regras) == (
        date(2025, 10, 5),
        date(2025, 12, 7),
        False,
        date(2025, 11, 12),
        {'inicio': date(2025, 10, 7), 'fim': date(2025, 10, 8)},
    )


def test_fgv_tem_a_data_por_extenso_e_a_discursiva_no_mesmo_dia():
    regras = extrair_regras(config(), {'edital.pdf': [PROVAS_CPRM]})

    c = regras.cronograma
    assert (c.objetiva.valor, c.discursiva.valor, c.discursiva_no_mesmo_dia) == (
        date(2025, 11, 30),
        date(2025, 11, 30),
        True,
    )


def test_data_ausente_no_cronograma_fica_vazia_com_aviso():
    regras = extrair_regras(config(), {'edital.pdf': [PROVA_AGSUS]})

    c = regras.cronograma
    assert c.objetiva.valor == date(2025, 10, 12)
    assert (c.discursiva.valor, c.discursiva.fonte, c.discursiva_no_mesmo_dia) == (
        None,
        FonteRegra.DEFAULT,
        None,
    )
    assert c.resultado_preliminar.valor is None
    aviso = next(a for a in regras.avisos if 'cronograma' in a)
    assert all(nome in aviso for nome in ('discursiva', 'resultado preliminar', 'resultado final', 'recurso'))
    assert 'objetiva' not in aviso


def test_data_do_resultado_no_meio_da_celula_quebrada():
    linhas = """Divulgação do edital de resultado final nas provas
5/8/2026
objetivas e de resultado provisório no procedimentode análise documental para a caracterização da
"""
    regras = extrair_regras(config(), {'edital.pdf': [linhas]})

    assert regras.cronograma.resultado_final.valor == date(2026, 8, 5)


def test_candidato_nao_encontrado_sai_com_status_explicito_e_nenhum_some():
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU]})

    assert [m.chave for m in regras.metadados] == [c.chave for c in CANDIDATOS]
    bibliografia = regras.metadado('bibliografia')
    assert (bibliografia.status, bibliografia.valor, bibliografia.fonte) == (
        StatusExtracao.NAO_ENCONTRADO,
        None,
        FonteRegra.DEFAULT,
    )


def test_candidato_encontrado_traz_valor_trecho_documento_e_pagina():
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU, AGSUS]})

    alternativas = regras.metadado('alternativas')
    assert (alternativas.status, alternativas.valor, alternativas.fonte) == (
        StatusExtracao.ENCONTRADO,
        5,
        FonteRegra.DESCOBERTA,
    )
    assert (alternativas.documento_origem, alternativas.pagina_origem) == ('edital.pdf', 2)
    assert '5 (cinco) alternativas' in alternativas.trecho_origem


def test_valores_diferentes_de_um_candidato_unico_sao_ambiguos():
    texto = (
        'A prova terá questões com 4 (quatro) alternativas. Na outra parte, haverá 5 (cinco) alternativas.'
    )
    regras = extrair_regras(config(), {'edital.pdf': [texto]})

    alternativas = regras.metadado('alternativas')
    assert (alternativas.status, alternativas.valor) == (StatusExtracao.AMBIGUO, [4, 5])


def test_o_mesmo_valor_escrito_com_zero_a_esquerda_nao_e_ambiguo():
    texto = (
        'O prazo de validade do Concurso é de 2 (dois) anos. 1.3 A validade do certame é de 02 (dois) anos.'
    )
    regras = extrair_regras(config(), {'edital.pdf': [texto]})

    validade = regras.metadado('validade')
    assert (validade.status, validade.valor) == (StatusExtracao.ENCONTRADO, '2 (dois) anos')


def test_cpnu_descobre_corte_em_acertos_com_nota_ponderada_e_a_soma_dos_eixos():
    documentos = {**DOCUMENTOS_CPNU, 'edital.pdf': [*DOCUMENTOS_CPNU['edital.pdf'], CORTES_CPNU]}
    regras = extrair_regras(cpnu(), documentos)

    corte = regras.metadado('corte_em_acertos_com_nota_ponderada')
    assert (corte.status, corte.valor, corte.fonte) == (StatusExtracao.ENCONTRADO, 36, FonteRegra.DESCOBERTA)
    assert '36 (trinta e seis) acertos' in corte.trecho_origem
    soma = regras.metadado('soma_dos_pesos_dos_eixos')
    assert (soma.status, soma.valor) == (StatusExtracao.ENCONTRADO, 10)


DESEMPATE_CD = (
    '12.1 Em caso de empate na nota final no concurso, terá preferência o candidato que, na seguinte ordem: '
    'a) obtiver idade igual ou superior a sessenta anos, até o último dia de inscrição neste concurso, '
    'conforme artigo 27, parágrafo único, do Estatuto da Pessoa Idosa (lei nº 10.741/2003); b) obtiver '
    'maior nota na prova objetiva de conhecimentos específicos (P ); 2 c) obtiver o maior número de acertos '
    'na prova objetiva de conhecimentos específicos (P ); 2 d) obtiver a maior nota na prova discursiva '
    '(P ); 3 e) obtiver o maior número de acertos na prova objetiva de conhecimentos gerais (P ) 1 f) tiver '
    'maior idade; g) tiver exercido a função de jurado (conforme art. 440 do Código de Processo Penal, '
    'conforme a Lei nº 11.689/2008). 13 DAS DISPOSIÇÕES FINAIS 13.1 A inscrição do candidato implicará a '
    'aceitação das normas.'
)
DESEMPATE_PF = (
    '18.10.1 Em caso de empate na nota final na primeira etapa do concurso para o cargo de Delegado de '
    'Polícia Federal, terá preferência o candidato que, na seguinte ordem: a) tiver idade igual ou superior '
    'a sessenta anos; b) obtiver a maior nota na prova discursiva (P ); 2 c) obtiver a maior nota na prova '
    'oral (P ); 3 d) tiver maior idade. 18.10.2 Em caso de empate na nota final na primeira etapa do '
    'concurso para os cargos de Perito Criminal Federal, terá preferência o candidato que, na seguinte '
    'ordem: a) tiver idade igual ou superior a sessenta anos; b) obtiver a maior nota na prova discursiva '
    '(P ); 2 c) obtiver a maior nota na prova objetiva (P ); 1 d) tiver maior idade. 18.11 Texto final.'
)


def test_desempate_sai_na_ordem_do_edital_com_as_provas_legiveis():
    regras = extrair_regras(config(), {'edital.pdf': [CAPA_TCU, DESEMPATE_CD]})

    desempate = regras.metadado('desempate')
    assert (desempate.status, desempate.fonte, desempate.pagina_origem) == (
        StatusExtracao.ENCONTRADO,
        FonteRegra.DESCOBERTA,
        2,
    )
    assert len(desempate.valor) == 7
    assert desempate.valor[0].startswith('obtiver idade igual ou superior a sessenta anos')
    assert desempate.valor[1:5] == [
        'obtiver maior nota na prova objetiva de conhecimentos específicos (P2)',
        'obtiver o maior número de acertos na prova objetiva de conhecimentos específicos (P2)',
        'obtiver a maior nota na prova discursiva (P3)',
        'obtiver o maior número de acertos na prova objetiva de conhecimentos gerais (P1)',
    ]
    assert desempate.valor[5:] == [
        'tiver maior idade',
        'tiver exercido a função de jurado (conforme art. 440 do Código de Processo Penal, '
        'conforme a Lei nº 11.689/2008)',
    ]
    assert 'na seguinte ordem' in desempate.trecho_origem


def test_desempate_e_o_da_lista_do_cargo_da_configuracao():
    regras = extrair_regras(
        config('CARGO 4: PERITO CRIMINAL FEDERAL – ÁREA 3: INFORMÁTICA FORENSE'),
        {'edital.pdf': [CARGOS_PF, DESEMPATE_PF]},
    )

    assert regras.metadado('desempate').valor == [
        'tiver idade igual ou superior a sessenta anos',
        'obtiver a maior nota na prova discursiva (P2)',
        'obtiver a maior nota na prova objetiva (P1)',
        'tiver maior idade',
    ]
