import logging
import threading
from collections import deque
from dataclasses import dataclass

from concursos.modelo import Etapa


@dataclass(frozen=True)
class Passo:
    concurso: str
    indice: int
    total: int

    @property
    def fracao(self) -> float:
        return (self.indice - 1) / self.total if self.total else 0.0


class Andamento:
    """Ponte entre a thread da análise e a tela: a thread escreve, um timer da tela lê.

    Os elementos da NiceGUI só podem ser mexidos no loop da interface, nunca da thread de trabalho.
    """

    def __init__(self, maximo_linhas: int = 2000) -> None:
        self._trava = threading.Lock()
        self._linhas: deque[str] = deque(maxlen=maximo_linhas)
        self.passo: Passo | None = None
        self.etapa: Etapa | None = None
        self.terminou = False

    def ao_progresso(self, concurso: str, indice: int, total: int) -> None:
        self.passo = Passo(concurso, indice, total)
        self.etapa = None

    def ao_etapa(self, _concurso: str, etapa: Etapa) -> None:
        self.etapa = etapa

    def escrever(self, linha: str) -> None:
        with self._trava:
            self._linhas.append(linha)

    def retirar_linhas(self) -> list[str]:
        with self._trava:
            linhas = list(self._linhas)
            self._linhas.clear()
        return linhas


class HandlerDoPainel(logging.Handler):
    """Manda o log do pacote para o painel "Log detalhado" enquanto a análise roda."""

    def __init__(self, andamento: Andamento, nivel: int = logging.INFO) -> None:
        super().__init__(nivel)
        self.andamento = andamento
        self.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s', '%H:%M:%S'))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.andamento.escrever(self.format(record))
        except Exception:  # noqa: BLE001
            self.handleError(record)


def arquivo_de_log() -> str | None:
    """O arquivo que a CLI configurou em `~/.concurso/logs/`, se houver."""
    for handler in logging.getLogger('concursos').handlers:
        if isinstance(handler, logging.FileHandler):
            return handler.baseFilename
    return None
