from pathlib import Path

import pandas as pd
import pytest
import yaml

from concursos.cli import main


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


EDITAL_MINIMO = 'conhecimentos: []\n'


def com_edital_minimo(pasta: Path, config: dict) -> dict:
    """Concurso sem edital fica incompleto; o manual mínimo não traz regra nem tópico."""
    if 'edital' in config:
        return config
    (pasta / 'edital_manual.yaml').write_text(EDITAL_MINIMO, encoding='utf-8')
    return {**config, 'edital': {'manual': 'edital_manual.yaml'}}


def criar_concurso(provas: Path, nome: str, config: dict, arquivos: dict[str, str]) -> Path:
    pasta = provas / nome
    pasta.mkdir(parents=True, exist_ok=True)
    config = com_edital_minimo(pasta, config)
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')
    for nome_arquivo, conteudo in arquivos.items():
        (pasta / nome_arquivo).write_text(conteudo, encoding='utf-8')
    return pasta


def analisar(provas: Path, analises: Path, *extra: str) -> int:
    return main(['analisar', '--provas', str(provas), '--analises', str(analises), *extra])


def ler_csv(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, keep_default_na=False)
