from dataclasses import dataclass
from enum import StrEnum

LETRAS = 'ABCDEFGHIJ'
ALTERNATIVAS_PADRAO = 5


class Formato(StrEnum):
    MULTIPLA_ESCOLHA = 'multipla_escolha'
    CERTO_ERRADO = 'certo_errado'

    @property
    def alternativas(self) -> frozenset[str]:
        return self.letras()

    def letras(self, alternativas: int | None = None) -> frozenset[str]:
        """Certo/errado ignora o número; a múltipla escolha tem 5 alternativas quando ele não é dado."""
        if self is Formato.CERTO_ERRADO:
            return frozenset('CE')
        return frozenset(LETRAS[: alternativas or ALTERNATIVAS_PADRAO])


class Pontuacao(StrEnum):
    SIMPLES = 'simples'
    CEBRASPE = 'cebraspe'

    @property
    def fator_penalidade(self) -> float:
        return 1.0 if self is Pontuacao.CEBRASPE else 0.0


class StatusGabarito(StrEnum):
    PRELIMINAR = 'preliminar'
    DEFINITIVO = 'definitivo'


class Nivel(StrEnum):
    FEDERAL = 'federal'
    ESTADUAL = 'estadual'
    MUNICIPAL = 'municipal'
    NAO_INFORMADO = 'nao_informado'


class Escolaridade(StrEnum):
    SUPERIOR = 'superior'
    MEDIO = 'medio'
    NAO_INFORMADO = 'nao_informado'


class Bloco(StrEnum):
    GERAL = 'geral'
    ESPECIFICO = 'especifico'
    NAO_INFORMADO = 'nao_informado'


class ModeloCorrecao(StrEnum):
    BRUTA = 'bruta'
    LIQUIDA = 'liquida'
    PONDERADA = 'ponderada'

    @classmethod
    def pelo_fator(cls, fator: float, *, ponderada: bool = False) -> 'ModeloCorrecao':
        """Com penalidade é sempre líquida, mesmo com pesos; sem ela, ponderada se os pesos variam."""
        if fator > 0:
            return cls.LIQUIDA
        return cls.PONDERADA if ponderada else cls.BRUTA


class Estado(StrEnum):
    MARCADA = 'marcada'
    BRANCO = 'branco'
    MULTIPLA = 'multipla'


class Origem(StrEnum):
    MANUAL = 'manual'
    FOLHA = 'folha'
    REVISADA = 'revisada'


class Resultado(StrEnum):
    ACERTO = 'acerto'
    ERRO = 'erro'
    BRANCO = 'branco'


class FonteRecomendacao(StrEnum):
    """De onde veio uma recomendação de estudo, na ordem em que as camadas são tentadas."""

    LEGISLACAO = 'legislacao'
    LIVROS = 'livros'
    OPEN_NOTEBOOK = 'open_notebook'
    CATALOGO = 'catalogo'


class OrigemErroTec(StrEnum):
    """Como a extensão do TEC viu o erro: na hora em que ele aconteceu ou numa tela de questão já resolvida."""

    TEMPO_REAL = 'tempo_real'
    HISTORICO = 'historico'


class ModoCaderno(StrEnum):
    """Se o desempenho de um caderno do TEC conta desde o início (`tudo`) ou desde a primeira importação."""

    TUDO = 'tudo'
    DAQUI = 'daqui'


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


class DecisaoJanela(StrEnum):
    """Como a GUI abre; só `NAVEGADOR_SEM_WEBVIEW2` é uma queda que o usuário precisa entender."""

    NATIVA = 'nativa'
    NAVEGADOR_PEDIDO = 'navegador_pedido'
    NAVEGADOR_LINUX = 'navegador_linux'
    NAVEGADOR_SEM_WEBVIEW2 = 'navegador_sem_webview2'


class Etapa(StrEnum):
    LENDO_ARQUIVOS = 'lendo_arquivos'
    LENDO_FOLHA = 'lendo_folha'
    CORRIGINDO = 'corrigindo'
    CLASSIFICANDO = 'classificando'
    GERANDO_RELATORIOS = 'gerando_relatorios'
    CONSOLIDANDO = 'consolidando'


class CanalAtualizacao(StrEnum):
    STABLE = 'stable'
    BETA = 'beta'


class TemaGui(StrEnum):
    SISTEMA = 'sistema'
    CLARO = 'claro'
    ESCURO = 'escuro'


class EstadoLivro(StrEnum):
    NA_FILA = 'na_fila'
    LENDO = 'lendo'
    LIDO = 'lido'
    ENVIANDO = 'enviando'
    PRONTO = 'pronto'
    ERRO = 'erro'


class OndeProcurar(StrEnum):
    LIVROS = 'livros'
    ANALISES = 'analises'
    TUDO = 'tudo'


class TipoCampo(StrEnum):
    DATA = 'data'
    INTEIRO = 'inteiro'
    NUMERO = 'numero'
