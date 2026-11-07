"""Configuração e cliente do servidor MCP da PCI Concursos; os fatos do servidor estão em `docs/pesquisa-pci-mcp.md`."""

import json
import logging
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, fields
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol

from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import gravar_secao, ler_toml
from concursos.datas import data_br
from concursos.erros import avisar
from concursos.integracoes.cache_pci import CachePci, argumentos_normalizados

logger = logging.getLogger(__name__)

SECAO = 'pci_mcp'
URL_PADRAO = 'https://mcp.pciconcursos.com.br/mcp'
REGIOES = ('norte', 'nordeste', 'centro-oeste', 'sudeste', 'sul')
MAXIMO_CONSULTAS = 20
FERRAMENTAS = (
    'listar_concursos',
    'pesquisar_concursos',
    'buscar_por_cargo',
    'buscar_por_cidade',
    'pesquisar_provas',
)
DICA_INSTALAR = "instale o extra: `uv tool install 'concurso-analise[pci]'` (ou `uv sync --extra pci`)"
DICA_SERVIDOR = 'o site do PCI pode estar fora do ar; tente de novo mais tarde.'
DICA_FORMATO = 'atualize o app; o PCI mudou a forma de responder (o app foi testado com a versão 1.0.0 dele).'
CAUSA_FORMATO = 'O PCI respondeu num formato que o app não conhece.'
CAUSA_FORA_DO_AR = 'Não consegui falar com o PCI.'
_UF = re.compile(r'^[a-z]{2}$')


@dataclass(frozen=True)
class ConfiguracaoPciMcp:
    """A seção `[pci_mcp]` da configuração global; `cargos` e `uf` são a reserva do `[pci]` do candidato."""

    enabled: bool = False
    url: str = URL_PADRAO
    timeout: float = 30
    ttl_horas: float = 24
    cargos: tuple[str, ...] = ()
    uf: str = ''
    cidade: str = ''
    regiao: str = ''
    dias_alerta: int = 15
    pasta_downloads: str = ''
    timeout_download: float = 300


_TIPOS = {campo.name: campo.type for campo in fields(ConfiguracaoPciMcp)}


def validar_cargos(valor: Any, onde: str) -> tuple[str, ...]:
    if not isinstance(valor, list) or not all(isinstance(c, str) and c.strip() for c in valor):
        raise ConfiguracaoInvalidaError(f'{onde} cargos = {valor!r} é inválido; use uma lista de nomes')
    return tuple(c.strip() for c in valor)


def validar_uf(valor: Any, onde: str) -> str:
    uf = valor.strip().lower() if isinstance(valor, str) else None
    if uf is None or (uf and not _UF.match(uf)):
        raise ConfiguracaoInvalidaError(f'{onde} uf = {valor!r} é inválido; use a sigla, ex.: "sp"')
    return uf


def ler_configuracao(config_global: Path) -> ConfiguracaoPciMcp:
    dados = dict(ler_toml(config_global).get(SECAO, {}))
    onde = f'{config_global}: [{SECAO}]'
    desconhecidos = sorted(set(dados) - set(_TIPOS))
    if desconhecidos:
        raise ConfiguracaoInvalidaError(
            f'{onde} tem campo desconhecido {", ".join(desconhecidos)}; os campos são {", ".join(_TIPOS)}'
        )
    for nome, valor in dados.items():
        esperado = _TIPOS[nome]
        if nome == 'cargos':
            dados[nome] = validar_cargos(valor, onde)
            continue
        if nome == 'uf':
            dados[nome] = validar_uf(valor, onde)
            continue
        if nome == 'regiao':
            valido = valor in ('', *REGIOES)
        elif esperado is float:
            valido = isinstance(valor, int | float) and not isinstance(valor, bool) and valor > 0
        elif esperado is int:
            valido = isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0
        elif esperado is bool:
            valido = isinstance(valor, bool)
        elif nome == 'url':
            valido = isinstance(valor, str) and bool(valor)
        else:
            valido = isinstance(valor, str)
        if not valido:
            raise ConfiguracaoInvalidaError(f'{onde} {nome} = {valor!r} é inválido')
    return ConfiguracaoPciMcp(**dados)


def gravar_configuracao(config_global: Path, **valores: Any) -> ConfiguracaoPciMcp:
    atual = ler_configuracao(config_global)
    dados = {campo: getattr(atual, campo) for campo in _TIPOS} | valores
    dados['cargos'] = list(dados['cargos'])
    gravar_secao(config_global, SECAO, dados)
    return ler_configuracao(config_global)


class PciMcpErro(RuntimeError):
    def __init__(self, causa: str, dica: str | None = None, detalhe: str | None = None) -> None:
        super().__init__(causa)
        self.causa = causa
        self.dica = dica
        self.detalhe = detalhe


