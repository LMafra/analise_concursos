import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from concursos.modelo import (
    LETRAS,
    Escolaridade,
    Formato,
    ModeloCorrecao,
    Nivel,
    Pontuacao,
    StatusGabarito,
)
from concursos.perfis import ids_de_banca, perfil_da_banca

ARQUIVO_CONFIG = 'concurso.yaml'
ARQUIVO_CONFIRMACAO = 'edital_a_confirmar.yaml'
CAMPOS_CONFIRMAVEIS = ('data_prova', 'alternativas', 'fator_penalidade', 'nota_corte')
_CAMPOS_DE_CORRECAO = ('fator_penalidade', 'nota_corte')


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


def carregar_concurso(pasta: Path) -> ConcursoConfig:
    caminho = pasta / ARQUIVO_CONFIG
    if not caminho.exists():
        raise ArquivoAusenteError(f'{caminho}: arquivo de configuração ausente')
    dados = _ler_yaml(caminho)
    confirmados = _ler_confirmacao(pasta / ARQUIVO_CONFIRMACAO)
    if not confirmados:
        return validar_dados(pasta, dados)
    try:
        return _montar(pasta, _com_confirmados(dados, confirmados))
    except (KeyError, TypeError, ValueError) as erro:
        validar_dados(pasta, dados)
        raise ConfiguracaoInvalidaError(f'{pasta / ARQUIVO_CONFIRMACAO}: {erro}') from erro


def ler_dados(pasta: Path) -> dict:
    """O `concurso.yaml` cru, para regravar; vazio se ausente ou ilegível."""
    caminho = pasta / ARQUIVO_CONFIG
    if not caminho.exists():
        return {}
    try:
        return yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError:
        return {}


def vinculo_sem_provas(pasta: Path) -> dict | None:
    """O bloco `pci` da pasta criada por "Adicionar ao meu projeto", enquanto ela não tem os arquivos da prova."""
    try:
        dados = ler_dados(pasta)
    except ValueError:
        return None
    if not isinstance(dados, dict) or dados.get('provas') or not isinstance(dados.get('pci'), dict):
        return None
    return dados['pci']


def gravar_dados(pasta: Path, dados: dict) -> None:
    texto = yaml.safe_dump(dados, allow_unicode=True, sort_keys=False)
    (pasta / ARQUIVO_CONFIG).write_text(texto, encoding='utf-8')


def com_gabarito_definitivo(dados: dict, prova: str, anterior: str, novo: str, data: str) -> dict:
    """Cópia dos dados com o gabarito definitivo na prova, o anterior ignorado e o evento no histórico."""
    provas = {**dados['provas']}
    provas[prova] = {
        **provas[prova],
        'gabarito': {'arquivo': novo, 'status': StatusGabarito.DEFINITIVO.value},
    }
    alterado = {**dados, 'provas': provas}
    if anterior != novo:
        alterado['ignorar'] = [*(dados.get('ignorar') or []), anterior]
    evento = {'data': data, 'tipo': 'gabarito_definitivo', 'prova': prova, 'anterior': anterior, 'novo': novo}
    alterado['historico'] = [*(dados.get('historico') or []), evento]
    return alterado


def _ler_yaml(caminho: Path) -> dict:
    try:
        dados = yaml.load(caminho.read_text(encoding='utf-8'), Loader=_CarregadorSemDatas) or {}
    except yaml.YAMLError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro
    if not isinstance(dados, dict):
        raise ConfiguracaoInvalidaError(f'{caminho}: esperado um mapa de campo para valor')
    return dados


def _ler_confirmacao(caminho: Path) -> dict:
    """Os campos preenchidos do `edital_a_confirmar.yaml`; os vazios ficam de fora."""
    if not caminho.exists():
        return {}
    dados = _ler_yaml(caminho)
    if desconhecidos := sorted(set(dados) - set(CAMPOS_CONFIRMAVEIS)):
        raise ConfiguracaoInvalidaError(
            f"{caminho}: campo desconhecido '{desconhecidos[0]}' (use {', '.join(CAMPOS_CONFIRMAVEIS)})"
        )
    return {campo: valor for campo, valor in dados.items() if valor is not None}


