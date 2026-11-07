"""Configuração e cliente HTTP do open-notebook (https://github.com/lfnovo/open-notebook), versão 1.15."""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import gravar_secao, ler_toml
from concursos.erros import avisar
from concursos.llm import obter_chave_da_variavel

logger = logging.getLogger(__name__)

SECAO = 'open_notebook'
URL_PADRAO = 'http://localhost:5055'
VARIAVEL_CHAVE_PADRAO = 'OPEN_NOTEBOOK_PASSWORD'
TIMEOUT_PADRAO = 120
LIMITE_PAGINA = 100
DICA_INSTANCIA = (
    'abra o seu open-notebook e confira o endereço em Configurações > Avançado; para usar a biblioteca do '
    'próprio app, desligue-o lá e prepare a biblioteca em Estudar.'
)
DICA_VERSAO = 'o open-notebook mudou de versão; o app foi testado com a versão 1.15.'


@dataclass(frozen=True)
class ConfiguracaoOpenNotebook:
    """A seção `[open_notebook]` da configuração global; a senha nunca fica aqui, só o nome da variável."""

    enabled: bool = False
    consentimento: bool = False
    url: str = URL_PADRAO
    variavel_chave: str = VARIAVEL_CHAVE_PADRAO
    timeout: float = TIMEOUT_PADRAO
    incluir_nome: bool = False
    embed: bool = False

    @property
    def ativa(self) -> bool:
        return self.enabled and self.consentimento


_TIPOS = {campo.name: campo.type for campo in fields(ConfiguracaoOpenNotebook)}


def ler_configuracao(config_global: Path) -> ConfiguracaoOpenNotebook:
    dados = ler_toml(config_global).get(SECAO, {})
    desconhecidos = sorted(set(dados) - set(_TIPOS))
    if desconhecidos:
        raise ConfiguracaoInvalidaError(
            f'{config_global}: [{SECAO}] tem campo desconhecido {", ".join(desconhecidos)}; '
            f'os campos são {", ".join(_TIPOS)}'
        )
    for nome, valor in dados.items():
        esperado = _TIPOS[nome]
        if esperado is float:
            valido = isinstance(valor, int | float) and not isinstance(valor, bool) and valor > 0
        elif esperado is bool:
            valido = isinstance(valor, bool)
        else:
            valido = isinstance(valor, str) and bool(valor)
        if not valido:
            raise ConfiguracaoInvalidaError(f'{config_global}: [{SECAO}] {nome} = {valor!r} é inválido')
    return ConfiguracaoOpenNotebook(**dados)


def gravar_configuracao(config_global: Path, **valores: Any) -> ConfiguracaoOpenNotebook:
    atual = ler_configuracao(config_global)
    dados = {campo: getattr(atual, campo) for campo in _TIPOS} | valores
    gravar_secao(config_global, SECAO, dados)
    return ler_configuracao(config_global)


def obter_senha(
    configuracao: ConfiguracaoOpenNotebook, home: Path, ambiente: Mapping[str, str] | None = None
) -> str | None:
    """Sem senha é válido: o open-notebook sem `OPEN_NOTEBOOK_PASSWORD` não exige autenticação."""
    encontrada = obter_chave_da_variavel(configuracao.variavel_chave, home, ambiente)
    return encontrada[0] if encontrada else None


class OpenNotebookIndisponivelError(RuntimeError):
    def __init__(
        self, causa: str, dica: str | None = None, status: int | None = None, detalhe: str | None = None
    ) -> None:
        super().__init__(causa)
        self.causa = causa
        self.dica = dica
        self.status = status
        self.detalhe = detalhe


@dataclass(frozen=True)
class _Arquivo:
    nome: str
    conteudo: bytes


