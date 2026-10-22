import io
from pathlib import Path

import cv2
import pytest
import yaml
from conftest import criar_concurso, ler_csv
from folha_sintetica import folha_generica

from concursos.calibracao import ARQUIVO_CALIBRADO, CalibracaoError, calibrar
from concursos.cli import main
from concursos.folha import ler_folha
from concursos.migracao import candidato_padrao

TOTAL = 40
MARCAS = {q: 'ABCD'[(q * 3) % 4] for q in range(1, TOTAL + 1)}
PRIMEIRAS = ''.join(MARCAS[q] for q in range(1, 6))


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def folha_fraca(tmp_path: Path) -> Path:
    caminho = tmp_path / 'amostra.png'
    cv2.imwrite(str(caminho), folha_generica('ABCD', {}, TOTAL, 15, fracas=MARCAS))
    return caminho


def lidas(caminho: Path, pasta: Path, calibrado=None) -> str:
    respostas = ler_folha(caminho, None, TOTAL, None, pasta, 0.75, alternativas='ABCD', calibrado=calibrado)
    return ''.join(r.alternativa or '-' for r in respostas)


def test_calibracao_ajusta_o_limiar_e_a_folha_fraca_passa_a_ser_lida(folha_fraca, tmp_path):
    esperado = ''.join(MARCAS[q] for q in range(1, TOTAL + 1))
    assert lidas(folha_fraca, tmp_path)[:5] != PRIMEIRAS

    calibracao = calibrar(folha_fraca, PRIMEIRAS)

    assert calibracao.perfil.alternativas == 'ABCD'
    assert calibracao.perfil.limiar_marcada != 0.5
    assert lidas(folha_fraca, tmp_path, calibracao.perfil) == esperado
    assert calibracao.depuracao.ndim == 3


def test_letra_fora_da_grade_reprova(folha_fraca):
    with pytest.raises(CalibracaoError, match='4 alternativas'):
        calibrar(folha_fraca, 'EEEEE')


def test_respostas_que_contradizem_a_folha_reprovam(folha_fraca):
    trocadas = ''.join('ABCD'[('ABCD'.index(letra) + 1) % 4] for letra in PRIMEIRAS)

    with pytest.raises(CalibracaoError, match='não batem'):
        calibrar(folha_fraca, trocadas)


def test_respostas_em_formato_invalido_reprovam(folha_fraca):
    with pytest.raises(CalibracaoError, match='5 primeiras'):
        calibrar(folha_fraca, 'AB')


CONFIG = {
    'banca': 'generic',
    'formato': 'multipla_escolha',
    'alternativas': 4,
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, TOTAL]}},
    'respostas': {'folha': 'folha.png', 'total_itens': TOTAL},
}


@pytest.fixture
def projeto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, folha_fraca: Path) -> Path:
    raiz = tmp_path / 'projeto'
    raiz.mkdir()
    monkeypatch.chdir(raiz)
    monkeypatch.setenv('CONCURSO_DOCTOR', '0')
    pasta = criar_concurso(
        raiz / 'provas',
        'ficticia',
        CONFIG,
        {'gabarito.txt': ''.join(f'{q} A\n' for q in range(1, TOTAL + 1))},
    )
    cv2.imwrite(str(pasta / 'folha.png'), cv2.imread(str(folha_fraca)))
    monkeypatch.setenv('CONCURSO_CALIBRAR_FOLHA', str(folha_fraca))
    return raiz


def test_perfil_calibrado_e_usado_nas_leituras_do_projeto(projeto, monkeypatch):
    monkeypatch.setenv('CONCURSO_CALIBRAR_RESPOSTAS', PRIMEIRAS.lower())

    assert main(['--yes', 'init']) == 0

    calibrado = yaml.safe_load((projeto / '.concurso' / ARQUIVO_CALIBRADO).read_text(encoding='utf-8'))
    assert calibrado['alternativas'] == 'ABCD'
    assert (projeto / '.concurso' / 'calibracao.png').exists()
    respostas = ler_csv(projeto / 'analises' / candidato_padrao() / 'ficticia' / 'respostas_extraidas.csv')
    assert ''.join(respostas['alternativa_marcada']) == ''.join(MARCAS[q] for q in range(1, TOTAL + 1))


def test_calibracao_reprovada_nao_grava_nada(projeto, monkeypatch, capsys):
    monkeypatch.setenv('CONCURSO_CALIBRAR_RESPOSTAS', 'DDDDD' if PRIMEIRAS != 'DDDDD' else 'AAAAA')

    assert main(['--yes', 'init']) == 1

    assert 'dica:' in capsys.readouterr().err
    assert not (projeto / '.concurso').exists()


def test_no_wizard_a_calibracao_reprovada_explica_e_pergunta_de_novo(
    projeto, folha_fraca, monkeypatch, capsys
):
    monkeypatch.delenv('CONCURSO_CALIBRAR_FOLHA')
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.setattr('sys.stdin', Terminal(f'\n\n\n{folha_fraca}\nEEEEE\n{folha_fraca}\n{PRIMEIRAS}\n\n'))

    assert main([]) == 0

    saida = capsys.readouterr().out
    assert 'erro: você digitou E' in saida and 'dica:' in saida
    assert 'Calibração aprovada' in saida
    assert (projeto / '.concurso' / ARQUIVO_CALIBRADO).exists()
