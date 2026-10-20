from dataclasses import dataclass, field
from pathlib import Path

import yaml

from concursos.modelo import Formato, ModeloCorrecao, Pontuacao

ARQUIVO_CONFIG = 'concurso.yaml'
BANCAS = ('cebraspe', 'fgv', 'selecon', 'quadrix')
STATUS_GABARITO = ('preliminar', 'definitivo')
MODELOS_DECLARAVEIS = (ModeloCorrecao.BRUTA, ModeloCorrecao.LIQUIDA)


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
class EditalConfig:
    arquivo: str | None
    anexos: tuple[str, ...] = ()
    manual: str | None = None

    @property
    def documentos(self) -> list[str]:
        """Anexos primeiro: em editais fragmentados (CPNU), o conteúdo programático fica no anexo."""
        return [*self.anexos, *([self.arquivo] if self.arquivo else [])]


@dataclass(frozen=True)
class FolhaConfig:
    arquivo: str
    template: str
    total_itens: int | None = None
    itens_por_coluna: int | None = None


@dataclass(frozen=True)
class PesoItens:
    inicio: int
    fim: int
    peso: float


@dataclass(frozen=True)
class ResultadoOficialConfig:
    arquivo: str
    identificador: str | None = None
    pesos: tuple[PesoItens, ...] = ()

    def peso_de(self, questao: int) -> float:
        return next((p.peso for p in self.pesos if p.inicio <= questao <= p.fim), 1.0)


@dataclass(frozen=True)
class CorrecaoConfig:
    """Regra de correção declarada; complementa ou substitui a extraída do edital."""

    modelo: ModeloCorrecao | None = None
    fator_penalidade: float | None = None
    nota_maxima: float | None = None
    nota_corte: float | None = None

    @property
    def define_regra(self) -> bool:
        return self.modelo is not None or self.fator_penalidade is not None


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
    folha: FolhaConfig | None = None
    edital: EditalConfig | None = None
    resultado_oficial: ResultadoOficialConfig | None = None
    correcao: CorrecaoConfig | None = None
    ignorar: tuple[str, ...] = field(default_factory=tuple)
    historico: tuple[dict, ...] = field(default_factory=tuple)

    def caminho(self, arquivo: str) -> Path:
        return self.pasta / arquivo

    @property
    def status_gabarito(self) -> str:
        estados = {prova.gabarito.status for prova in self.provas}
        return estados.pop() if len(estados) == 1 else 'misto'

    def prova_da_questao(self, questao: int) -> ProvaConfig:
        return next(p for p in self.provas if questao in p.questoes)

    @property
    def total_itens(self) -> int:
        return sum(len(prova.questoes) for prova in self.provas)


def carregar_concurso(pasta: Path) -> ConcursoConfig:
    caminho = pasta / ARQUIVO_CONFIG
    if not caminho.exists():
        raise ArquivoAusenteError(f'{caminho}: arquivo de configuração ausente')
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro
    return validar_dados(pasta, dados)


def validar_dados(pasta: Path, dados: dict) -> ConcursoConfig:
    try:
        return _montar(pasta, dados)
    except (KeyError, TypeError, ValueError) as erro:
        raise ConfiguracaoInvalidaError(f'{pasta / ARQUIVO_CONFIG}: {erro}') from erro


def _montar(pasta: Path, dados: dict) -> ConcursoConfig:
    provas = tuple(_montar_prova(chave, valor) for chave, valor in _obrigatorio(dados, 'provas').items())
    _validar_faixas_disjuntas(provas)
    respostas = dados.get('respostas') or {}
    if respostas.get('arquivo') and respostas.get('folha'):
        raise ConfiguracaoInvalidaError("respostas: use 'arquivo' ou 'folha', não ambos")
    return ConcursoConfig(
        nome=dados.get('nome', pasta.name),
        pasta=pasta,
        banca=_opcao(_obrigatorio(dados, 'banca'), BANCAS, 'banca'),
        formato=_enum(Formato, _obrigatorio(dados, 'formato'), 'formato'),
        pontuacao=_enum(Pontuacao, dados.get('pontuacao', 'simples'), 'pontuacao'),
        provas=provas,
        cargo=dados.get('cargo'),
        tipo=None if dados.get('tipo') is None else str(dados['tipo']),
        respostas_arquivo=respostas.get('arquivo'),
        folha=_montar_folha(respostas) if respostas.get('folha') else None,
        edital=_montar_edital(dados['edital']) if dados.get('edital') else None,
        resultado_oficial=_montar_resultado(dados['resultado_oficial'])
        if dados.get('resultado_oficial')
        else None,
        correcao=_montar_correcao(dados['correcao']) if dados.get('correcao') else None,
        ignorar=tuple(dados.get('ignorar') or ()),
        historico=tuple(dados.get('historico') or ()),
    )