def _com_confirmados(dados: dict, confirmados: dict) -> dict:
    """O que o `concurso.yaml` declara vence o que foi confirmado."""
    dados = dict(dados)
    for campo, valor in confirmados.items():
        if campo in _CAMPOS_DE_CORRECAO:
            correcao = dict(dados.get('correcao') or {})
            if correcao.get(campo) is None:
                correcao[campo] = valor
            dados['correcao'] = correcao
        elif dados.get(campo) is None:
            dados[campo] = valor
    return dados


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
    formato = _enum(Formato, _obrigatorio(dados, 'formato'), 'formato')
    return ConcursoConfig(
        nome=dados.get('nome', pasta.name),
        pasta=pasta,
        banca=_opcao(_obrigatorio(dados, 'banca'), ids_de_banca(), 'banca'),
        formato=formato,
        pontuacao=_enum(Pontuacao, dados.get('pontuacao', 'simples'), 'pontuacao'),
        provas=provas,
        alternativas=_alternativas(dados.get('alternativas'), formato),
        cargo=dados.get('cargo'),
        tipo=None if dados.get('tipo') is None else str(dados['tipo']),
        respostas_arquivo=respostas.get('arquivo'),
        folha=_montar_folha(respostas) if respostas.get('folha') else None,
        edital=_montar_edital(dados['edital']) if dados.get('edital') else None,
        resultado_oficial=_montar_resultado(dados['resultado_oficial'])
        if dados.get('resultado_oficial')
        else None,
        correcao=_montar_correcao(dados['correcao']) if dados.get('correcao') else None,
        data_prova=_data_opcional(dados, 'data_prova'),
        nivel=_enum(Nivel, dados.get('nivel') or Nivel.NAO_INFORMADO, 'nivel'),
        escolaridade=_enum(
            Escolaridade, dados.get('escolaridade') or Escolaridade.NAO_INFORMADO, 'escolaridade'
        ),
        ignorar=tuple(dados.get('ignorar') or ()),
        historico=tuple(dados.get('historico') or ()),
        simulado=_montar_simulado(dados['simulado']) if dados.get('simulado') else None,
        titulo=_texto_opcional(dados.get('titulo'), 'titulo'),
        pci_titulo=_texto_opcional((dados.get('pci') or {}).get('titulo') or None, 'pci.titulo'),
    )


def _texto_opcional(valor: object, campo: str) -> str | None:
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ConfiguracaoInvalidaError(f"{campo}: valor '{valor}' não é texto")
    return valor.strip() or None