class PciMcpIndisponivelError(PciMcpErro):
    """Rede, timeout, HTTP ou o extra `pci` não instalado."""


class PciMcpFormatoError(PciMcpErro):
    """A resposta não tem o formato de `docs/pesquisa-pci-mcp.md`."""


class PciMcpParametroError(PciMcpErro):
    """O servidor recusou um argumento (`isError`), ou falta um filtro obrigatório."""


def interpretar(ferramenta: str, is_error: bool, texto: str) -> dict:
    if is_error:
        motivo = texto.removeprefix('Erro ao executar a tool:').strip()
        raise PciMcpParametroError(
            f'O PCI recusou a busca: {motivo}',
            'confira os filtros (a UF tem 2 letras, como "sp").',
            f'ferramenta {ferramenta}',
        )
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise PciMcpFormatoError(
            CAUSA_FORMATO, DICA_FORMATO, f'{ferramenta}: a resposta não é JSON'
        ) from erro
    if (
        not isinstance(dados, dict)
        or not isinstance(dados.get('meta'), dict)
        or not isinstance(dados.get('data'), list)
    ):
        raise PciMcpFormatoError(
            CAUSA_FORMATO, DICA_FORMATO, f'{ferramenta}: a resposta não tem `meta` e `data`'
        )
    return dados


class TransporteMcp(Protocol):
    def ferramentas(self) -> frozenset[str]: ...

    def chamar(self, ferramenta: str, argumentos: dict[str, Any]) -> dict: ...


def _causa(erro: BaseException) -> str:
    while isinstance(erro, BaseExceptionGroup) and erro.exceptions:
        erro = erro.exceptions[0]
    return f'{type(erro).__name__}: {erro}' if str(erro) else type(erro).__name__


class TransporteSdk:
    """Uma sessão do SDK `mcp` por execução, aberta na primeira consulta, num laço de eventos em outra thread.

    O `BlockingPortal` do anyio entra e sai do `Client` na mesma tarefa, como o SDK exige."""

    def __init__(self, alvo: Any, timeout: float, modo: str = 'legacy') -> None:
        self.alvo = alvo
        self.timeout = timeout
        self.modo = modo
        self._portal_cm: Any = None
        self._portal: Any = None
        self._cliente_cm: Any = None
        self._cliente: Any = None
        self._ferramentas: frozenset[str] | None = None

    def __enter__(self) -> 'TransporteSdk':
        return self

    def __exit__(
        self, tipo: type[BaseException] | None, erro: BaseException | None, rastro: TracebackType | None
    ) -> None:
        self.fechar()

    def _abrir(self) -> Any:
        if self._cliente is not None:
            return self._cliente
        try:
            from anyio.from_thread import start_blocking_portal
            from mcp import Client
        except ImportError as erro:
            raise PciMcpIndisponivelError(
                'Falta um componente do app para buscar no PCI.',
                DICA_INSTALAR,
                'o cliente MCP (pacote `mcp`) não está instalado',
            ) from erro
        self._portal_cm = start_blocking_portal()
        self._portal = self._portal_cm.__enter__()
        try:
            cliente = Client(self.alvo, mode=self.modo, read_timeout_seconds=self.timeout, cache=None)
            self._cliente_cm = self._portal.wrap_async_context_manager(cliente)
            self._cliente = self._cliente_cm.__enter__()
        except Exception as erro:
            self._cliente_cm = None
            self.fechar()
            raise PciMcpIndisponivelError(
                CAUSA_FORA_DO_AR, DICA_SERVIDOR, f'abrir a sessão MCP: {_causa(erro)}'
            ) from erro
        return self._cliente

    def fechar(self) -> None:
        cliente_cm, portal_cm = self._cliente_cm, self._portal_cm
        self._cliente = self._cliente_cm = self._portal = self._portal_cm = None
        try:
            if cliente_cm is not None:
                cliente_cm.__exit__(None, None, None)
        except Exception as erro:
            logger.debug('PCI: erro ao fechar a sessão: %s', _causa(erro))
        finally:
            if portal_cm is not None:
                portal_cm.__exit__(None, None, None)

    def ferramentas(self) -> frozenset[str]:
        if self._ferramentas is None:
            cliente = self._abrir()
            try:
                resultado = self._portal.call(cliente.list_tools)
            except Exception as erro:
                raise PciMcpIndisponivelError(
                    CAUSA_FORA_DO_AR, DICA_SERVIDOR, f'listar as ferramentas: {_causa(erro)}'
                ) from erro
            self._ferramentas = frozenset(ferramenta.name for ferramenta in resultado.tools)
        return self._ferramentas

    def chamar(self, ferramenta: str, argumentos: dict[str, Any]) -> dict:
        cliente = self._abrir()
        try:
            resultado = self._portal.call(cliente.call_tool, ferramenta, argumentos)
        except Exception as erro:
            raise PciMcpIndisponivelError(
                CAUSA_FORA_DO_AR, DICA_SERVIDOR, f'consulta {ferramenta}: {_causa(erro)}'
            ) from erro
        texto = ''.join(getattr(parte, 'text', '') for parte in resultado.content)
        return interpretar(ferramenta, bool(resultado.is_error), texto)


