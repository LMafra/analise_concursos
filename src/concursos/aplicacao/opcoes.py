from collections.abc import Callable
from dataclasses import dataclass

from concursos.assistente import Interacao, InteracaoAutomatica
from concursos.config.contexto import Contexto
from concursos.modelo import Etapa

Saida = Callable[[str], None]
Progresso = Callable[[str, int, int], None]
AoEtapa = Callable[[str, Etapa], None]


def descartar(_texto: str) -> None:
    return None


@dataclass(frozen=True)
class Opcoes:
    """`saida` recebe as mensagens para o usuário; `interacao` é None quando não há a quem perguntar."""

    contexto: Contexto
    sim: bool = False
    dry_run: bool = False
    forcar: bool = False
    todos: bool = False
    abrir: bool = True
    llm: bool = True
    rede: bool = True
    fornecidos: frozenset[str] = frozenset()
    saida: Saida = descartar
    interacao: Interacao | None = None
    ao_progresso: Progresso | None = None
    ao_etapa: AoEtapa | None = None

    def interacao_ou_automatica(self) -> Interacao:
        return self.interacao if self.interacao is not None else InteracaoAutomatica()
