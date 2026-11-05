import sys
from dataclasses import dataclass
from pathlib import Path

import concursos

PASTA_NO_EXECUTAVEL = 'tec-erros'
ARQUIVO_CADERNO = 'caderno.html'
ARQUIVO_USERSCRIPT = 'tec-erros.user.js'
PASTA_EXTENSAO = 'extensao-chrome'
INSTRUCOES = 'https://github.com/LMafra/analise_concursos/tree/main/tec-erros/docs'


@dataclass(frozen=True)
class CapturaTec:
    pasta: Path
    caderno: Path
    extensao: Path
    userscript: Path
    zip_extensao: Path | None


def candidatas() -> list[Path]:
    """No executável, o `dist/` do tec-erros vai junto; numa cópia do repositório, é o gerado pelo Node."""
    pastas = []
    if embutida := getattr(sys, '_MEIPASS', None):
        pastas.append(Path(embutida) / PASTA_NO_EXECUTAVEL)
    pastas.append(Path(concursos.__file__).resolve().parents[2] / 'tec-erros' / 'dist')
    return pastas


def localizar(pastas: list[Path] | None = None) -> CapturaTec | None:
    for pasta in candidatas() if pastas is None else pastas:
        if (pasta / ARQUIVO_CADERNO).is_file():
            zips = sorted(pasta.glob('tec-erros-extensao-*.zip'))
            return CapturaTec(
                pasta,
                pasta / ARQUIVO_CADERNO,
                pasta / PASTA_EXTENSAO,
                pasta / ARQUIVO_USERSCRIPT,
                zips[-1] if zips else None,
            )
    return None
