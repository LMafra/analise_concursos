import math
import sys
import types
from pathlib import Path

import pandas as pd
import pytest
from consolidado_sintetico import concurso, consolidado

from concursos.aplicacao.resultados import (
    PontoDeNota,
    ResumoVisual,
    _fracos,
    _pontos,
    relatorios_disponiveis,
    resumo_visual,
)
from concursos.config.contexto import Contexto
from concursos.gui.componentes import resumo_visual as visual
from concursos.gui.componentes import seletor_pasta, toasts


def _contexto(tmp_path: Path) -> Contexto:
    projeto = tmp_path / 'proj'
    provas = projeto / 'provas'
    analises = projeto / 'analises' / 'ana'
    analises.mkdir(parents=True)
    provas.mkdir(parents=True)
    return Contexto(tmp_path, tmp_path / 'home', projeto, provas, analises)


def test_pontos_escolhe_o_melhor_gap_por_concurso() -> None:
    tabela = pd.DataFrame(
        [
            {
                'concurso': 'alfa',
                'ordem': 1,
                'percentual_ponderado': 65.0,
                'menor_gap_percentual': -2.0,
                'atingido': False,
            },
            {
                'concurso': 'alfa',
                'ordem': 1,
                'percentual_ponderado': 60.0,
                'menor_gap_percentual': -10.0,
                'atingido': False,
            },
            {
                'concurso': 'beta',
                'ordem': 2,
                'percentual_ponderado': float('nan'),
                'menor_gap_percentual': 1.0,
                'atingido': True,
            },
            {
                'concurso': 'beta',
                'ordem': 2,
                'percentual_ponderado': 80.0,
                'menor_gap_percentual': float('nan'),
                'atingido': True,
            },
        ]
    )

    pontos = _pontos(tabela)

    assert [ponto.concurso for ponto in pontos] == ['alfa', 'beta']
    assert pontos[0].nota == 60.0
    assert pontos[0].corte == 70.0
    assert pontos[1].corte is None
    assert pontos[1].atingido is True


def test_fracos_pega_os_tres_piores() -> None:
    assert _fracos(pd.DataFrame(columns=['disciplina', 'topico', 'percentual'])) == ()

    tabela = pd.DataFrame(
        [
            {'disciplina': 'A', 'topico': 't1', 'percentual': 40.0},
            {'disciplina': 'B', 'topico': 't2', 'percentual': 10.0},
            {'disciplina': 'C', 'topico': 't3', 'percentual': 30.0},
            {'disciplina': 'D', 'topico': 't4', 'percentual': 50.0},
        ]
    )
    fracos = _fracos(tabela)
    assert [item.topico for item in fracos] == ['t2', 't3', 't1']


def test_resumo_visual_sem_parquet_fica_vazio(tmp_path) -> None:
    assert resumo_visual(_contexto(tmp_path)) == ResumoVisual()


def test_resumo_visual_com_parquet_vazio_fica_vazio(tmp_path) -> None:
    from concursos.analytics.consolidado import ARQUIVO_PARQUET, pasta_consolidado

    contexto = _contexto(tmp_path)
    cache = pasta_consolidado(contexto.analises)
    cache.mkdir(parents=True)
    pd.DataFrame().to_parquet(cache / ARQUIVO_PARQUET)
    assert resumo_visual(contexto) == ResumoVisual()


def test_resumo_visual_com_parquet_invalido_fica_vazio(tmp_path) -> None:
    from concursos.analytics.consolidado import ARQUIVO_PARQUET, pasta_consolidado

    contexto = _contexto(tmp_path)
    cache = pasta_consolidado(contexto.analises)
    cache.mkdir(parents=True)
    (cache / ARQUIVO_PARQUET).write_bytes(b'nao-e-parquet')
    assert resumo_visual(contexto) == ResumoVisual()


def test_resumo_visual_le_o_consolidado(tmp_path) -> None:
    from concursos.analytics.consolidado import ARQUIVO_PARQUET, pasta_consolidado

    contexto = _contexto(tmp_path)
    cache = pasta_consolidado(contexto.analises)
    cache.mkdir(parents=True)
    tabela = consolidado(
        concurso('alfa', ['acerto', 'erro', 'acerto', 'branco', 'acerto'], ordem=1),
        concurso('beta', ['acerto', 'acerto', 'erro', 'acerto', 'acerto'], ordem=2),
    )
    tabela.to_parquet(cache / ARQUIVO_PARQUET)
    resumo = resumo_visual(contexto)
    assert [ponto.concurso for ponto in resumo.pontos] == ['alfa', 'beta']
    assert resumo.pontos[0].nota < resumo.pontos[1].nota


