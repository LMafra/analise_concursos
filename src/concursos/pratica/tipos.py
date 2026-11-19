from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ConfiguracaoPratica:
    entrada: Path
    candidato: str | None = None
    open_notebook: bool = False


@dataclass
class Pratica:
    erros: list[dict] = field(default_factory=list)
    cadernos: list[dict] = field(default_factory=list)
    estado: dict = field(default_factory=dict)


@dataclass
class Escolhas:
    """O que foi decidido uma vez e vale para as próximas importações (`.concurso/pratica_tec.yaml`)."""

    aliases: dict[str, str | None] = field(default_factory=dict)
    materias: dict[str, str] = field(default_factory=dict)
    cadernos: dict[str, dict] = field(default_factory=dict)
    planilhas: dict[str, dict] = field(default_factory=dict)


@dataclass
class Pendencia:
    assunto: str
    disciplina: str | None
    sugestao: str | None
    score: float


@dataclass
class ResultadoPratica:
    mudou: bool
    avisos: list[str]
    pratica: Pratica
    escolhas: Escolhas
    disciplinas: dict[str, str | None]