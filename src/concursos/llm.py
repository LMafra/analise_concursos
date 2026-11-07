import json
import logging
import os
import stat
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from concursos.config.contexto import gravar_secao, ler_toml
from concursos.erros import avisar

logger = logging.getLogger(__name__)

SECAO = 'llm'
NENHUM = 'nenhum'
SERVICO_KEYRING = 'concurso-analise'
ARQUIVO_ENV = '.env'
TIMEOUT_SEGUNDOS = 60
_MAXIMO_TOKENS = 1024


class FormatoApi(StrEnum):
    OPENAI = 'openai'
    ANTHROPIC = 'anthropic'


@dataclass(frozen=True)
class Provedor:
    id: str
    url: str
    modelo: str
    variavel_chave: str | None
    api: FormatoApi = FormatoApi.OPENAI


PROVEDORES = {
    p.id: p
    for p in (
        Provedor('openai', 'https://api.openai.com/v1', 'gpt-4o-mini', 'OPENAI_API_KEY'),
        Provedor('openrouter', 'https://openrouter.ai/api/v1', 'openai/gpt-4o-mini', 'OPENROUTER_API_KEY'),
        Provedor(
            'gemini',
            'https://generativelanguage.googleapis.com/v1beta/openai',
            'gemini-2.0-flash',
            'GEMINI_API_KEY',
        ),
        Provedor('ollama', 'http://localhost:11434/v1', 'llama3.1', None),
        Provedor(
            'anthropic',
            'https://api.anthropic.com/v1',
            'claude-3-5-haiku-latest',
            'ANTHROPIC_API_KEY',
            FormatoApi.ANTHROPIC,
        ),
    )
}


class LlmIndisponivelError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConfiguracaoLlm:
    """A seção `[llm]` da configuração global; nunca guarda a chave, só o nome da variável."""

    provedor: str
    url: str
    modelo: str
    variavel_chave: str | None
    consentimento: bool = False
    consentimento_livros: bool = False

    @property
    def api(self) -> FormatoApi:
        return PROVEDORES[self.provedor].api if self.provedor in PROVEDORES else FormatoApi.OPENAI


def ler_configuracao(config_global: Path) -> ConfiguracaoLlm | None:
    dados = ler_toml(config_global).get(SECAO, {})
    provedor = dados.get('provedor') or NENHUM
    if provedor == NENHUM:
        return None
    padrao = PROVEDORES.get(provedor)
    return ConfiguracaoLlm(
        provedor=provedor,
        url=dados.get('url') or (padrao and padrao.url) or '',
        modelo=dados.get('modelo') or (padrao and padrao.modelo) or '',
        variavel_chave=dados.get('variavel_chave', padrao and padrao.variavel_chave) or None,
        consentimento=bool(dados.get('consentimento')),
        consentimento_livros=bool(dados.get('consentimento_livros')),
    )


def gravar_configuracao(config_global: Path, provedor: str) -> None:
    """Grava o provedor escolhido com o consentimento; `nenhum` desliga a camada."""
    if provedor == NENHUM:
        gravar_secao(config_global, SECAO, {'provedor': NENHUM})
        return
    padrao = PROVEDORES[provedor]
    dados = {'provedor': provedor, 'url': padrao.url, 'modelo': padrao.modelo, 'consentimento': True}
    if padrao.variavel_chave:
        dados['variavel_chave'] = padrao.variavel_chave
    gravar_secao(config_global, SECAO, dados)


def gravar_consentimento_livros(config_global: Path, consentiu: bool) -> None:
    """Separado do consentimento do edital: os trechos dos livros só vão ao provedor com este."""
    gravar_secao(config_global, SECAO, {'consentimento_livros': consentiu})


def obter_chave(
    configuracao: ConfiguracaoLlm, home: Path, ambiente: Mapping[str, str] | None = None
) -> tuple[str, str] | None:
    """A chave e de onde veio: variável de ambiente, keyring ou o `.env` da pasta global, nessa ordem."""
    if configuracao.variavel_chave is None:
        return None
    return obter_chave_da_variavel(configuracao.variavel_chave, home, ambiente)


def obter_chave_da_variavel(
    variavel: str, home: Path, ambiente: Mapping[str, str] | None = None
) -> tuple[str, str] | None:
    ambiente = os.environ if ambiente is None else ambiente
    if chave := ambiente.get(variavel):
        return chave, f'variável {variavel}'
    if chave := _do_keyring(variavel):
        return chave, 'keyring'
    if chave := _do_env(home / ARQUIVO_ENV, variavel):
        return chave, str(home / ARQUIVO_ENV)
    return None


def guardar_chave(variavel: str, chave: str, home: Path) -> str:
    """No keyring; sem backend, no `.env` da pasta global com permissão 600 e aviso. Devolve onde ficou."""
    try:
        import keyring

        keyring.set_password(SERVICO_KEYRING, variavel, chave)
        return 'keyring'
    except Exception:  # noqa: BLE001 - sem keyring ou sem backend (WSL sem desktop)
        logger.debug('keyring indisponível', exc_info=True)
    caminho = home / ARQUIVO_ENV
    linhas = [
        linha
        for linha in (caminho.read_text(encoding='utf-8').splitlines() if caminho.exists() else [])
        if not linha.startswith(f'{variavel}=')
    ]
    home.mkdir(parents=True, exist_ok=True)
    caminho.touch(mode=0o600, exist_ok=True)
    caminho.chmod(0o600)
    caminho.write_text('\n'.join([*linhas, f'{variavel}={chave}']) + '\n', encoding='utf-8')
    avisar(
        logger,
        'Este computador não tem um cofre de senhas; a chave da IA ficou num arquivo só seu, sem criptografia.',
        f'para mais segurança, defina a variável {variavel} no sistema e apague o arquivo {caminho}.',
        f'sem keyring disponível: a chave ficou em texto plano em {caminho} (permissão 600)',
    )
    return str(caminho)


