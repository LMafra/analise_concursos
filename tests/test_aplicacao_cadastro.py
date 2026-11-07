import json
from datetime import date
from pathlib import Path

import pytest
import yaml
from concurso_sintetico import EDITAL_TCU
from test_aplicacao_envio import GABARITO_FGV, Roteiro, opcoes

from concursos.aplicacao import cadastro, nomes
from concursos.aplicacao.projeto import concurso_alvo
from concursos.deteccao import Papel


@pytest.fixture
def raiz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / 'projeto'
    (pasta / 'provas').mkdir(parents=True)
    monkeypatch.chdir(pasta)
    return pasta


def _envio(tmp_path: Path, nome: str, com_edital: bool = True) -> dict[Path, Papel]:
    pasta = tmp_path / nome
    pasta.mkdir()
    (pasta / 'gabarito.txt').write_text(GABARITO_FGV, encoding='utf-8')
    papeis = {pasta / 'gabarito.txt': Papel.GABARITO}
    if com_edital:
        (pasta / 'edital.txt').write_text(EDITAL_TCU, encoding='utf-8')
        papeis[pasta / 'edital.txt'] = Papel.EDITAL
    return papeis


def test_pasta_automatica_pela_sigla_e_ano_do_edital_e_numerada_se_existir(raiz, tmp_path):
    primeira = cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), None, _envio(tmp_path, 'a'), None)
    segunda = cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), None, _envio(tmp_path, 'b'), None)

    assert primeira == raiz / 'provas' / 'tcu_2025'
    assert segunda == raiz / 'provas' / 'tcu_2025_2'


def test_sem_edital_a_pasta_leva_a_data_do_cadastro(raiz, tmp_path):
    pasta = cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), None, _envio(tmp_path, 'a', False), None)

    assert pasta == raiz / 'provas' / f'concurso_{date.today():%Y%m%d}'


def test_pasta_explicita_continua_valendo(raiz, tmp_path):
    pasta = cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), 'meu_tcu', _envio(tmp_path, 'a'), None)

    assert pasta == raiz / 'provas' / 'meu_tcu'


def test_nome_detectado_vem_do_edital(tmp_path):
    detectado = cadastro.nome_detectado(_envio(tmp_path, 'a'))

    assert detectado is not None
    assert detectado.titulo == 'TCU 2025 — Auditor Federal de Controle Externo'
    assert detectado.origem == 'do edital'
    assert cadastro.nome_detectado(_envio(tmp_path, 'b', False)) is None


def test_corrigir_titulo_grava_no_concurso_e_vazio_volta_ao_edital(raiz, tmp_path):
    pasta = cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), None, _envio(tmp_path, 'a'), None)

    cadastro.corrigir_titulo(opcoes(raiz), pasta.name, '  TCU AUFC 2025  ')
    assert yaml.safe_load((pasta / 'concurso.yaml').read_text(encoding='utf-8'))['titulo'] == 'TCU AUFC 2025'

    cadastro.corrigir_titulo(opcoes(raiz), pasta.name, '')
    assert 'titulo' not in yaml.safe_load((pasta / 'concurso.yaml').read_text(encoding='utf-8'))


def test_concurso_existente_nao_muda_de_pasta(raiz, tmp_path):
    antiga = cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), 'tcu_antigo', _envio(tmp_path, 'a'), None)
    cadastro.corrigir_titulo(opcoes(raiz), 'tcu_antigo', 'TCU 2025')

    assert antiga.is_dir()
    assert sorted(p.name for p in (raiz / 'provas').iterdir()) == ['tcu_antigo']


def test_nome_na_tela_antes_da_analise_vem_da_leitura_rapida_do_edital(raiz, tmp_path):
    pasta = cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), None, _envio(tmp_path, 'a'), None)
    contexto = opcoes(raiz).contexto

    nome = nomes.nome_no_projeto(contexto, concurso_alvo(contexto, pasta.name))

    assert nome.titulo == 'TCU 2025 — Auditor Federal de Controle Externo'
    assert nome.subtitulo == 'Tribunal de Contas da União, Edital nº 1/2025'
    assert not nome.a_confirmar


def test_nome_na_tela_prefere_o_edital_estruturado_da_analise(raiz, tmp_path):
    pasta = cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), None, _envio(tmp_path, 'a'), None)
    contexto = opcoes(raiz).contexto
    analise = raiz / 'analises' / 'ana' / pasta.name
    analise.mkdir(parents=True)
    identificacao = {
        'sigla': {'valor': 'TCU', 'fonte': 'retificacao', 'confianca_extracao': 0.9},
        'ano': {'valor': 2026, 'fonte': 'retificacao'},
        'nome_oficial': {'valor': 'Tribunal de Contas da União', 'fonte': 'retificacao'},
    }
    (analise / 'edital_estruturado.json').write_text(json.dumps({'identificacao': identificacao}))

    nome = nomes.nome_no_projeto(contexto, concurso_alvo(contexto, pasta.name))

    assert (nome.titulo, nome.origem) == ('TCU 2026', 'da retificação do edital')


def test_opcoes_de_concurso_mostram_o_nome_e_a_pasta_sem_cadastro_pelo_nome(raiz, tmp_path):
    cadastro.cadastrar_envio(opcoes(raiz, Roteiro()), None, _envio(tmp_path, 'a'), None)
    (raiz / 'provas' / 'rascunho').mkdir()

    assert nomes.opcoes_de_concurso(opcoes(raiz).contexto) == {
        'rascunho': 'rascunho',
        'tcu_2025': 'TCU 2025 — Auditor Federal de Controle Externo',
    }