def _montar_prova(chave: str, dados: dict) -> ProvaConfig:
    gabarito = _obrigatorio(dados, 'gabarito', f'provas.{chave}.')
    if isinstance(gabarito, str):
        gabarito = {'arquivo': gabarito}
    inicio, fim = _obrigatorio(dados, 'itens', f'provas.{chave}.')
    faixas = tuple(
        FaixaDisciplina(f['inicio'], f['fim'], f['disciplina']) for f in dados.get('disciplinas') or ()
    )
    gabarito = GabaritoConfig(**gabarito)
    _opcao(gabarito.status, STATUS_GABARITO, f'provas.{chave}.gabarito.status')
    return ProvaConfig(chave, gabarito, int(inicio), int(fim), faixas, dados.get('caderno'))


def _montar_folha(respostas: dict) -> FolhaConfig:
    return FolhaConfig(
        arquivo=respostas['folha'],
        template=_obrigatorio(respostas, 'template', 'respostas.'),
        total_itens=respostas.get('total_itens'),
        itens_por_coluna=respostas.get('itens_por_coluna'),
    )


def _montar_edital(edital: str | dict) -> EditalConfig:
    if isinstance(edital, str):
        return EditalConfig(edital)
    manual = edital.get('manual')
    arquivo = edital.get('arquivo') if manual else _obrigatorio(edital, 'arquivo', 'edital.')
    return EditalConfig(arquivo, tuple(edital.get('anexos') or ()), manual)


def _montar_resultado(resultado: str | dict) -> ResultadoOficialConfig:
    if isinstance(resultado, str):
        return ResultadoOficialConfig(resultado)
    identificador = resultado.get('identificador')
    pesos = tuple(
        PesoItens(int(p['itens'][0]), int(p['itens'][1]), float(p['peso']))
        for p in resultado.get('pesos') or ()
    )
    return ResultadoOficialConfig(
        _obrigatorio(resultado, 'arquivo', 'resultado_oficial.'),
        None if identificador is None else str(identificador),
        pesos,
    )


def _montar_correcao(correcao: dict) -> CorrecaoConfig:
    modelo = correcao.get('modelo')
    if modelo is not None:
        modelo = ModeloCorrecao(_opcao(modelo, MODELOS_DECLARAVEIS, 'correcao.modelo'))
    fator, maxima, corte = (
        _numero_opcional(correcao, campo, 'correcao.')
        for campo in ('fator_penalidade', 'nota_maxima', 'nota_corte')
    )
    if fator is not None and fator < 0:
        raise ConfiguracaoInvalidaError('correcao.fator_penalidade: não pode ser negativo')
    if modelo is not None and fator is not None and ModeloCorrecao.pelo_fator(fator) is not modelo:
        raise ConfiguracaoInvalidaError(
            f"correcao: modelo '{modelo}' incompatível com fator_penalidade {fator:g} "
            '(liquida exige fator maior que 0; bruta, fator 0)'
        )
    if modelo is ModeloCorrecao.LIQUIDA and fator is None:
        raise ConfiguracaoInvalidaError("correcao: modelo 'liquida' exige fator_penalidade maior que 0")
    return CorrecaoConfig(modelo, fator, maxima, corte)


def _numero_opcional(dados: dict, campo: str, prefixo: str = '') -> float | None:
    valor = dados.get(campo)
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        raise ConfiguracaoInvalidaError(f"{prefixo}{campo}: valor '{valor}' não é numérico") from None


def _obrigatorio(dados: dict, campo: str, prefixo: str = ''):
    if dados.get(campo) in (None, ''):
        raise ConfiguracaoInvalidaError(f"campo obrigatório '{prefixo}{campo}' ausente")
    return dados[campo]


def _opcao(valor: str, opcoes: tuple[str, ...], campo: str) -> str:
    if valor not in opcoes:
        raise ConfiguracaoInvalidaError(f"{campo}: valor '{valor}' inválido (use {', '.join(opcoes)})")
    return valor


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
