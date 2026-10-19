from pathlib import Path

import pandas as pd
import pytest
import yaml

from concursos.cli import main


@pytest.fixture
def raizes(tmp_path: Path) -> tuple[Path, Path]:
    provas = tmp_path / 'provas'
    analises = tmp_path / 'analises'
    provas.mkdir()
    return provas, analises


def criar_concurso(provas: Path, nome: str, config: dict, arquivos: dict[str, str]) -> Path:
    pasta = provas / nome
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / 'concurso.yaml').write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')
    for nome_arquivo, conteudo in arquivos.items():
        (pasta / nome_arquivo).write_text(conteudo, encoding='utf-8')
    return pasta


def analisar(provas: Path, analises: Path, *extra: str) -> int:
    return main(['analisar', '--provas', str(provas), '--analises', str(analises), *extra])


def ler_csv(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, keep_default_na=False)