def abrir_transporte(configuracao: ConfiguracaoPciMcp) -> TransporteMcp:
    """O ponto que os testes da CLI trocam por um transporte falso."""
    return TransporteSdk(configuracao.url, configuracao.timeout)


@dataclass(frozen=True)
class DatasInscricao:
    inicio: str = ''
    fim: str = ''
    texto: str = ''
    aberto: bool = False
    em_breve: bool = False
    dias_ate_inicio: int | None = None
    dias_ate_fim: int | None = None


@dataclass(frozen=True)
class ConcursoPci:
    """`dias_ate_*` são relativos a `data_referencia` (o `meta.data_atual` da resposta), não a hoje."""

    id: int
    titulo: str
    uf: str
    cargos: tuple[str, ...]
    cargos_resumo: str
    vagas_salario: str
    formacao: str
    regiao: str
    datas: DatasInscricao
    link: str
    data_referencia: str


@dataclass(frozen=True)
class ProvaAnteriorPci:
    id: int
    descricao: str
    orgao: str
    ano: int | None
    organizadora: str
    link: str


def _id(item: Any, ferramenta: str) -> int:
    valor = item.get('id') if isinstance(item, dict) else None
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise PciMcpFormatoError(CAUSA_FORMATO, DICA_FORMATO, f'{ferramenta}: item sem `id` numérico')
    return valor


def _texto(valor: Any) -> str:
    return valor.strip() if isinstance(valor, str) else ''


def _inteiro(valor: Any) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def ler_concurso(item: Any, data_referencia: str, ferramenta: str = 'concursos') -> ConcursoPci:
    identificador = _id(item, ferramenta)
    datas = item.get('datas') if isinstance(item.get('datas'), dict) else {}
    noticia = item.get('noticia') if isinstance(item.get('noticia'), dict) else {}
    cargos = item.get('cargos') if isinstance(item.get('cargos'), list) else []
    return ConcursoPci(
        id=identificador,
        titulo=_texto(item.get('titulo')),
        uf=_texto(item.get('uf')).upper(),
        cargos=tuple(_texto(c) for c in cargos if _texto(c)),
        cargos_resumo=_texto(item.get('cargos_resumo')),
        vagas_salario=_texto(item.get('vagas_salario')),
        formacao=_texto(item.get('formacao')),
        regiao=_texto(item.get('regiao')),
        datas=DatasInscricao(
            inicio=_texto(datas.get('inicio')),
            fim=_texto(datas.get('fim')),
            texto=_texto(datas.get('texto')),
            aberto=datas.get('aberto') is True,
            em_breve=datas.get('em_breve') is True,
            dias_ate_inicio=_inteiro(datas.get('dias_ate_inicio')),
            dias_ate_fim=_inteiro(datas.get('dias_ate_fim')),
        ),
        link=_texto(noticia.get('link')),
        data_referencia=data_referencia,
    )


def ler_prova(item: Any) -> ProvaAnteriorPci:
    return ProvaAnteriorPci(
        id=_id(item, 'pesquisar_provas'),
        descricao=_texto(item.get('descricao')),
        orgao=_texto(item.get('orgao')),
        ano=_inteiro(item.get('ano')),
        organizadora=_texto(item.get('organizadora')),
        link=_texto(item.get('link')),
    )


