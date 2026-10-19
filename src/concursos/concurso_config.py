from dataclasses import dataclass, field
from pathlib import Path

import yaml

from concursos.modelo import Formato, Pontuacao

ARQUIVO_CONFIG = 'concurso.yaml'


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
    status: str = 'definitivo'


@dataclass(frozen=True)
class ProvaConfig:
    chave: str
    gabarito: GabaritoConfig
    inicio: int
    fim: int
    disciplinas: tuple[FaixaDisciplina, ...] = ()

    @property
    def questoes(self) -> range:
        return range(self.inicio, self.fim + 1)

    def disciplina_de(self, questao: int) -> str:
        return next((f.disciplina for f in self.disciplinas if f.contem(questao)), 'nao_mapeado')


@dataclass(frozen=True)
class ConcursoConfig:
    nome: str
    pasta: Path
    banca: str
    formato: Formato
    pontuacao: Pontuacao
    provas: tuple[ProvaConfig, ...]
    cargo: str | None = None
    tipo: str | None = None
    respostas_arquivo: str | None = None
    ignorar: tuple[str, ...] = field(default_factory=tuple)

    def caminho(self, arquivo: str) -> Path:
        return self.pasta / arquivo

    def prova_da_questao(self, questao: int) -> ProvaConfig:
        return next(p for p in self.provas if questao in p.questoes)


def carregar_concurso(pasta: Path) -> ConcursoConfig:
    caminho = pasta / ARQUIVO_CONFIG
    if not caminho.exists():
        raise ArquivoAusenteError(f'{caminho}: arquivo de configuração ausente')
    dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    try:
        return _montar(pasta, dados)
    except (KeyError, TypeError, ValueError) as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro


def _montar(pasta: Path, dados: dict) -> ConcursoConfig:
    provas = tuple(_montar_prova(chave, valor) for chave, valor in dados['provas'].items())
    respostas = dados.get('respostas') or {}
    return ConcursoConfig(
        nome=dados.get('nome', pasta.name),
        pasta=pasta,
        banca=dados['banca'],
        formato=Formato(dados['formato']),
        pontuacao=Pontuacao(dados.get('pontuacao', 'simples')),
        provas=provas,
        cargo=dados.get('cargo'),
        tipo=None if dados.get('tipo') is None else str(dados['tipo']),
        respostas_arquivo=respostas.get('arquivo'),
        ignorar=tuple(dados.get('ignorar') or ()),
    )


def _montar_prova(chave: str, dados: dict) -> ProvaConfig:
    gabarito = dados['gabarito']
    if isinstance(gabarito, str):
        gabarito = {'arquivo': gabarito}
    inicio, fim = dados['itens']
    faixas = tuple(
        FaixaDisciplina(f['inicio'], f['fim'], f['disciplina']) for f in dados.get('disciplinas') or ()
    )
    return ProvaConfig(chave, GabaritoConfig(**gabarito), int(inicio), int(fim), faixas)