def test_relatorios_disponiveis_lista_indice_e_concursos(tmp_path) -> None:
    from concursos.relatorio_html import ARQUIVO_INDICE, ARQUIVO_RELATORIO_HTML

    contexto = _contexto(tmp_path)
    analises = contexto.analises
    assert relatorios_disponiveis(contexto) == []

    (analises / ARQUIVO_INDICE).write_text('<html></html>', encoding='utf-8')
    concurso_pasta = analises / 'alfa'
    concurso_pasta.mkdir()
    (concurso_pasta / ARQUIVO_RELATORIO_HTML).write_text('<html></html>', encoding='utf-8')
    opcoes = relatorios_disponiveis(contexto)
    assert [item.rotulo for item in opcoes] == ['Visão geral', 'alfa']


def test_tendencia_com_tres_provas() -> None:
    pontos = (
        PontoDeNota('a', 1, 50.0, 60.0, False),
        PontoDeNota('b', 2, 55.0, 60.0, False),
        PontoDeNota('c', 3, 70.0, 60.0, True),
        PontoDeNota('d', 4, 72.0, 60.0, True),
    )
    texto, _ = visual._tendencia(pontos)
    assert 'pontos percentuais' in texto


def test_tendencia_queda_e_estavel() -> None:
    queda = tuple(
        PontoDeNota(n, i, nota, 60.0, nota >= 60)
        for i, (n, nota) in enumerate(
            [('a', 80.0), ('b', 75.0), ('c', 50.0), ('d', 45.0)],
            start=1,
        )
    )
    texto, _ = visual._tendencia(queda)
    assert texto.startswith('↘')
    estavel = tuple(PontoDeNota(n, i, 60.0, 60.0, True) for i, n in enumerate(['a', 'b', 'c', 'd'], start=1))
    assert visual._tendencia(estavel)[0] == 'Estável'
    amostra = (PontoDeNota('a', 1, 50.0, None, None), PontoDeNota('b', 2, 55.0, None, None))
    assert visual._tendencia(amostra)[0] == 'Amostra inicial'


def test_escala_aperta_intervalo_pequeno() -> None:
    minimo, maximo, marcas = visual._escala([48.0, 52.0])
    assert maximo - minimo >= 10
    assert marcas
    assert math.isclose(minimo, float(marcas[0]))


def test_ultimo_do_resumo() -> None:
    resumo = ResumoVisual(pontos=(PontoDeNota('a', 1, 10.0, None, None),))
    assert visual.ultimo(resumo).concurso == 'a'
    assert visual.ultimo(ResumoVisual()) is None


def test_toasts_notificam(monkeypatch) -> None:
    avisos: list[tuple] = []
    destinos: list[str] = []
    monkeypatch.setattr(toasts.ui, 'notify', lambda *a, **k: avisos.append((a, k)))
    monkeypatch.setattr(toasts.ui, 'navigate', types.SimpleNamespace(to=destinos.append))

    class DialogoFalso:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def open(self):
            return None

        def close(self):
            return None

    class CardFalso:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class RowFalso:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(toasts.ui, 'dialog', DialogoFalso)
    monkeypatch.setattr(toasts.ui, 'card', CardFalso)
    monkeypatch.setattr(toasts.ui, 'row', RowFalso)
    monkeypatch.setattr(toasts.ui, 'label', lambda *a, **k: None)
    monkeypatch.setattr(
        toasts.ui,
        'button',
        lambda *a, **k: types.SimpleNamespace(props=lambda *x, **y: None),
    )

    toasts.sucesso('ok')
    toasts.erro('falhou')
    toasts.com_desfazer('apagado', lambda: None)
    toasts.sujo_ao_sair(lambda: False, '/inicio')
    toasts.sujo_ao_sair(lambda: True, '/inicio')

    assert len(avisos) == 3
    assert destinos == ['/inicio']


@pytest.mark.asyncio
async def test_escolher_pasta_na_janela_nativa(tmp_path, monkeypatch) -> None:
    class Janela:
        async def create_file_dialog(self, *a, **k):
            return [str(tmp_path / 'escolhida')]

    (tmp_path / 'escolhida').mkdir()
    monkeypatch.setattr(seletor_pasta.app.native, 'main_window', Janela(), raising=False)
    fake = types.ModuleType('webview')
    fake.FileDialog = types.SimpleNamespace(FOLDER='FOLDER')
    monkeypatch.setitem(sys.modules, 'webview', fake)

    assert await seletor_pasta.escolher_pasta(tmp_path) == tmp_path / 'escolhida'


@pytest.mark.asyncio
async def test_escolher_pasta_cancela_na_janela_nativa(tmp_path, monkeypatch) -> None:
    class Janela:
        async def create_file_dialog(self, *a, **k):
            return None

    monkeypatch.setattr(seletor_pasta.app.native, 'main_window', Janela(), raising=False)
    fake = types.ModuleType('webview')
    fake.FileDialog = types.SimpleNamespace(FOLDER='FOLDER')
    monkeypatch.setitem(sys.modules, 'webview', fake)

    assert await seletor_pasta.escolher_pasta(tmp_path) is None
