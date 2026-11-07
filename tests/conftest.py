import importlib.util
from pathlib import Path

import pandas as pd
import pytest
from concurso_sintetico import EDITAL_MINIMO, com_edital_minimo, criar_concurso  # noqa: F401

from concursos.cli import main
from concursos.erros import linhas_extras

# Sem o extra [gui], os testes da interface ficam de fora (a CLI não depende dele).
collect_ignore = [] if importlib.util.find_spec('nicegui') else ['gui']


@pytest.fixture(autouse=True)
def home_isolada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / 'home_concurso'
    monkeypatch.setenv('CONCURSO_HOME', str(home))
    return home


@pytest.fixture(autouse=True)
def navegador(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Os relatórios que a CLI abriria no navegador; nenhum teste abre um de verdade."""
    abertos: list[Path] = []
    monkeypatch.setattr('concursos.relatorio_html.abrir_no_navegador', abertos.append)
    return abertos


@pytest.fixture(autouse=True)
def sem_rede_pci(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum teste fala com o servidor real do PCI; quem precisa troca por um transporte falso."""

    def recusar(configuracao):
        raise AssertionError('teste tentou abrir o transporte real do PCI')

    monkeypatch.setattr('concursos.integracoes.pci_mcp.abrir_transporte', recusar)


@pytest.fixture
def raizes(tmp_path: Path) -> tuple[Path, Path]:
    provas = tmp_path / 'provas'
    analises = tmp_path / 'analises'
    provas.mkdir()
    return provas, analises


def analisar(provas: Path, analises: Path, *extra: str) -> int:
    return main(['analisar', '--provas', str(provas), '--analises', str(analises), *extra])


def ler_csv(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, keep_default_na=False)


def log_completo(caplog: pytest.LogCaptureFixture) -> str:
    """O texto, a dica e o detalhe de cada registro; o `caplog.text` só traz o texto."""
    return '\n'.join('\n'.join([r.getMessage(), *linhas_extras(r)]) for r in caplog.records)