class ClienteOpenNotebook:
    def __init__(self, url: str, senha: str | None = None, timeout: float = TIMEOUT_PADRAO) -> None:
        self.url = url.rstrip('/')
        self.senha = senha
        self.timeout = timeout

    @classmethod
    def da_configuracao(
        cls, configuracao: ConfiguracaoOpenNotebook, home: Path, ambiente: Mapping[str, str] | None = None
    ) -> 'ClienteOpenNotebook':
        return cls(configuracao.url, obter_senha(configuracao, home, ambiente), configuracao.timeout)

    def saude(self) -> None:
        self._requisitar('GET', '/health')

    def listar_notebooks(self) -> list[dict]:
        return self._requisitar(
            'GET', '/api/notebooks', consulta={'archived': 'false', 'order_by': 'created asc'}
        )

    def obter_notebook(self, notebook_id: str) -> dict | None:
        try:
            return self._requisitar('GET', f'/api/notebooks/{_id(notebook_id)}')
        except OpenNotebookIndisponivelError as erro:
            if erro.status == 404:
                return None
            raise

    def buscar_notebook_por_nome(self, nome: str) -> dict | None:
        """O mais antigo com o nome exato; o servidor aceita nomes repetidos."""
        iguais = [nb for nb in self.listar_notebooks() if nb.get('name') == nome and not nb.get('archived')]
        if len(iguais) > 1:
            avisar(
                logger,
                f'open-notebook: há {len(iguais)} cadernos chamados "{nome}"; usei o mais antigo.',
                'apague ou renomeie os repetidos no seu open-notebook.',
            )
        return min(iguais, key=lambda nb: str(nb.get('created', ''))) if iguais else None

    def criar_notebook(self, nome: str, descricao: str = '') -> dict:
        return self._requisitar('POST', '/api/notebooks', corpo={'name': nome, 'description': descricao})

    def listar_sources(self, notebook_id: str) -> list[dict]:
        sources: list[dict] = []
        while True:
            pagina = self._requisitar(
                'GET',
                '/api/sources',
                consulta={
                    'notebook_id': notebook_id,
                    'limit': LIMITE_PAGINA,
                    'offset': len(sources),
                    'sort_by': 'created',
                    'sort_order': 'asc',
                },
            )
            sources.extend(pagina)
            if len(pagina) < LIMITE_PAGINA:
                return sources

    def adicionar_source_texto(
        self, notebook_id: str, titulo: str, conteudo: str, embed: bool = False, assincrono: bool = False
    ) -> dict:
        formulario = {
            'type': 'text',
            'notebooks': json.dumps([notebook_id]),
            'title': titulo,
            'content': conteudo,
            'embed': _booleano(embed),
            'async_processing': _booleano(assincrono),
        }
        return self._requisitar('POST', '/api/sources', formulario=formulario)

    def adicionar_source_arquivo(
        self, notebook_id: str, caminho: Path, titulo: str, embed: bool = False, assincrono: bool = False
    ) -> dict:
        formulario = {
            'type': 'upload',
            'notebooks': json.dumps([notebook_id]),
            'title': titulo,
            'embed': _booleano(embed),
            'async_processing': _booleano(assincrono),
        }
        arquivo = _Arquivo(caminho.name, caminho.read_bytes())
        return self._requisitar('POST', '/api/sources', formulario=formulario, arquivo=arquivo)

    def status_source(self, source_id: str) -> dict:
        return self._requisitar('GET', f'/api/sources/{_id(source_id)}/status')

    def renomear_source(self, source_id: str, titulo: str) -> dict:
        return self._requisitar('PUT', f'/api/sources/{_id(source_id)}', corpo={'title': titulo})

    def apagar_source(self, source_id: str) -> None:
        self._requisitar('DELETE', f'/api/sources/{_id(source_id)}')

    def vincular_source(self, notebook_id: str, source_id: str) -> None:
        self._requisitar('POST', f'/api/notebooks/{_id(notebook_id)}/sources/{_id(source_id)}')

    def desvincular_source(self, notebook_id: str, source_id: str) -> None:
        self._requisitar('DELETE', f'/api/notebooks/{_id(notebook_id)}/sources/{_id(source_id)}')

    def listar_notas(self, notebook_id: str) -> list[dict]:
        return self._requisitar('GET', '/api/notes', consulta={'notebook_id': notebook_id})

    def criar_nota(self, notebook_id: str, titulo: str, conteudo: str) -> dict:
        corpo = {'title': titulo, 'content': conteudo, 'note_type': 'human', 'notebook_id': notebook_id}
        return self._requisitar('POST', '/api/notes', corpo=corpo)

    def atualizar_nota(self, nota_id: str, conteudo: str) -> dict:
        return self._requisitar('PUT', f'/api/notes/{_id(nota_id)}', corpo={'content': conteudo})

    def buscar_texto(self, consulta: str, notebook_ids: list[str], limite: int = 20) -> list[dict]:
        """Busca de texto completo (sem embedding nem LLM); cada resultado traz `parent_id`, `title` e
        `relevance`, sem trecho do texto."""
        corpo = {
            'query': consulta,
            'type': 'text',
            'limit': limite,
            'search_sources': True,
            'search_notes': False,
            'notebook_ids': notebook_ids,
        }
        return self._requisitar('POST', '/api/search', corpo=corpo).get('results', [])

    def buscar_vetorial(
        self, consulta: str, notebook_ids: list[str] | None = None, limite: int = 20
    ) -> list[dict]:
        corpo = {
            'query': consulta,
            'type': 'vector',
            'limit': limite,
            'search_sources': True,
            'search_notes': False,
            'minimum_score': 0.2,
        }
        if notebook_ids:
            corpo['notebook_ids'] = notebook_ids
        return self._requisitar('POST', '/api/search', corpo=corpo).get('results', [])

    def obter_source(self, source_id: str) -> dict:
        return self._requisitar('GET', f'/api/sources/{_id(source_id)}')

    def reprocessar_source(self, source_id: str) -> dict:
        """Refaz os embeddings do source em segundo plano (o `/retry` só vale para source de arquivo)."""
        corpo = {'item_id': source_id, 'item_type': 'source', 'async_processing': True}
        return self._requisitar('POST', '/api/embed', corpo=corpo)

    def listar_modelos(self, tipo: str | None = None) -> list[dict]:
        return self._requisitar('GET', '/api/models', consulta={'type': tipo} if tipo else None)

    def criar_modelo(self, nome: str, provedor: str, tipo: str, credencial: str | None = None) -> dict:
        corpo = {'name': nome, 'provider': provedor, 'type': tipo}
        if credencial:
            corpo['credential'] = credencial
        return self._requisitar('POST', '/api/models', corpo=corpo)

    def apagar_modelo(self, modelo_id: str) -> None:
        self._requisitar('DELETE', f'/api/models/{_id(modelo_id)}')

    def modelos_padrao(self) -> dict:
        return self._requisitar('GET', '/api/models/defaults')

    def gravar_modelos_padrao(self, **padroes: str) -> dict:
        return self._requisitar('PUT', '/api/models/defaults', corpo=padroes)

    def perguntar(self, pergunta: str, modelo_id: str) -> dict:
        """Ask do open-notebook com o mesmo modelo nas três funções; devolve `{answer, question}`."""
        corpo = {
            'question': pergunta,
            'strategy_model': modelo_id,
            'answer_model': modelo_id,
            'final_answer_model': modelo_id,
        }
        return self._requisitar('POST', '/api/search/ask/simple', corpo=corpo)

    def _requisitar(
        self,
        metodo: str,
        caminho: str,
        *,
        corpo: dict | None = None,
        formulario: dict[str, str] | None = None,
        arquivo: _Arquivo | None = None,
        consulta: dict | None = None,
    ) -> Any:
        url = f'{self.url}{caminho}'
        if consulta:
            url += '?' + urllib.parse.urlencode(consulta)
        cabecalhos = {'Accept': 'application/json'}
        if self.senha:
            cabecalhos['Authorization'] = f'Bearer {self.senha}'
        dados = None
        if corpo is not None:
            dados = json.dumps(corpo).encode('utf-8')
            cabecalhos['Content-Type'] = 'application/json'
        elif formulario is not None:
            dados, tipo = _multipart(formulario, arquivo)
            cabecalhos['Content-Type'] = tipo
        requisicao = urllib.request.Request(url, data=dados, headers=cabecalhos, method=metodo)
        logger.debug('open-notebook: %s %s', metodo, caminho)
        try:
            with urllib.request.urlopen(requisicao, timeout=self.timeout) as resposta:
                bruto = resposta.read()
        except urllib.error.HTTPError as erro:
            raise _erro_http(metodo, caminho, erro) from erro
        except (urllib.error.URLError, TimeoutError, ConnectionError) as erro:
            motivo = getattr(erro, 'reason', erro)
            raise OpenNotebookIndisponivelError(
                'Não consegui falar com o open-notebook.',
                DICA_INSTANCIA,
                detalhe=f'open-notebook indisponível em {self.url}: {motivo}',
            ) from erro
        if not bruto:
            return None
        try:
            return json.loads(bruto.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as erro:
            raise OpenNotebookIndisponivelError(
                'O open-notebook respondeu algo que o app não entende.',
                DICA_VERSAO,
                detalhe=f'open-notebook: {metodo} {caminho} devolveu algo que não é JSON',
            ) from erro


def _erro_http(metodo: str, caminho: str, erro: urllib.error.HTTPError) -> OpenNotebookIndisponivelError:
    try:
        detalhe = json.loads(erro.read().decode('utf-8')).get('detail')
    except Exception:  # noqa: BLE001 - corpo vazio ou não JSON
        detalhe = None
    tecnico = f'open-notebook: {metodo} {caminho} devolveu HTTP {erro.code}' + (
        f' ({detalhe})' if detalhe else ''
    )
    causas = {
        401: 'O open-notebook pediu a senha.',
        404: 'O open-notebook não encontrou o que o app pediu.',
        413: 'O arquivo é grande demais para o open-notebook.',
    }
    dicas = {
        401: f'defina a senha da instância na variável {VARIAVEL_CHAVE_PADRAO} (ou na `variavel_chave` de '
        '[open_notebook])',
        413: 'divida o arquivo em partes menores ou aumente o limite do seu open-notebook '
        '(OPEN_NOTEBOOK_MAX_UPLOAD_SIZE_MB, padrão 100 MB).',
        405: DICA_VERSAO,
        422: DICA_VERSAO,
    }
    return OpenNotebookIndisponivelError(
        causas.get(erro.code, 'O open-notebook recusou o pedido.'), dicas.get(erro.code), erro.code, tecnico
    )


def _multipart(campos: dict[str, str], arquivo: _Arquivo | None) -> tuple[bytes, str]:
    fronteira = f'concurso-analise-{uuid.uuid4().hex}'
    partes: list[bytes] = []
    for nome, valor in campos.items():
        partes.append(
            f'--{fronteira}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n'.encode()
            + valor.encode('utf-8')
            + b'\r\n'
        )
    if arquivo is not None:
        nome_arquivo = arquivo.nome.replace('"', '')
        partes.append(
            f'--{fronteira}\r\nContent-Disposition: form-data; name="file"; filename="{nome_arquivo}"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n'.encode()
            + arquivo.conteudo
            + b'\r\n'
        )
    partes.append(f'--{fronteira}--\r\n'.encode())
    return b''.join(partes), f'multipart/form-data; boundary={fronteira}'


def _booleano(valor: bool) -> str:
    return 'true' if valor else 'false'


def _id(valor: str) -> str:
    return urllib.parse.quote(valor, safe=':')