class ClientePciMcp:
    """Consultas ao PCI com cache; sem transporte (`--offline`), só o cache, mesmo vencido.

    Só termos de busca saem daqui: nenhum dado do candidato é argumento de ferramenta."""

    def __init__(
        self,
        transporte: TransporteMcp | None,
        cache: CachePci,
        *,
        refresh: bool = False,
        maximo: int = MAXIMO_CONSULTAS,
    ) -> None:
        self.transporte = transporte
        self.cache = cache
        self.refresh = refresh
        self.maximo = maximo
        self.consultas = 0
        self.do_cache = 0
        self.falhas = 0
        self._avisados: set[str] = set()

    def _avisar(self, chave: str, texto: str, detalhe: str | None = None) -> None:
        if chave not in self._avisados:
            self._avisados.add(chave)
            avisar(logger, texto, detalhe=detalhe)

    def resumo(self) -> str:
        return f'PCI: {self.consultas} consultas, {self.do_cache} do cache, {self.falhas} falhas'

    def consultar(self, ferramenta: str, argumentos: dict[str, Any]) -> dict | None:
        argumentos = argumentos_normalizados(argumentos)
        guardada = self.cache.obter(ferramenta, argumentos)
        if guardada and not guardada.vencida and not self.refresh:
            self.do_cache += 1
            logger.debug('PCI: %s %s do cache (%s)', ferramenta, argumentos, guardada.obtido_em)
            return guardada.resposta
        if self.transporte is None:
            if guardada:
                self.do_cache += 1
                self._avisar(
                    f'offline:{ferramenta}:{argumentos}',
                    f'PCI: sem internet; usei o resultado guardado da busca de {data_br(guardada.obtido_em)}.',
                    f'cache de {guardada.obtido_em} para {ferramenta} {argumentos}',
                )
                return guardada.resposta
            self._avisar(
                f'sem-cache:{ferramenta}:{argumentos}',
                'PCI: sem internet e sem resultado guardado desta busca; ela ficou de fora.',
                f'sem rede e sem cache para {ferramenta} {argumentos}',
            )
            return None
        if self.consultas >= self.maximo:
            self._avisar(
                'limite',
                f'PCI: cheguei ao limite de {self.maximo} consultas de uma vez; o resto fica para a próxima.',
            )
            return guardada.resposta if guardada else None
        inicio = time.monotonic()
        try:
            if ferramenta not in self.transporte.ferramentas():
                self._avisar(
                    f'ferramenta:{ferramenta}',
                    'PCI: o site não oferece mais esta busca; pulei o que dependia dela.',
                    f'o servidor não tem mais a ferramenta {ferramenta}',
                )
                return None
            self.consultas += 1
            resposta = self.transporte.chamar(ferramenta, argumentos)
        except PciMcpParametroError:
            self.falhas += 1
            raise
        except (PciMcpIndisponivelError, PciMcpFormatoError) as erro:
            self.falhas += 1
            if not guardada:
                raise
            avisar(
                logger,
                f'PCI: {erro.causa} Usei o resultado guardado da busca de {data_br(guardada.obtido_em)}.',
                erro.dica,
                f'{erro.detalhe or erro.causa}; usando o cache vencido de {guardada.obtido_em}',
            )
            return guardada.resposta
        logger.debug('PCI: %s %s em %.2fs', ferramenta, argumentos, time.monotonic() - inicio)
        self.cache.guardar(ferramenta, argumentos, resposta)
        return resposta

    def buscar_concursos(
        self,
        *,
        cargos: Iterable[str] = (),
        uf: str = '',
        cidade: str = '',
        regiao: str = '',
        termo: str = '',
        professores: bool = False,
    ) -> list[ConcursoPci]:
        """Uma consulta por cargo (o servidor não usa sinônimos), juntando pelo `id`; sem filtro, a lista geral."""
        uf = uf.strip().lower()
        consultas: list[tuple[str, dict[str, Any]]] = []
        if cidade:
            if not uf:
                raise PciMcpParametroError(
                    'A busca por cidade precisa da UF.',
                    'escolha a UF junto com a cidade (na linha de comando, `--uf sp --cidade campinas`).',
                )
            consultas.append(('buscar_por_cidade', {'uf': uf, 'cidade': cidade}))
        if termo:
            consultas.append(('pesquisar_concursos', {'termo': termo, 'uf': uf}))
        consultas += [('buscar_por_cargo', {'cargo': cargo, 'uf': uf}) for cargo in cargos]
        filtrar_uf = not consultas and bool(uf)
        if not consultas:
            consultas.append(('listar_concursos', {'regiao': regiao, 'professores': professores}))
        encontrados: dict[int, ConcursoPci] = {}
        for ferramenta, argumentos in consultas:
            resposta = self.consultar(ferramenta, argumentos)
            if not resposta:
                continue
            data_atual = _texto(resposta['meta'].get('data_atual'))
            for item in resposta['data']:
                concurso = ler_concurso(item, data_atual, ferramenta)
                encontrados.setdefault(concurso.id, concurso)
        concursos = list(encontrados.values())
        if filtrar_uf:
            concursos = [c for c in concursos if c.uf.lower() in (uf, 'br', '')]
        return concursos

    def pesquisar_provas_anteriores(self, termo: str) -> list[ProvaAnteriorPci]:
        resposta = self.consultar('pesquisar_provas', {'termo': termo})
        if not resposta:
            return []
        provas: dict[int, ProvaAnteriorPci] = {}
        for item in resposta['data']:
            prova = ler_prova(item)
            provas.setdefault(prova.id, prova)
        return list(provas.values())
