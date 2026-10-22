import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

VARIAVEL_HOME = 'CONCURSO_HOME'
PASTA_HOME = '.concurso'
PASTA_PROJETO = '.concurso'
PASTA_PROVAS = 'provas'
PASTA_ANALISES = 'analises'


@dataclass(frozen=True)
class Contexto:
    """Todos os caminhos de uma execução; nenhum outro módulo decide onde ler ou gravar."""

    raiz: Path
    home: Path
    projeto: Path
    provas: Path
    analises: Path

    @property
    def logs(self) -> Path:
        return self.home / 'logs'


def resolver_home(ambiente: Mapping[str, str] | None = None) -> Path:
    ambiente = os.environ if ambiente is None else ambiente
    if valor := ambiente.get(VARIAVEL_HOME):
        return Path(valor).expanduser()
    return Path.home() / PASTA_HOME


def resolver_contexto(
    *,
    cwd: Path | None = None,
    data_dir: Path | None = None,
    provas: Path | None = None,
    analises: Path | None = None,
    ambiente: Mapping[str, str] | None = None,
) -> Contexto:
    raiz = (cwd or Path.cwd()).resolve()
    return Contexto(
        raiz=raiz,
        home=resolver_home(ambiente),
        projeto=_absoluto(data_dir, raiz) if data_dir else raiz / PASTA_PROJETO,
        provas=_absoluto(provas, raiz) if provas else raiz / PASTA_PROVAS,
        analises=_absoluto(analises, raiz) if analises else raiz / PASTA_ANALISES,
    )


def _absoluto(caminho: Path, raiz: Path) -> Path:
    caminho = caminho.expanduser()
    return caminho if caminho.is_absolute() else raiz / caminho
