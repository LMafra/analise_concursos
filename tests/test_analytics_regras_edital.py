from pathlib import Path

from concursos.analytics.regras_edital import FonteRegra, extrair_regras
from concursos.concurso_config import validar_dados

CAPA_TCU = """TRIBUNAL DE CONTAS DA UNIÃO
CONCURSO PÚBLICO PARA O PROVIMENTO DE VAGAS E A FORMAÇÃO DE CADASTRO DE RESERVA PARA
O CARGO DE AUDITOR FEDERAL DE CONTROLE EXTERNO
EDITAL Nº 1 – TCU/AUFC, DE 24 DE OUTUBRO DE 2025
Versão atualizada até a retificação do Edital nº 5 – TCU/AUFC, de 23 de janeiro de 2026.
A Diretora-Geral do Instituto Serzedello Corrêa, do Tribunal de Contas da União, torna pública a realização de
concurso público para o provimento de vagas e a formação de cadastro de reserva para o cargo de Auditor Federal de
Controle Externo – AUFC, mediante as condições estabelecidas neste edital.
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
inscrições relativas à realização do processo seletivo simplificado destinado ao preenchimento de 106 (cento e seis)
vagas para o cargo de Analista de Gestão e 24 (vinte e quatro) vagas para o cargo de Auxiliar de Gestão, e formação de
cadastro de reserva, para contratação dos profissionais, nos termos deste Edital.
"""


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
        + 'Os candidatos ao cargo de Perito Criminal Federal – Área 3 serão convocados quando estiverem entre '
        'os 45 candidatos mais bem classificados na prova objetiva.'
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
