"""Tipos e erros do `concurso.yaml`."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from concursos.modelo import (
    Escolaridade,
    Formato,
    ModeloCorrecao,
    Nivel,
    Pontuacao,
    StatusGabarito,
)
from concursos.perfis import perfil_da_banca


class _CarregadorSemDatas(yaml.SafeLoader):
    """Datas chegam como texto, para que uma data inválida vire erro de validação com o nome do campo."""


_CarregadorSemDatas.yaml_implicit_resolvers = {
    inicial: [(tag, padrao) for tag, padrao in resolvedores if tag != 'tag:yaml.org,2002:timestamp']
    for inicial, resolvedores in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_DATA_ISO = re.compile(r'\d{4}-\d{2}-\d{2}')


class ConfiguracaoInvalidaError(ValueError):
    pass


class ArquivoAusenteError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class FaixaDisciplina:
    inicio: int
    fim: int
    disciplina: str

    def contem(self, questao: int) -> bool:
        return self.inicio <= questao <= self.fim


@dataclass(frozen=True)
class GabaritoConfig:
    arquivo: str
    status: StatusGabarito = StatusGabarito.DEFINITIVO


@dataclass(frozen=True)
class EditalConfig:
    arquivo: str | None
    anexos: tuple[str, ...] = ()
    manual: str | None = None
    retificacoes: tuple[str, ...] = ()

    @property
    def documentos(self) -> list[str]:
        """Anexos primeiro: em editais fragmentados (CPNU), o conteúdo programático fica no anexo."""
        return [*self.anexos, *([self.arquivo] if self.arquivo else [])]

    @property
    def arquivos(self) -> list[str]:
        return [*self.documentos, *self.retificacoes, *([self.manual] if self.manual else [])]


@dataclass(frozen=True)
class FolhaConfig:
    arquivo: str
    template: str | None
    total_itens: int | None = None
    itens_por_coluna: int | None = None


@dataclass(frozen=True)
class PesoItens:
    inicio: int
    fim: int
    peso: float


def peso_da_questao(pesos: tuple[PesoItens, ...], questao: int) -> float:
    """Itens fora de todas as faixas valem 1."""
    return next((p.peso for p in pesos if p.inicio <= questao <= p.fim), 1.0)


def pesos_variam(pesos: tuple[PesoItens, ...]) -> bool:
    return any(p.peso != 1 for p in pesos)


@dataclass(frozen=True)
class ResultadoOficialConfig:
    arquivo: str
    identificador: str | None = None
    pesos: tuple[PesoItens, ...] = ()

    def peso_de(self, questao: int) -> float:
        return peso_da_questao(self.pesos, questao)


@dataclass(frozen=True)
class VarianteCorrecaoConfig:
    """Opção de cargo com pesos próprios (no CPNU, o código do cargo); sem pesos, eles vêm do edital."""

    nome: str
    pesos: tuple[PesoItens, ...] = ()


@dataclass(frozen=True)
class CorrecaoConfig:
    """Regra de correção declarada; complementa ou substitui a extraída do edital."""

    modelo: ModeloCorrecao | None = None
    fator_penalidade: float | None = None
    nota_maxima: float | None = None
    nota_corte: float | None = None
    pesos: tuple[PesoItens, ...] = ()
    variantes: tuple[VarianteCorrecaoConfig, ...] = ()

    @property
    def define_regra(self) -> bool:
        return self.modelo is not None or self.fator_penalidade is not None or bool(self.pesos)


@dataclass(frozen=True)
class ProvaConfig:
    chave: str
    gabarito: GabaritoConfig
    inicio: int
    fim: int
    disciplinas: tuple[FaixaDisciplina, ...] = ()
    caderno: str | None = None

    @property
    def questoes(self) -> range:
        return range(self.inicio, self.fim + 1)

    @property
    def caderno_pdf(self) -> bool:
        return bool(self.caderno) and self.caderno.lower().endswith('.pdf')

    def disciplina_de(self, questao: int) -> str:
        return next((f.disciplina for f in self.disciplinas if f.contem(questao)), 'nao_mapeado')


@dataclass(frozen=True)
class SimuladoConfig:
    """Prova anterior resolvida como treino; o edital, se houver, é o do alvo e serve só para os tópicos."""

    fonte: str
    id_pci: int | None = None
    ano_original: int | None = None
    organizadora: str = ''
    orgao: str = ''
    descricao: str = ''
    link: str = ''
    concurso_alvo: str | None = None
    cargo_alvo: str | None = None


@dataclass(frozen=True)
class ConcursoConfig:
    nome: str
    pasta: Path
    banca: str
    formato: Formato
    pontuacao: Pontuacao
    provas: tuple[ProvaConfig, ...]
    alternativas: int | None = None
    cargo: str | None = None
    tipo: str | None = None
    respostas_arquivo: str | None = None
    folha: FolhaConfig | None = None
    edital: EditalConfig | None = None
    resultado_oficial: ResultadoOficialConfig | None = None
    correcao: CorrecaoConfig | None = None
    data_prova: date | None = None
    nivel: Nivel = Nivel.NAO_INFORMADO
    escolaridade: Escolaridade = Escolaridade.NAO_INFORMADO
    ignorar: tuple[str, ...] = ()
    historico: tuple[dict, ...] = ()
    simulado: SimuladoConfig | None = None
    titulo: str | None = None
    """O nome mostrado, corrigido pelo usuário; vence o do edital."""
    pci_titulo: str | None = None

    def caminho(self, arquivo: str) -> Path:
        return self.pasta / arquivo

    @property
    def arquivos_referenciados(self) -> dict[str, str]:
        """Cada arquivo que o `concurso.yaml` cita, com o papel dele (caminho relativo à pasta)."""
        referenciados = {}
        for prova in self.provas:
            referenciados[prova.gabarito.arquivo] = f'gabarito da prova {prova.chave}'
            if prova.caderno:
                referenciados[prova.caderno] = f'caderno da prova {prova.chave}'
        if self.respostas_arquivo:
            referenciados[self.respostas_arquivo] = 'respostas'
        if self.folha:
            referenciados[self.folha.arquivo] = 'folha de resposta'
        for arquivo in self.edital.arquivos if self.edital else ():
            referenciados[arquivo] = 'edital'
        if self.resultado_oficial:
            referenciados[self.resultado_oficial.arquivo] = 'resultado oficial'
        return referenciados

    @property
    def status_gabarito(self) -> str:
        estados = {prova.gabarito.status for prova in self.provas}
        return estados.pop() if len(estados) == 1 else 'misto'

    def prova_da_questao(self, questao: int) -> ProvaConfig:
        return next(p for p in self.provas if questao in p.questoes)

    @property
    def total_itens(self) -> int:
        return sum(len(prova.questoes) for prova in self.provas)

    @property
    def n_alternativas(self) -> int | None:
        """O do concurso; sem ele, o do perfil da banca; sem os dois, o padrão do formato."""
        return self.alternativas or perfil_da_banca(self.banca).alternativas
