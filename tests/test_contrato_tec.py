import json
from pathlib import Path

from concursos.pratica_tec import ler_entrada, ler_exportacao, mesclar_cadernos, mesclar_erros

PASTA = Path(__file__).parent / 'contrato_tec'
ENTRADA = PASTA / 'entrada'


def exportacoes() -> list[tuple[dict, list[str]]]:
    return [ler_exportacao(caminho) for caminho in sorted(ENTRADA.glob('tec-erros-*.json'))]


def test_mesclagem_das_exportacoes_do_contrato_igual_a_do_tec_erros():
    erros: list[dict] = []
    cadernos: list[dict] = []
    for dados, _ in exportacoes():
        erros = mesclar_erros(erros, dados['erros'])
        cadernos = mesclar_cadernos(cadernos, dados['cads'])

    esperada = json.loads((PASTA / 'mesclagem_esperada.json').read_text(encoding='utf-8'))
    assert erros == esperada['erros']
    assert cadernos == esperada['cads']


def test_registro_sem_mudanca_mantem_o_t_de_quando_mudou():
    erros: list[dict] = []
    for dados, _ in exportacoes():
        erros = mesclar_erros(erros, dados['erros'])

    assert next(e for e in erros if e['id'] == 'q300')['t'] == 500


def test_campo_desconhecido_na_exportacao_vira_aviso():
    avisos = [aviso for _, avisos in exportacoes() for aviso in avisos]

    assert len(avisos) == 1
    assert avisos[0].endswith('campo desconhecido ignorado: extra')


def test_ler_entrada_aplica_os_removidos_do_caderno_estado():
    pratica, avisos = ler_entrada(ENTRADA)

    assert [e['id'] for e in pratica.erros] == ['q100', 'h1a2b3c4d', 'q300']
    assert pratica.estado['aliases']['Outro assunto'] is None
    assert len(pratica.cadernos) == 4
    assert len(avisos) == 1