class ClienteLlm(Protocol):
    provedor: str

    def completar(self, sistema: str, usuario: str) -> str: ...


@dataclass(frozen=True)
class ClienteOpenAI:
    """OpenAI, OpenRouter, Gemini (endpoint compatível) e Ollama."""

    provedor: str
    url: str
    modelo: str
    chave: str | None

    def completar(self, sistema: str, usuario: str) -> str:
        corpo = {
            'model': self.modelo,
            'temperature': 0,
            'messages': [{'role': 'system', 'content': sistema}, {'role': 'user', 'content': usuario}],
        }
        cabecalhos = {'Authorization': f'Bearer {self.chave}'} if self.chave else {}
        resposta = _post(f'{self.url.rstrip("/")}/chat/completions', corpo, cabecalhos)
        try:
            return resposta['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError) as erro:
            raise LlmIndisponivelError(f'{self.provedor}: resposta sem choices[0].message.content') from erro


@dataclass(frozen=True)
class ClienteAnthropic:
    provedor: str
    url: str
    modelo: str
    chave: str | None

    def completar(self, sistema: str, usuario: str) -> str:
        corpo = {
            'model': self.modelo,
            'max_tokens': _MAXIMO_TOKENS,
            'temperature': 0,
            'system': sistema,
            'messages': [{'role': 'user', 'content': usuario}],
        }
        cabecalhos = {'x-api-key': self.chave or '', 'anthropic-version': '2023-06-01'}
        resposta = _post(f'{self.url.rstrip("/")}/messages', corpo, cabecalhos)
        try:
            return ''.join(bloco['text'] for bloco in resposta['content'] if bloco.get('type') == 'text')
        except (KeyError, TypeError) as erro:
            raise LlmIndisponivelError(f'{self.provedor}: resposta sem content de texto') from erro


@dataclass
class ClienteComMemoria:
    """Repete a resposta do mesmo pedido: com --all-candidates, o mesmo edital vai ao provedor uma vez só e
    todos os candidatos recebem a mesma resposta."""

    cliente: ClienteLlm
    respostas: dict[tuple[str, str], str] = field(default_factory=dict)

    @property
    def provedor(self) -> str:
        return self.cliente.provedor

    def completar(self, sistema: str, usuario: str) -> str:
        if (sistema, usuario) not in self.respostas:
            self.respostas[sistema, usuario] = self.cliente.completar(sistema, usuario)
        return self.respostas[sistema, usuario]


def cliente_configurado(home: Path, config_global: Path, permitido: bool = True) -> ClienteLlm | None:
    """O cliente do provedor configurado, ou None (desligado, sem consentimento ou sem chave, com aviso)."""
    configuracao = ler_configuracao(config_global)
    if not permitido or configuracao is None:
        return None
    if not configuracao.consentimento:
        avisar(
            logger,
            f'A IA ({configuracao.provedor}) está configurada, mas falta a sua autorização; segui sem ela.',
            'autorize em Configurações > Inteligência artificial para ler editais, ou rode concurso-analise init.',
            f'LLM {configuracao.provedor} sem consentimento',
        )
        return None
    chave = None
    if configuracao.variavel_chave is not None:
        encontrada = obter_chave(configuracao, home)
        if encontrada is None:
            avisar(
                logger,
                f'A IA ({configuracao.provedor}) está sem a chave de acesso; segui sem ela.',
                'informe a chave em Configurações > Inteligência artificial para ler editais, ou defina a variável '
                f'{configuracao.variavel_chave} (export {configuracao.variavel_chave}=...).',
                f'LLM {configuracao.provedor} sem chave',
            )
            return None
        chave = encontrada[0]
    classe = ClienteAnthropic if configuracao.api is FormatoApi.ANTHROPIC else ClienteOpenAI
    return classe(configuracao.provedor, configuracao.url, configuracao.modelo, chave)


def _post(url: str, corpo: dict, cabecalhos: dict[str, str]) -> dict:
    requisicao = urllib.request.Request(
        url,
        data=json.dumps(corpo).encode('utf-8'),
        headers={'Content-Type': 'application/json', **cabecalhos},
        method='POST',
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS) as resposta:
            return json.loads(resposta.read().decode('utf-8'))
    except urllib.error.HTTPError as erro:
        raise LlmIndisponivelError(f'{url}: HTTP {erro.code}') from erro
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as erro:
        raise LlmIndisponivelError(f'{url}: {erro}') from erro


def _do_keyring(variavel: str) -> str | None:
    try:
        import keyring

        return keyring.get_password(SERVICO_KEYRING, variavel)
    except Exception:  # noqa: BLE001 - sem keyring ou sem backend
        return None


def _do_env(caminho: Path, variavel: str) -> str | None:
    if not caminho.exists():
        return None
    if os.name != 'nt' and stat.S_IMODE(caminho.stat().st_mode) & 0o077:
        avisar(
            logger,
            'O arquivo com a chave da IA pode ser lido por outros usuários deste computador.',
            f'proteja o arquivo: chmod 600 "{caminho}"',
            str(caminho),
        )
    for linha in caminho.read_text(encoding='utf-8').splitlines():
        nome, _, valor = linha.partition('=')
        if nome.strip() == variavel and valor.strip():
            return valor.strip().strip('"\'')
    return None
