"""Identificação de acerto/erro/branco e completude do import TEC."""

import csv
import json
from pathlib import Path

import pytest
import yaml

from concursos.pratica_tec import (
    ARQUIVO_IMPORT_LOG,
    ARQUIVO_RESPOSTAS,
    PASTA_PRATICA,
    CompletudeInvalidaError,
    linha_de_resposta,
    resultado_questao,
    so_erros,
    tipo_questao,
    verificar_completude,
)


def erro(id_='q1', **campos):
    base = {
        'id': id_,
        'fp': 'texto',
        'd': '2026-11-02',
        't': 1,
        'v': 1,
        'ds': ['2026-11-02T10:00:00-03:00'],
        'dev': 'd1',
        'origem': 'tempo_real',
        'mat': 'Direito Tributário',
        'ass': 'Simples Nacional',
        'enun': 'Texto',
    }
    return {**base, **campos}


def caderno(id_='c1', **campos):
    return {
        'id': id_,
        'cad': 'Caderno 1',
        'mat': 'Direito Tributário',
        'tot': 100,
        'res': 10,
        'ac': 6,
        'er': 4,
        't': 1,
        **campos,
    }


def exportacao(erros=(), cads=(), **extra):
    return {
        'app': 'tec-erros',
        'v': 1,
        'em': '2026-11-02T10:00:00-03:00',
        'dev': 'd1',
        'erros': list(erros),
        'cads': list(cads),
        **extra,
    }


def gravar_json(caminho: Path, dados) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding='utf-8')
    return caminho


def ler_csv(caminho: Path) -> list[dict]:
    with caminho.open(encoding='utf-8', newline='') as arquivo:
        return list(csv.DictReader(arquivo))


