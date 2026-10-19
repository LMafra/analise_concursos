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
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
        return _montar(pasta, dados)
    except (yaml.YAMLError, KeyError, TypeError, ValueError) as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro


def _montar(pasta: Path, dados: dict) -> ConcursoConfig:
    provas = tuple(_montar_prova(chave, valor) for chave, valor in _obrigatorio(dados, 'provas').items())
    _validar_faixas_disjuntas(provas)
    respostas = dados.get('respostas') or {}
    return ConcursoConfig(
        nome=dados.get('nome', pasta.name),
        pasta=pasta,
        banca=_obrigatorio(dados, 'banca'),
        formato=_enum(Formato, _obrigatorio(dados, 'formato'), 'formato'),
        pontuacao=_enum(Pontuacao, dados.get('pontuacao', 'simples'), 'pontuacao'),
        provas=provas,
        cargo=dados.get('cargo'),
        tipo=None if dados.get('tipo') is None else str(dados['tipo']),
        respostas_arquivo=respostas.get('arquivo'),
        ignorar=tuple(dados.get('ignorar') or ()),
    )


def _montar_prova(chave: str, dados: dict) -> ProvaConfig:
    gabarito = _obrigatorio(dados, 'gabarito', f'provas.{chave}.')
    if isinstance(gabarito, str):
        gabarito = {'arquivo': gabarito}
    inicio, fim = _obrigatorio(dados, 'itens', f'provas.{chave}.')
    faixas = tuple(
        FaixaDisciplina(f['inicio'], f['fim'], f['disciplina']) for f in dados.get('disciplinas') or ()
    )
    return ProvaConfig(chave, GabaritoConfig(**gabarito), int(inicio), int(fim), faixas)


def _obrigatorio(dados: dict, campo: str, prefixo: str = ''):
    if dados.get(campo) in (None, ''):
        raise ConfiguracaoInvalidaError(f"campo obrigatório '{prefixo}{campo}' ausente")
    return dados[campo]


def _enum(tipo, valor, campo: str):
    try:
        return tipo(valor)
    except ValueError:
        opcoes = ', '.join(item.value for item in tipo)
        raise ConfiguracaoInvalidaError(f"{campo}: valor '{valor}' inválido (use {opcoes})") from None


def _validar_faixas_disjuntas(provas: tuple[ProvaConfig, ...]) -> None:
    ordenadas = sorted(provas, key=lambda p: p.inicio)
    for anterior, seguinte in zip(ordenadas, ordenadas[1:], strict=False):
        if seguinte.inicio <= anterior.fim:
            raise ConfiguracaoInvalidaError(
                f'faixas de itens sobrepostas: {anterior.chave} ({anterior.inicio}-{anterior.fim}) '
                f'e {seguinte.chave} ({seguinte.inicio}-{seguinte.fim})'
            )
