from dataclasses import asdict
from pathlib import Path

from test_analytics_regras_edital import CAPA_AGSUS, CAPA_TCU, CARGOS_PF, config

from concursos.analytics.insights import nome_do_concurso, rotulo_do_concurso, rotulos_dos_concursos
from concursos.analytics.regras_edital import (
    CONFIANCA_SIGLA_PELAS_INICIAIS,
    FonteRegra,
    extrair_regras,
)
from concursos.concurso_config import validar_dados

CAPA_CPRM = """COMPANHIA DE PESQUISA DE RECURSOS MINERAIS - CPRM
EDITAL Nº 01/2025 – RETIFICADO EM 24 DE NOVEMBRO DE 2025
O Diretor-Presidente da Companhia de Pesquisa de Recursos Minerais - CPRM, Empresa Pública vinculada ao
Ministério de Minas e Energia, torna pública a realização do Concurso Público."""

CAPA_CAMARA = """CÂMARA DOS DEPUTADOS
CONCURSO PÚBLICO PARA PROVIMENTO DE VAGAS NO CARGO DE TÉCNICO LEGISLATIVO
EDITAL Nº 1 – CÂMARA DOS DEPUTADOS, DE 30 DE DEZEMBRO DE 2025
O Diretor-Geral da Câmara dos Deputados torna pública a realização de concurso público."""

CAPA_SEM_ANO = """FUNDAÇÃO DE PREVIDÊNCIA COMPLEMENTAR DO SERVIDOR PÚBLICO FEDERAL DO PODER JUDICIÁRIO (FUNPRESP-JUD)
EDITAL Nº 1 – FUNPRESP-JUD
O Diretor-Presidente da Fundação torna pública a realização de concurso público."""


def identificacao(capa: str, cargo: str | None = None, **extra):
    return extrair_regras(config(cargo, **extra), {'edital.pdf': [capa]}).identificacao


def test_sigla_e_ano_pela_linha_do_edital():
    tcu = identificacao(CAPA_TCU)
    assert (tcu.sigla.valor, tcu.ano.valor) == ('TCU', 2025)
    assert tcu.sigla.fonte is FonteRegra.EDITAL
    assert 'EDITAL Nº 1 – TCU/AUFC' in tcu.sigla.trecho_origem
    assert (tcu.sigla.documento_origem, tcu.sigla.pagina_origem) == ('edital.pdf', 1)
    assert tcu.sigla.confianca_extracao > CONFIANCA_SIGLA_PELAS_INICIAIS

    pf = identificacao(CARGOS_PF, 'CARGO 4: PERITO CRIMINAL FEDERAL – ÁREA 3: INFORMÁTICA FORENSE')
    assert (pf.sigla.valor, pf.ano.valor) == ('PF', 2025)

    agsus = identificacao(CAPA_AGSUS, 'Analista de Gestão Tecnologia da Informação')
    assert (agsus.sigla.valor, agsus.ano.valor) == ('AgSUS', 2025)


def test_sigla_no_fim_do_nome_oficial_e_ano_pelo_numero_do_edital():
    cprm = identificacao(CAPA_CPRM)
    assert (cprm.sigla.valor, cprm.ano.valor) == ('CPRM', 2025)
    assert 'COMPANHIA DE PESQUISA' in cprm.sigla.trecho_origem


def test_sigla_entre_parenteses_do_nome_oficial():
    funpresp = identificacao(CAPA_SEM_ANO)
    assert funpresp.sigla.valor == 'FUNPRESP-JUD'


def test_sem_sigla_no_texto_usa_as_iniciais_com_confianca_baixa():
    camara = identificacao(CAPA_CAMARA)
    assert camara.sigla.valor == 'CD'
    assert camara.sigla.confianca_extracao == CONFIANCA_SIGLA_PELAS_INICIAIS
    assert camara.ano.valor == 2025


def test_sem_ano_no_edital_usa_o_da_data_da_prova():
    sem_data = identificacao(CAPA_SEM_ANO)
    assert sem_data.ano.valor is None
    com_data = identificacao(CAPA_SEM_ANO, data_prova='2026-05-10')
    assert (com_data.ano.valor, com_data.ano.fonte) == (2026, FonteRegra.CONFIG)


def _config(**extra):
    dados = {
        'nome': 'tcu_25',
        'banca': 'cebraspe',
        'formato': 'certo_errado',
        'provas': {'unica': {'gabarito': 'g.txt', 'itens': [1, 10]}},
        **extra,
    }
    return validar_dados(Path('tcu_25'), dados)


def _dados(capa: str, cargo: str | None = None) -> dict:
    return asdict(identificacao(capa, cargo))


def test_nome_pelo_edital_com_sigla_ano_e_cargo():
    nome = nome_do_concurso(_config(), _dados(CAPA_TCU))
    assert nome.titulo == 'TCU 2025 — Auditor Federal de Controle Externo'
    assert nome.subtitulo == 'Tribunal de Contas da União, Edital nº 1/2025'
    assert (nome.fonte, nome.a_confirmar) == (FonteRegra.EDITAL, False)


def test_sigla_pelas_iniciais_cede_ao_nome_oficial():
    nome = nome_do_concurso(_config(cargo='Técnico Legislativo'), _dados(CAPA_CAMARA, 'Técnico Legislativo'))
    assert nome.titulo.startswith('Câmara dos Deputados 2025')


def test_correcao_do_usuario_vence():
    nome = nome_do_concurso(_config(titulo='Meu TCU'), _dados(CAPA_TCU))
    assert (nome.titulo, nome.fonte, nome.confianca, nome.a_confirmar) == (
        'Meu TCU',
        FonteRegra.CONFIG,
        1.0,
        False,
    )


def test_sem_edital_cai_no_pci_no_arquivo_e_na_pasta_a_confirmar():
    pci = nome_do_concurso(_config(pci={'id': 7, 'titulo': 'TRE-MG 2026 - Analista Judiciário'}), None)
    assert (pci.titulo, pci.fonte, pci.a_confirmar) == (
        'TRE-MG 2026 - Analista Judiciário',
        FonteRegra.PCI,
        True,
    )

    arquivo = nome_do_concurso(_config(edital='edital_trf1_2024.pdf'), None)
    assert (arquivo.titulo, arquivo.a_confirmar) == ('Edital trf1 2024', True)
    assert 'arquivo' in arquivo.origem

    pasta = nome_do_concurso(_config(edital='edital.pdf'), None)
    assert (pasta.titulo, pasta.fonte, pasta.a_confirmar) == ('tcu_25', FonteRegra.DEFAULT, True)


def test_nome_vindo_da_ia_fica_a_confirmar():
    dados = _dados(CAPA_TCU)
    for campo in ('sigla', 'nome_oficial', 'cargo'):
        dados[campo]['fonte'] = FonteRegra.LLM.value
    nome = nome_do_concurso(_config(), dados)
    assert (nome.fonte, nome.a_confirmar) == (FonteRegra.LLM, True)


def test_rotulo_do_concurso():
    assert rotulo_do_concurso('tcu_25', _dados(CAPA_TCU)) == (
        'tcu_25: Tribunal de Contas da União — Auditor Federal de Controle Externo'
    )
    assert rotulo_do_concurso('tcu_25', None) == 'tcu_25'
    assert rotulos_dos_concursos({'tcu_25': {'identificacao': _dados(CAPA_TCU)}, 'x': {}}) == {
        'tcu_25': 'tcu_25: Tribunal de Contas da União — Auditor Federal de Controle Externo',
        'x': 'x',
    }