@pytest.fixture
def projeto(tmp_path):
    (tmp_path / '.gabarito-vivo').mkdir()
    (tmp_path / '.gabarito-vivo' / 'taxonomia.yaml').write_text(
        yaml.safe_dump(
            {'Legislação Tributária': {'bloco': 'especifico', 'nomes': ['Direito Tributário']}},
            allow_unicode=True,
        ),
        encoding='utf-8',
    )
    gravar_json(
        tmp_path / 'analises' / 'ana' / 'alvo' / 'edital_estruturado.json',
        {
            'fonte': 'edital.pdf',
            'cargo': None,
            'conhecimentos': [
                {
                    'nome': 'Conhecimentos específicos',
                    'disciplinas': [
                        {
                            'nome': 'Legislação Tributária',
                            'topicos': [
                                {
                                    'numero': '1',
                                    'nome': 'Simples Nacional',
                                    'descricao': 'Simples Nacional',
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )
    (tmp_path / 'tec').mkdir()
    return tmp_path


def importar(projeto: Path):
    from concursos.analytics.taxonomia import carregar_taxonomia
    from concursos.pratica_tec import importar_pratica

    return importar_pratica(
        projeto / 'tec',
        projeto / 'analises' / 'ana',
        projeto / '.gabarito-vivo' / 'pratica_tec.yaml',
        carregar_taxonomia(projeto / '.gabarito-vivo' / 'taxonomia.yaml'),
        'alvo',
        None,
    )


def test_tipo_certo_errado_e_multipla():
    assert tipo_questao([{'l': 'C', 't': 'Certo'}, {'l': 'E', 't': 'Errado'}]) == 'certo_errado'
    assert tipo_questao([{'l': 'A', 't': 'um'}, {'l': 'B', 't': 'dois'}]) == 'multipla_escolha'
    assert tipo_questao([]) == 'multipla_escolha'


def test_resultado_dois_formatos():
    assert resultado_questao('Certo', 'C', 'certo_errado') == 'acerto'
    assert resultado_questao('Errado', 'Certo', 'certo_errado') == 'erro'
    assert resultado_questao('B', 'b', 'multipla_escolha') == 'acerto'
    assert resultado_questao('A', 'C', 'multipla_escolha') == 'erro'
    assert resultado_questao('A', None, 'multipla_escolha') == 'branco'
    assert resultado_questao('A', '', 'multipla_escolha') == 'branco'


def test_completude_tres_casos():
    itens = [{'id': 'q1'}, {'id': 'q2'}]
    assert verificar_completude(itens, [{'id': 'c1', 'er': 2, 'res': 5, 'tot': 10}]) == [
        'prática: exportação só de erros (len == cads.er)'
    ]
    assert verificar_completude(
        [{'id': f'q{i}'} for i in range(5)], [{'id': 'c1', 'er': 2, 'res': 5, 'tot': 10}]
    ) == ['prática: exportação completa (len == cads.res)']
    assert verificar_completude(
        [{'id': f'q{i}'} for i in range(10)], [{'id': 'c1', 'er': 2, 'res': 5, 'tot': 10}]
    ) == ['prática: exportação completa (len == cads.tot, com brancos)']
    assert verificar_completude([{'id': 'q1'}], [{'id': 'c1', 'er': 2, 'res': 5, 'tot': 10}]) == [
        'prática: exportação parcial (len < cads.er)'
    ]
    with pytest.raises(CompletudeInvalidaError, match='mais questões'):
        verificar_completude(
            [{'id': f'q{i}'} for i in range(11)], [{'id': 'c1', 'er': 2, 'res': 5, 'tot': 10}]
        )
    assert verificar_completude(itens, []) == []


def test_so_erros_filtra_acertos_e_brancos():
    itens = [
        erro(
            id_='q1',
            marc='A',
            gab='B',
            alts=[{'l': 'A', 't': 'a'}, {'l': 'B', 't': 'b'}],
        ),
        erro(
            id_='q2',
            marc='B',
            gab='B',
            alts=[{'l': 'A', 't': 'a'}, {'l': 'B', 't': 'b'}],
        ),
        erro(id_='q3', marc='', gab='A', alts=[{'l': 'A', 't': 'a'}]),
    ]
    assert [i['id'] for i in so_erros(itens)] == ['q1']


def test_import_grava_tec_respostas_e_log(projeto: Path):
    alts_me = [{'l': 'A', 't': 'a'}, {'l': 'B', 't': 'b'}, {'l': 'C', 't': 'c'}]
    alts_ce = [{'l': 'C', 't': 'Certo'}, {'l': 'E', 't': 'Errado'}]
    itens = [
        erro(id_='q-me-ok', marc='B', gab='B', alts=alts_me, ass='X', enun='ME ok', fp='me ok'),
        erro(id_='q-me-er', marc='A', gab='C', alts=alts_me, ass='X', enun='ME er', fp='me er'),
        erro(id_='q-ce-ok', marc='C', gab='Certo', alts=alts_ce, ass='Y', enun='CE ok', fp='ce ok'),
        erro(id_='q-ce-er', marc='Certo', gab='Errado', alts=alts_ce, ass='Y', enun='CE er', fp='ce er'),
        erro(id_='q-br', marc='', gab='A', alts=alts_me, ass='Z', enun='branco', fp='branco'),
    ]
    gravar_json(
        projeto / 'tec' / 'todas.json',
        exportacao(itens, [caderno(res=4, ac=2, er=2, tot=5)]),
    )
    resultado = importar(projeto)
    pasta = projeto / 'analises' / 'ana' / PASTA_PRATICA
    respostas = ler_csv(pasta / ARQUIVO_RESPOSTAS)
    assert {r['id']: r['resultado'] for r in respostas} == {
        'q-me-ok': 'acerto',
        'q-me-er': 'erro',
        'q-ce-ok': 'acerto',
        'q-ce-er': 'erro',
        'q-br': 'branco',
    }
    log = json.loads((pasta / ARQUIVO_IMPORT_LOG).read_text(encoding='utf-8'))
    assert log['n_itens'] == 5
    assert log['n_erros'] == 2
    assert any('exportação completa' in a for a in resultado.avisos)
    # erros_tec só com erros
    assert {r['id'] for r in ler_csv(pasta / 'erros_tec.csv')} == {'q-me-er', 'q-ce-er'}


def test_linha_de_resposta_tem_comentario():
    linha = linha_de_resposta({'id': 'q1', 'gab': 'A', 'marc': 'A', 'com': 'porque', 'alts': []})
    assert linha['tem_comentario'] == 'sim'
    assert linha['tipo_questao'] == 'multipla_escolha'