def _montar_simulado(simulado: dict) -> SimuladoConfig:
    if not isinstance(simulado, dict):
        raise ConfiguracaoInvalidaError('simulado: esperado um mapa (fonte, id_pci, ano_original, ...)')
    for campo in ('id_pci', 'ano_original'):
        valor = simulado.get(campo)
        if valor is not None and (isinstance(valor, bool) or not isinstance(valor, int)):
            raise ConfiguracaoInvalidaError(f"simulado.{campo}: valor '{valor}' não é inteiro")
    textos = ('organizadora', 'orgao', 'descricao', 'link')
    return SimuladoConfig(
        fonte=str(simulado.get('fonte') or 'manual'),
        id_pci=simulado.get('id_pci'),
        ano_original=simulado.get('ano_original'),
        **{campo: str(simulado.get(campo) or '') for campo in textos},
        concurso_alvo=simulado.get('concurso_alvo') or None,
        cargo_alvo=simulado.get('cargo_alvo') or None,
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
    status = _enum(StatusGabarito, gabarito.status, f'provas.{chave}.gabarito.status')
    gabarito = GabaritoConfig(gabarito.arquivo, status)
    return ProvaConfig(chave, gabarito, int(inicio), int(fim), faixas, dados.get('caderno'))


def _montar_folha(respostas: dict) -> FolhaConfig:
    return FolhaConfig(
        arquivo=respostas['folha'],
        template=respostas.get('template'),
        total_itens=respostas.get('total_itens'),
        itens_por_coluna=respostas.get('itens_por_coluna'),
    )


def _montar_edital(edital: str | dict) -> EditalConfig:
    if isinstance(edital, str):
        return EditalConfig(edital)
    manual = edital.get('manual')
    arquivo = edital.get('arquivo') if manual else _obrigatorio(edital, 'arquivo', 'edital.')
    retificacoes = edital.get('retificacoes') or []
    if not isinstance(retificacoes, list) or not all(isinstance(r, str) for r in retificacoes):
        raise ConfiguracaoInvalidaError('edital.retificacoes: deve ser uma lista de arquivos')
    return EditalConfig(arquivo, tuple(edital.get('anexos') or ()), manual, tuple(retificacoes))


def _montar_resultado(resultado: str | dict) -> ResultadoOficialConfig:
    if isinstance(resultado, str):
        return ResultadoOficialConfig(resultado)
    identificador = resultado.get('identificador')
    return ResultadoOficialConfig(
        _obrigatorio(resultado, 'arquivo', 'resultado_oficial.'),
        None if identificador is None else str(identificador),
        _montar_pesos(resultado.get('pesos'), 'resultado_oficial.pesos'),
    )


def _montar_pesos(pesos: list[dict] | None, campo: str) -> tuple[PesoItens, ...]:
    faixas = tuple(PesoItens(int(p['itens'][0]), int(p['itens'][1]), float(p['peso'])) for p in pesos or ())
    for faixa in faixas:
        if faixa.inicio > faixa.fim:
            raise ConfiguracaoInvalidaError(f'{campo}: faixa {faixa.inicio}-{faixa.fim} inválida')
        if faixa.peso <= 0:
            raise ConfiguracaoInvalidaError(f'{campo}: peso {faixa.peso:g} deve ser maior que 0')
    return faixas


def _montar_correcao(correcao: dict) -> CorrecaoConfig:
    modelo = correcao.get('modelo')
    if modelo is not None:
        modelo = _enum(ModeloCorrecao, modelo, 'correcao.modelo')
    fator, maxima, corte = (
        _numero_opcional(correcao, campo, 'correcao.')
        for campo in ('fator_penalidade', 'nota_maxima', 'nota_corte')
    )
    if fator is not None and fator < 0:
        raise ConfiguracaoInvalidaError('correcao.fator_penalidade: não pode ser negativo')
    ponderada = modelo is ModeloCorrecao.PONDERADA
    if (
        modelo is not None
        and fator is not None
        and ModeloCorrecao.pelo_fator(fator, ponderada=ponderada) is not modelo
    ):
        raise ConfiguracaoInvalidaError(
            f"correcao: modelo '{modelo}' incompatível com fator_penalidade {fator:g} "
            '(liquida exige fator maior que 0; bruta e ponderada, fator 0)'
        )
    if modelo is ModeloCorrecao.LIQUIDA and fator is None:
        raise ConfiguracaoInvalidaError("correcao: modelo 'liquida' exige fator_penalidade maior que 0")
    pesos = _montar_pesos(correcao.get('pesos'), 'correcao.pesos')
    variantes = _montar_variantes(correcao.get('variantes'))
    if ponderada and not pesos and not variantes:
        raise ConfiguracaoInvalidaError("correcao: modelo 'ponderada' exige pesos ou variantes")
    return CorrecaoConfig(modelo, fator, maxima, corte, pesos, variantes)


def _montar_variantes(variantes: list | None) -> tuple[VarianteCorrecaoConfig, ...]:
    montadas = []
    for variante in variantes or ():
        if not isinstance(variante, dict):
            variante = {'nome': variante}
        nome = str(_obrigatorio(variante, 'nome', 'correcao.variantes.'))
        if any(v.nome == nome for v in montadas):
            raise ConfiguracaoInvalidaError(f"correcao.variantes: '{nome}' repetida")
        montadas.append(
            VarianteCorrecaoConfig(
                nome, _montar_pesos(variante.get('pesos'), f'correcao.variantes.{nome}.pesos')
            )
        )
    return tuple(montadas)


def _numero_opcional(dados: dict, campo: str, prefixo: str = '') -> float | None:
    valor = dados.get(campo)
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        raise ConfiguracaoInvalidaError(f"{prefixo}{campo}: valor '{valor}' não é numérico") from None


def _data_opcional(dados: dict, campo: str) -> date | None:
    valor = dados.get(campo)
    if valor is None:
        return None
    try:
        if not _DATA_ISO.fullmatch(str(valor)):
            raise ValueError
        return date.fromisoformat(str(valor))
    except ValueError:
        raise ConfiguracaoInvalidaError(
            f"{campo}: valor '{valor}' não é uma data ISO 8601 (aaaa-mm-dd)"
        ) from None


def _obrigatorio(dados: dict, campo: str, prefixo: str = ''):
    if dados.get(campo) in (None, ''):
        raise ConfiguracaoInvalidaError(f"campo obrigatório '{prefixo}{campo}' ausente")
    return dados[campo]


def _alternativas(valor: object, formato: Formato) -> int | None:
    if valor is None:
        return None
    if formato is Formato.CERTO_ERRADO:
        raise ConfiguracaoInvalidaError(
            'alternativas: só vale para multipla_escolha (certo_errado tem C e E)'
        )
    if not isinstance(valor, int) or not 2 <= valor <= len(LETRAS):
        raise ConfiguracaoInvalidaError(
            f'alternativas: deve ser um inteiro de 2 a {len(LETRAS)}, recebido {valor!r}'
        )
    return valor


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
