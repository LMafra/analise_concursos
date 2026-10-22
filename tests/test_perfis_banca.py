import json
import re
from pathlib import Path

import pytest
from conftest import analisar, criar_concurso

from concursos import perfis
from concursos.deteccao import detectar_banca
from concursos.perfis import PerfilInvalidoError, de_dict, ids_de_banca, perfil_da_banca, resolver_funcao

PACOTE = Path(__file__).resolve().parents[1] / 'src' / 'concursos'


class EntryPointFalso:
    def __init__(self, nome: str, objeto: object) -> None:
        self.name = nome
        self.objeto = objeto

    def load(self) -> object:
        return self.objeto


@pytest.fixture
def registro_limpo():
    perfis.perfis_de_banca.cache_clear()
    yield
    perfis.perfis_de_banca.cache_clear()


def test_perfil_embutido_declara_o_comportamento_da_banca():
    cebraspe = perfil_da_banca('cebraspe')
    fgv = perfil_da_banca('fgv')

    assert cebraspe.marcas == ('CEBRASPE',)
    assert (cebraspe.formato, cebraspe.penalidade) == ('certo_errado', 1.0)
    assert (cebraspe.leitor_gabarito, cebraspe.leitor_cargo, cebraspe.segmentacao) == (
        'cebraspe',
        'cebraspe',
        'itens',
    )
    assert cebraspe.chave_da_prova('CARGO 1 CONHECIMENTOS BASICOS') == 'cb'
    assert cebraspe.chave_da_prova('CARGO 1') == 'ce'
    assert cebraspe.template_folha(200) == 'cebraspe_ce'
    assert (fgv.leitor_secoes, fgv.penalidade, fgv.disciplinas_pelo_caderno) == ('fgv', 0.0, True)
    assert fgv.chave_da_prova('qualquer') == 'unica'
    assert (fgv.template_folha(70), fgv.template_folha(90), fgv.template_folha(50)) == (
        'fgv_mod70ae',
        'fgv_cpnu_90',
        None,
    )


def test_bancas_embutidas_na_ordem_de_deteccao():
    assert ids_de_banca()[:4] == ('cebraspe', 'fgv', 'selecon', 'quadrix')


def test_banca_por_entry_point_e_detectada_e_usada(registro_limpo, monkeypatch, tmp_path):
    ficticia = {
        'id': 'ficticia',
        'nome': 'Banca Fictícia',
        'marcas': ['BANCA FICTICIA'],
        'leitor_secoes': 'lista',
    }
    monkeypatch.setattr(
        perfis,
        'entry_points',
        lambda group: [EntryPointFalso('ficticia', ficticia)] if group == 'concurso.banca' else [],
    )
    provas, analises = tmp_path / 'provas', tmp_path / 'analises'
    config = {
        'nome': 'f',
        'banca': 'ficticia',
        'formato': 'multipla_escolha',
        'pontuacao': 'simples',
        'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 2]}},
        'respostas': {'arquivo': 'respostas.txt'},
    }
    criar_concurso(provas, 'f', config, {'gabarito.txt': '1 A\n2 B\n', 'respostas.txt': '1 A\n2 C\n'})

    assert detectar_banca('Edital da Banca Fictícia de 2026') == 'ficticia'
    assert 'ficticia' in ids_de_banca()
    assert analisar(provas, analises) == 0
    assert (analises / 'f' / 'relatorio.md').exists()


def test_perfil_invalido_aponta_o_campo():
    with pytest.raises(PerfilInvalidoError, match='segmentacao'):
        de_dict({'id': 'x', 'marcas': ['X'], 'segmentacao': 'por_pagina'})
    with pytest.raises(PerfilInvalidoError, match='campos desconhecidos: cor'):
        de_dict({'id': 'x', 'marcas': ['X'], 'cor': 'azul'})


def test_leitor_externo_por_caminho_de_modulo():
    assert resolver_funcao('json:dumps', {}) is json.dumps
    with pytest.raises(PerfilInvalidoError, match='leitor desconhecido'):
        resolver_funcao('nao_existe', {'cebraspe': json.dumps})


def test_nenhum_modulo_compara_o_nome_da_banca_com_uma_constante():
    comparacao = re.compile(
        r"banca\s*(==|!=|not in|in)\s*(['\"({]|[A-Z_]{3,})|pontuacao is (not )?Pontuacao\."
    )
    achados = [
        f'{arquivo.relative_to(PACOTE)}:{numero}'
        for arquivo in PACOTE.rglob('*.py')
        for numero, linha in enumerate(arquivo.read_text(encoding='utf-8').splitlines(), 1)
        if comparacao.search(linha)
    ]
    assert achados == []
