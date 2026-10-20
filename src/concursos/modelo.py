from dataclasses import dataclass
from enum import StrEnum


class Formato(StrEnum):
    MULTIPLA_ESCOLHA = 'multipla_escolha'
    CERTO_ERRADO = 'certo_errado'

    @property
    def alternativas(self) -> frozenset[str]:
        if self is Formato.CERTO_ERRADO:
            return frozenset('CE')
        return frozenset('ABCDE')


class Pontuacao(StrEnum):
    SIMPLES = 'simples'
    CEBRASPE = 'cebraspe'

    @property
    def fator_penalidade(self) -> float:
        return 1.0 if self is Pontuacao.CEBRASPE else 0.0


class ModeloCorrecao(StrEnum):
    BRUTA = 'bruta'
    LIQUIDA = 'liquida'
    PONDERADA = 'ponderada'

    @classmethod
    def pelo_fator(cls, fator: float) -> 'ModeloCorrecao':
        return cls.LIQUIDA if fator > 0 else cls.BRUTA


class Estado(StrEnum):
    MARCADA = 'marcada'
    BRANCO = 'branco'
    MULTIPLA = 'multipla'


class Origem(StrEnum):
    MANUAL = 'manual'
    FOLHA = 'folha'


class Resultado(StrEnum):
    ACERTO = 'acerto'
    ERRO = 'erro'
    BRANCO = 'branco'


@dataclass(frozen=True)
class RespostaMarcada:
    questao: int
    alternativa: str | None
    estado: Estado
    confianca: float
    origem: Origem
    arquivo: str
    pagina: int | None = None


@dataclass(frozen=True)
class ItemGabarito:
    questao: int
    resposta: str | None
    anulada: bool = False
