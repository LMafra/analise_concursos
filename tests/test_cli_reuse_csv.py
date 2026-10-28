import logging
from pathlib import Path

import cv2
import pytest
import yaml
from conftest import com_edital_minimo, ler_csv
from folha_sintetica import folha_cebraspe

from concursos.cli import main

TOTAL = 105
GABARITO = ''.join(f'{q} {"C" if q % 2 else "E"}\n' for q in range(1, TOTAL + 1))
CONCURSO = {
    'nome': 'cebraspe',
    'banca': 'cebraspe',
    'formato': 'certo_errado',
    'pontuacao': 'cebraspe',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, TOTAL]}},
}
PERFIL_FOLHA = {'respostas': {'folha': 'folha.png', 'template': 'cebraspe_ce', 'total_itens': TOTAL}}


def marcas(**trocas: str) -> dict[int, str]:
    resultado = {q: 'C' for q in range(1, TOTAL + 1)}
    resultado[2] = ''
    resultado.update({int(q.removeprefix('q')): v for q, v in trocas.items()})
    return resultado


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / 'projeto'
    pasta = raiz / 'provas' / 'cebraspe'
    candidato = pasta / 'candidatos' / 'ana'
    candidato.mkdir(parents=True)
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(com_edital_minimo(pasta, CONCURSO)), encoding='utf-8')
    (pasta / 'gabarito.txt').write_text(GABARITO, encoding='utf-8')
    (candidato / 'candidato.yaml').write_text(yaml.safe_dump(PERFIL_FOLHA), encoding='utf-8')
    gravar_folha(raiz, marcas())
    monkeypatch.chdir(raiz)
    return raiz


def gravar_folha(raiz: Path, marcacoes: dict[int, str]) -> None:
    caminho = raiz / 'provas' / 'cebraspe' / 'candidatos' / 'ana' / 'folha.png'
    cv2.imwrite(str(caminho), folha_cebraspe(marcacoes, TOTAL, 15))


def saida(raiz: Path, arquivo: str, candidato: str = 'ana') -> Path:
    return raiz / 'analises' / candidato / 'cebraspe' / arquivo


def acertos(raiz: Path, candidato: str = 'ana') -> int:
    return int(ler_csv(saida(raiz, 'desempenho_por_disciplina.csv', candidato))['acertos'].sum())


def revisar_csv(raiz: Path, **respostas: str) -> None:
    caminho = saida(raiz, 'respostas_extraidas.csv')
    tabela = ler_csv(caminho)
    for questao, alternativa in respostas.items():
        tabela.loc[tabela['questao'] == int(questao.removeprefix('q')), 'alternativa_marcada'] = alternativa
    tabela.to_csv(caminho, index=False)


def test_reuse_csv_aplica_a_revisao_que_vence_a_folha(projeto):
    assert main(['--candidate', 'ana']) == 0
    antes = acertos(projeto)

    revisar_csv(projeto, q2='E', q4='E')
    assert main(['analyze', 'cebraspe', '--reuse-csv', '--candidate', 'ana']) == 0

    assert (projeto / 'provas/cebraspe/candidatos/ana/respostas_revisadas.csv').exists()
    assert acertos(projeto) == antes + 2
    respostas = ler_csv(saida(projeto, 'respostas_extraidas.csv')).set_index('questao')
    assert respostas.loc[2, ['alternativa_marcada', 'origem']].tolist() == ['E', 'revisada']


def test_execucao_seguinte_nao_reprocessa(projeto):
    assert main(['--candidate', 'ana']) == 0
    revisar_csv(projeto, q2='E')
    assert main(['analyze', 'cebraspe', '--reuse-csv', '--candidate', 'ana']) == 0
    mtime = saida(projeto, 'relatorio.md').stat().st_mtime_ns

    assert main(['--candidate', 'ana']) == 0

    assert saida(projeto, 'relatorio.md').stat().st_mtime_ns == mtime


def test_trocar_a_folha_depois_da_revisao_avisa_e_mantem_a_revisao(projeto, caplog):
    assert main(['--candidate', 'ana']) == 0
    revisar_csv(projeto, q2='E')
    assert main(['analyze', 'cebraspe', '--reuse-csv', '--candidate', 'ana']) == 0
    revisados = acertos(projeto)

    gravar_folha(projeto, marcas(q1='E'))
    with caplog.at_level(logging.WARNING):
        assert main(['--candidate', 'ana']) == 0

    assert 'revisão antiga' in caplog.text
    assert acertos(projeto) == revisados


def test_reuse_csv_sem_csv_de_leitura_da_dica(projeto, capsys):
    assert main(['analyze', 'cebraspe', '--reuse-csv', '--candidate', 'ana']) != 0

    erro = capsys.readouterr().err
    assert 'respostas_extraidas.csv' in erro
    assert 'dica:' in erro
    assert not (projeto / 'provas/cebraspe/candidatos/ana/respostas_revisadas.csv').exists()


def test_reuse_csv_sem_concurso_da_dica(projeto, capsys):
    assert main(['analyze', '--reuse-csv', '--candidate', 'ana']) != 0

    assert 'dica:' in capsys.readouterr().err


def test_reuse_csv_invalido_nao_e_copiado(projeto, capsys):
    assert main(['--candidate', 'ana']) == 0
    revisar_csv(projeto, q2='X')

    assert main(['analyze', 'cebraspe', '--reuse-csv', '--candidate', 'ana']) != 0

    erro = capsys.readouterr().err
    assert "'X'" in erro and 'dica:' in erro
    assert not (projeto / 'provas/cebraspe/candidatos/ana/respostas_revisadas.csv').exists()


def test_csv_manual_sem_folha_roda_o_pipeline(projeto):
    pasta = projeto / 'provas' / 'cebraspe' / 'candidatos' / 'bia'
    pasta.mkdir()
    linhas = ''.join(f'{q},{"C" if q % 2 else "E"}\n' for q in range(1, 11))
    (pasta / 'respostas.csv').write_text(f'questao,alternativa\n{linhas}', encoding='utf-8')

    assert main(['--candidate', 'bia']) == 0

    assert acertos(projeto, 'bia') == 10
    respostas = ler_csv(saida(projeto, 'respostas_extraidas.csv', 'bia'))
    assert len(respostas) == TOTAL
    assert set(respostas['origem']) == {'manual'}
    assert saida(projeto, 'relatorio.md', 'bia').exists()
