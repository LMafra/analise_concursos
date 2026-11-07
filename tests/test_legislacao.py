from pathlib import Path

import pytest
from conftest import log_completo

from concursos.legislacao import (
    TAMANHO_MINIMO_NORMA,
    Citacao,
    TipoNorma,
    avisos_da_norma,
    citacoes_do_edital,
    conteudo_para_notebook,
    extrair_citacoes,
    ler_repositorio,
    normas_citadas,
    resolver,
    titulo_para_notebook,
)

TOPICO_CD = (
    'Lei de Acesso à Informação (Lei nº 12.527/2011). Lei Geral de Proteção de Dados (Lei nº 13.709/2018). '
    'Processo administrativo (Lei nº 9.784/1999).'
)
TOPICO_AGSUS = (
    'Lei Federal nº 13.958, de 18 de dezembro de 2019, alterada pela Lei Federal nº 14.621, de 14 de julho de '
    '2023. Decreto Legislativo nº 143, de 20 de junho de 2002.'
)
TOPICO_FUNPRESP = (
    'Previdência complementar: Leis Complementares nº 108/2001 e nº 109/2001; Lei nº 12.618/2012.'
)
TOPICO_TCU = 'Lei nº 14.133/2021, Decreto nº 10.024/2019, Lei nº 13.709/2018 – LGPD (impactos em contratos).'


def chaves(citacoes: list[Citacao]) -> list[tuple]:
    return [(c.tipo.value, c.numero, c.ano) for c in citacoes]


def test_lei_com_barra_e_ano():
    assert chaves(extrair_citacoes(TOPICO_CD)) == [
        ('lei', '12527', 2011),
        ('lei', '13709', 2018),
        ('lei', '9784', 1999),
    ]


def test_lei_com_data_por_extenso_e_sem_decreto_legislativo():
    citacoes = extrair_citacoes(TOPICO_AGSUS)

    assert chaves(citacoes) == [('lei', '13958', 2019), ('lei', '14621', 2023)]
    assert citacoes[0].trecho == 'Lei Federal nº 13.958, de 18 de dezembro de 2019'


def test_lista_de_leis_complementares():
    assert chaves(extrair_citacoes(TOPICO_FUNPRESP)) == [
        ('lei_complementar', '108', 2001),
        ('lei_complementar', '109', 2001),
        ('lei', '12618', 2012),
    ]


def test_lei_e_decreto_na_mesma_frase():
    assert chaves(extrair_citacoes(TOPICO_TCU)) == [
        ('lei', '14133', 2021),
        ('decreto', '10024', 2019),
        ('lei', '13709', 2018),
    ]


def test_ano_com_sublinhado_e_com_dois_digitos():
    assert chaves(extrair_citacoes('Lei nº 13.303_2016 (Lei das Estatais) e Lei 8.112/90')) == [
        ('lei', '13303', 2016),
        ('lei', '8112', 1990),
    ]


def test_sumulas_e_constituicao():
    texto = 'Constituição Federal de 1988; Súmula Vinculante nº 13; Súmula nº 222 do TCU; CF/88.'

    assert chaves(extrair_citacoes(texto)) == [
        ('constituicao', None, None),
        ('sumula_vinculante', '13', None),
        ('sumula_tcu', '222', None),
    ]


def test_texto_sem_norma_nao_cita_nada():
    assert extrair_citacoes('Leis de De Morgan; leitura e gravação; lei penal no tempo.') == []


def gravar(repositorio: Path, relativo: str, cabecalho: str, corpo: str = 'Art. 1º Texto.\n') -> Path:
    caminho = repositorio / relativo
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(f'---\n{cabecalho}---\n\n{corpo}', encoding='utf-8')
    return caminho


