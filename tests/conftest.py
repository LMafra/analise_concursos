import importlib.util
from pathlib import Path

import pandas as pd
import pytest
from concurso_sintetico import EDITAL_MINIMO, com_edital_minimo, criar_concurso  # noqa: F401

from concursos.cli import main
from concursos.erros import linhas_extras

# Sem o extra [gui], os testes da interface ficam de fora (a CLI não depende dele).
collect_ignore = [] if importlib.util.find_spec('nicegui') else ['gui']

# Candidato fixo: o layout multi-candidato grava em analises/<candidato>/<concurso>/.
CANDIDATO = 'candidato'


@pytest.fixture(autouse=True)
def home_isolada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / 'home_concurso'
    monkeypatch.setenv('GABARITO_VIVO_HOME', str(home))
    # Candidato via `--candidate` no helper `analisar`; forçar o env quebra fixtures
    # com outro slug e o layout plano das fases 1–3.
    monkeypatch.delenv('GABARITO_VIVO_CANDIDATO', raising=False)
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


def saida(analises: Path, *partes: str) -> Path:
    """Pasta (ou arquivo) da análise do candidato de teste."""
    return analises.joinpath(CANDIDATO, *partes)


def analisar(provas: Path, analises: Path, *extra: str) -> int:
    """Chama o comando moderno `analyze`; traduz flags do helper antigo (`--forcar`, `--concurso`)."""
    projeto = provas.parent
    args: list[str] = [
        '--candidate',
        CANDIDATO,
        '--data-dir',
        str(projeto / '.gabarito-vivo'),
        '--provas',
        str(provas),
        '--analises',
        str(analises),
    ]
    concurso: str | None = None
    i = 0
    while i < len(extra):
        flag = extra[i]
        if flag == '--forcar':
            args.append('--force')
        elif flag == '--concurso':
            i += 1
            concurso = extra[i]
        elif flag == '--config':
            i += 1
            _aplicar_config_legado(Path(extra[i]), projeto)
        else:
            args.append(flag)
        i += 1
    args.append('analyze')
    if concurso is not None:
        args.append(concurso)
    return main(args)


def _aplicar_config_legado(caminho: Path, projeto: Path) -> None:
    """O legado lia `config.yaml`; o app lê `[analise]` em `.gabarito-vivo/config.toml`."""
    import tomli_w
    import yaml

    dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    pasta = projeto / '.gabarito-vivo'
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / 'config.toml').write_text(tomli_w.dumps({'analise': dados}), encoding='utf-8')


def ler_csv(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, keep_default_na=False)


def log_completo(caplog: pytest.LogCaptureFixture) -> str:
    """O texto, a dica e o detalhe de cada registro; o `caplog.text` só traz o texto."""
    return '\n'.join('\n'.join([r.getMessage(), *linhas_extras(r)]) for r in caplog.records)
