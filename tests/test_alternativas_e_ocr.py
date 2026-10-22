import random

import cv2
import pandas as pd
import pytest
from conftest import analisar, criar_concurso, ler_csv
from folha_sintetica import folha_generica

from concursos import perfis
from concursos.analytics.correcao import ConfiguracaoCorrecao, aplicar_correcao
from concursos.concurso_config import ConfiguracaoInvalidaError, carregar_concurso
from concursos.folha import FolhaIlegivelError, ler_folha
from concursos.gabarito import GabaritoInvalidoError, ler_gabarito_texto
from concursos.modelo import Estado, Formato, Pontuacao, Resultado
from concursos.perfis import PerfilInvalidoError, ids_de_ocr, perfil_ocr
from concursos.respostas import RespostasInvalidasError, ler_respostas_txt

CONCURSO_4 = {
    'nome': 'quatro',
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'alternativas': 4,
    'pontuacao': 'simples',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
    'respostas': {'arquivo': 'respostas.txt'},
}


class EntryPointFalso:
    def __init__(self, nome: str, objeto: object) -> None:
        self.name = nome
        self.objeto = objeto

    def load(self) -> object:
        return self.objeto


def test_concurso_de_4_alternativas_aceita_gabarito_e_respostas_de_a_a_d(raizes):
    provas, analises = raizes
    criar_concurso(
        provas,
        'quatro',
        CONCURSO_4,
        {'gabarito.txt': '1 A\n2 B\n3 C\n4 D\n', 'respostas.txt': '1 A\n2 B\n3 D\n4 -\n'},
    )

    assert analisar(provas, analises) == 0

    desempenho = ler_csv(analises / 'quatro' / 'desempenho_por_disciplina.csv')
    assert int(desempenho['acertos'].sum()) == 2


def test_letra_fora_das_alternativas_diz_a_linha_e_as_letras_aceitas():
    with pytest.raises(
        RespostasInvalidasError, match=r"linha 2: resposta 'E' inválida \(use A, B, C, D ou -\)"
    ):
        ler_respostas_txt('1 A\n2 E\n', Formato.MULTIPLA_ESCOLHA, [1, 2], 'respostas.txt', alternativas=4)
    with pytest.raises(GabaritoInvalidoError, match=r"linha 1: gabarito 'E' inválido .*use A, B, C, D"):
        ler_gabarito_texto('1 E\n', Formato.MULTIPLA_ESCOLHA, 'gabarito.txt', alternativas=4)


def test_cinco_alternativas_continua_o_padrao():
    itens = ler_gabarito_texto('1 E\n', Formato.MULTIPLA_ESCOLHA, 'gabarito.txt')

    assert itens[0].resposta == 'E'


@pytest.mark.parametrize(
    ('formato', 'alternativas', 'mensagem'),
    [('certo_errado', 4, 'alternativas'), ('multipla_escolha', 1, 'alternativas')],
)
def test_numero_de_alternativas_invalido_aponta_o_campo(tmp_path, formato, alternativas, mensagem):
    criar_concurso(tmp_path, 'x', {**CONCURSO_4, 'formato': formato, 'alternativas': alternativas}, {})

    with pytest.raises(ConfiguracaoInvalidaError, match=mensagem):
        carregar_concurso(tmp_path / 'x')


def test_pontuacao_cebraspe_continua_aceita(tmp_path):
    dados = {**CONCURSO_4, 'formato': 'certo_errado', 'pontuacao': 'cebraspe'}
    del dados['alternativas']
    criar_concurso(tmp_path, 'x', dados, {})

    assert carregar_concurso(tmp_path / 'x').pontuacao is Pontuacao.CEBRASPE


def test_ajustada_usa_o_numero_de_alternativas_do_concurso():
    questoes = pd.DataFrame(
        {'questao': [1], 'resultado': [Resultado.ERRO], 'anulada': [False]},
    )

    itens = aplicar_correcao(questoes, ConfiguracaoCorrecao(), Formato.MULTIPLA_ESCOLHA, alternativas=4).itens

    assert itens['pontos_ajustada'].iloc[0] == pytest.approx(-1 / 3)


def test_folha_de_4_alternativas_lida_com_o_perfil_de_ocr(tmp_path):
    sorteio = random.Random(5)
    marcas = {q: sorteio.choice(['A', 'B', 'C', 'D', '']) for q in range(1, 121)}
    caminho = tmp_path / 'folha.png'
    cv2.imwrite(str(caminho), folha_generica('ABCD', marcas, 120, 20))

    lidas = ler_folha(caminho, 'grade_abcd', 120, 20, tmp_path / 'depuracao', 0.75)

    assert {r.questao: r.alternativa for r in lidas} == {q: m or None for q, m in marcas.items()}
    assert all(r.estado is (Estado.MARCADA if marcas[r.questao] else Estado.BRANCO) for r in lidas)
    assert perfil_ocr('grade_abcd').alternativas == 'ABCD'


def test_perfil_de_ocr_desconhecido_lista_os_disponiveis(tmp_path):
    with pytest.raises(FolhaIlegivelError, match='cebraspe_ce, fgv_cpnu_90, fgv_mod70ae, grade_abcd'):
        ler_folha(tmp_path / 'folha.png', 'nao_existe', 40, None, tmp_path, 0.75)
    with pytest.raises(PerfilInvalidoError, match='grade_abcd'):
        perfil_ocr('nao_existe')


def test_perfis_de_ocr_embutidos_guardam_os_limiares_atuais():
    fgv = perfil_ocr('fgv_mod70ae')

    assert (fgv.alternativas, fgv.itens_por_coluna) == ('ABCDE', 20)
    assert (fgv.vazio, fgv.cheio, fgv.limiar_marcada, fgv.largura) == (0.2, 0.9, 0.5, 2480)
    assert perfil_ocr('cebraspe_ce').alternativas == 'CE'


def test_perfil_de_ocr_por_entry_point(monkeypatch):
    perfis.perfis_de_ocr.cache_clear()
    proprio = {'id': 'minha_folha', 'alternativas': 'ABCD', 'itens_por_coluna': 25}
    monkeypatch.setattr(
        perfis,
        'entry_points',
        lambda group: [EntryPointFalso('minha', proprio)] if group == 'concurso.ocr' else [],
    )
    try:
        assert 'minha_folha' in ids_de_ocr()
        assert perfil_ocr('minha_folha').itens_por_coluna == 25
    finally:
        perfis.perfis_de_ocr.cache_clear()