@pytest.fixture
def repositorio(tmp_path: Path) -> Path:
    raiz = tmp_path / 'leis'
    gravar(
        raiz,
        'federal/leis-ordinarias/2018/lei-13709-2018-08-14.md',
        'titulo: "Lei nº 13.709, de 14 de agosto de 2018"\nementa: "Lei Geral de Proteção de Dados Pessoais (LGPD)."\n'
        'versao_texto: "compilada (texto vigente)"\nurn: "urn:lex:br:federal:lei:2018-08-14;13709"\n'
        'fonte: "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm"\n',
        'x' * TAMANHO_MINIMO_NORMA,
    )
    gravar(
        raiz,
        'federal/leis-ordinarias/2021/lei-14133-2021-04-01.md',
        'titulo: "Lei nº 14.133, de 1º de abril de 2021"\nementa: "Lei de Licitações e Contratos Administrativos."\n'
        'versao_texto: "republicação/retificação"\nurn: "urn:lex:br:federal:lei:2021-04-01;14133"\n',
    )
    gravar(
        raiz, 'federal/decretos/2019/dec-10024-2019-09-20.md', 'titulo: "Decreto nº 10.024"\nrevogada: true\n'
    )
    gravar(
        raiz,
        'jurisprudencia/stf/sumulas-vinculantes/sumula-vinculante-13.md',
        'titulo: "Súmula Vinculante 13"\n',
    )
    (raiz / 'constituicao.md').write_text('# Constituição\n' + 'Art. 1º\n' * 2000, encoding='utf-8')
    return raiz


def test_resolve_lei_pelo_numero_e_ano(repositorio):
    norma = resolver(Citacao(TipoNorma.LEI, '13709', 2018, 'Lei nº 13.709/2018'), repositorio)

    assert norma.relativo == 'federal/leis-ordinarias/2018/lei-13709-2018-08-14.md'
    assert norma.urn == 'urn:lex:br:federal:lei:2018-08-14;13709'
    assert norma.chave == norma.urn
    assert avisos_da_norma(norma) == []


def test_lei_parcial_tem_aviso_de_versao_e_de_tamanho(repositorio):
    norma = resolver(Citacao(TipoNorma.LEI, '14133', 2021, ''), repositorio)

    avisos = avisos_da_norma(norma)
    assert any('não compilado' in aviso for aviso in avisos)
    assert any('incompleto' in aviso for aviso in avisos)
    assert conteudo_para_notebook(norma).startswith('AVISO: texto não compilado')


def test_decreto_revogado_e_sumula_pequena_sem_aviso_de_tamanho(repositorio):
    decreto = resolver(Citacao(TipoNorma.DECRETO, '10024', 2019, ''), repositorio)
    sumula = resolver(Citacao(TipoNorma.SUMULA_VINCULANTE, '13', None, ''), repositorio)

    assert 'norma revogada' in avisos_da_norma(decreto)
    assert avisos_da_norma(sumula) == []


def test_constituicao_sem_cabecalho_usa_a_fonte_do_planalto(repositorio):
    norma = resolver(Citacao(TipoNorma.CONSTITUICAO, None, None, 'CF/88'), repositorio)

    assert norma.titulo == 'Constituição Federal'
    assert norma.fonte.startswith('https://www.planalto.gov.br')
    assert norma.chave == 'constituicao.md'


def test_citacao_sem_arquivo_vira_aviso(repositorio, caplog):
    normas = normas_citadas(extrair_citacoes('Decreto nº 12.572/2025'), repositorio)

    assert normas == {}
    assert 'git pull' in log_completo(caplog)


def test_titulo_com_ementa_curta(repositorio):
    norma = resolver(Citacao(TipoNorma.LEI, '13709', 2018, ''), repositorio)

    assert titulo_para_notebook(norma) == (
        'Lei nº 13.709, de 14 de agosto de 2018 — Lei Geral de Proteção de Dados Pessoais (LGPD).'
    )


def test_citacoes_do_edital_estruturado(tmp_path):
    (tmp_path / 'edital_estruturado.json').write_text(
        '{"conhecimentos": [{"disciplinas": [{"nome": "Direito", "topicos": ['
        '{"nome": "Lei nº 9.784/1999"}, {"nome": "LAI (Lei nº 12.527/2011) e Lei nº 9.784/1999"}]}]}]}',
        encoding='utf-8',
    )

    assert chaves(citacoes_do_edital(tmp_path)) == [('lei', '9784', 1999), ('lei', '12527', 2011)]
    assert citacoes_do_edital(tmp_path / 'outro') == []


def test_repositorio_da_configuracao_global(tmp_path):
    config = tmp_path / 'config.toml'
    assert ler_repositorio(config) is None

    config.write_text('[legislacao]\nrepositorio = "~/projects/leis"\n', encoding='utf-8')

    assert ler_repositorio(config) == Path('~/projects/leis').expanduser()
