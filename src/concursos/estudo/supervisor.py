"""Os processos do open-notebook gerenciado: SurrealDB, embeddings, API e worker, só em 127.0.0.1.

Sobem sob demanda (`garantir`), com portas livres, senha e token aleatórios por sessão, e param depois
de `OCIOSIDADE` sem uso ou quando o app fecha. Um processo que cai faz todos subirem de novo; três
partidas falhas seguidas deixam o supervisor `indisponivel`, e quem chama usa a busca local.
"""

import contextlib
import hashlib
import hmac
import logging
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from concursos.erros import ErroDoAmbiente
from concursos.estudo import instalacao
from concursos.estudo.instalacao import Pastas

logger = logging.getLogger(__name__)

HOST = '127.0.0.1'
OCIOSIDADE = 600.0
TIMEOUT_PARTIDA = 180.0
TIMEOUT_PARADA = 10.0
FALHAS_ATE_DESISTIR = 3
NAMESPACE = 'open_notebook'
USUARIO_BANCO = 'concurso'
VARIAVEL_CIFRA = 'CONCURSO_OPEN_NOTEBOOK_CIFRA'
DICA = 'a busca continua nos seus livros pelo app; tente de novo mais tarde ou reinicie o app'
_SEGREDOS_DO_AMBIENTE = ('_API_KEY', '_API_BASE', 'OPEN_NOTEBOOK_', 'SURREAL_', 'OPENAI_COMPATIBLE_')


@dataclass(frozen=True)
class Processo:
    nome: str
    argv: list[str]
    cwd: Path
    ambiente: dict[str, str]
    saude: str | None = None


@dataclass(frozen=True)
class Sessao:
    url: str
    senha: str
    porta_surreal: int
    porta_embeddings: int
    porta_api: int
    token_embeddings: str


@dataclass(frozen=True)
class Segredos:
    senha_api: str
    senha_banco: str
    token_embeddings: str
    cifra: str


Montador = Callable[[Path, Pastas, Sessao, Segredos, Mapping[str, str]], list[Processo]]


def senha_do_banco(cifra: str) -> str:
    """O SurrealDB grava o usuário na primeira partida; a senha precisa ser a mesma nas seguintes."""
    return hmac.new(cifra.encode(), b'surrealdb', hashlib.sha256).hexdigest()


def porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def python_do_pacote(raiz: Path) -> Path:
    return raiz / 'python' / ('python.exe' if sys.platform == 'win32' else 'bin/python3')


def ambiente_limpo(base: Mapping[str, str]) -> dict[str, str]:
    """O ambiente do app sem chaves de provedores nem variáveis do open-notebook do usuário."""
    return {
        nome: valor
        for nome, valor in base.items()
        if not any(marca in nome for marca in _SEGREDOS_DO_AMBIENTE)
        and nome not in ('PYTHONPATH', 'PYTHONHOME')
    }


def preparar_dados(raiz: Path, pastas: Pastas) -> None:
    """A API lê as migrations por caminho relativo à pasta atual, que é `dados/`."""
    origem = raiz / 'open-notebook' / 'open_notebook' / 'database' / 'migrations'
    destino = pastas.dados / 'open_notebook' / 'database' / 'migrations'
    shutil.rmtree(destino, ignore_errors=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(origem, destino)


def processos_do_pacote(
    raiz: Path, pastas: Pastas, sessao: Sessao, segredos: Segredos, ambiente_ia: Mapping[str, str]
) -> list[Processo]:
    preparar_dados(raiz, pastas)
    python = str(python_do_pacote(raiz))
    codigo = raiz / 'open-notebook'
    base = ambiente_limpo(os.environ) | {'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1', 'NO_COLOR': '1'}
    surreal = base | {
        'SURREAL_USER': USUARIO_BANCO,
        'SURREAL_PASS': segredos.senha_banco,
        'SURREAL_LOG': 'warn',
    }
    embeddings = base | {'EMBEDDINGS_TOKEN': segredos.token_embeddings}
    open_notebook = (
        base
        | {
            'SURREAL_URL': f'ws://{HOST}:{sessao.porta_surreal}/rpc',
            'SURREAL_USER': USUARIO_BANCO,
            'SURREAL_PASSWORD': segredos.senha_banco,
            'SURREAL_NAMESPACE': NAMESPACE,
            'SURREAL_DATABASE': NAMESPACE,
            'OPEN_NOTEBOOK_PASSWORD': segredos.senha_api,
            'OPEN_NOTEBOOK_ENCRYPTION_KEY': segredos.cifra,
            'PYTHONPATH': str(codigo),
            'PROMPTS_PATH': str(codigo / 'prompts'),
            'TIKTOKEN_CACHE_DIR': str(raiz / 'tiktoken'),
            'OPENAI_COMPATIBLE_BASE_URL_EMBEDDING': f'http://{HOST}:{sessao.porta_embeddings}/v1',
            'OPENAI_COMPATIBLE_API_KEY_EMBEDDING': segredos.token_embeddings,
        }
        | dict(ambiente_ia)
    )
    executavel = raiz / 'bin' / ('surreal.exe' if sys.platform == 'win32' else 'surreal')
    return [
        Processo(
            'surreal',
            [str(executavel), 'start', '--bind', f'{HOST}:{sessao.porta_surreal}', f'rocksdb:{pastas.banco}'],
            pastas.dados,
            surreal,
            f'http://{HOST}:{sessao.porta_surreal}/health',
        ),
        Processo(
            'embeddings',
            [
                python,
                str(raiz / 'servidor_embeddings.py'),
                '--porta',
                str(sessao.porta_embeddings),
                '--modelo',
                str(raiz / 'modelo'),
            ],
            pastas.dados,
            embeddings,
            f'http://{HOST}:{sessao.porta_embeddings}/health',
        ),
        Processo(
            'api',
            [
                python,
                '-m',
                'uvicorn',
                'api.main:app',
                '--host',
                HOST,
                '--port',
                str(sessao.porta_api),
                '--log-level',
                'warning',
            ],
            pastas.dados,
            open_notebook,
            f'{sessao.url}/health',
        ),
        Processo(
            'worker',
            [python, '-m', 'surreal_commands.cli.worker', '--import-modules', 'commands'],
            pastas.dados,
            open_notebook,
        ),
    ]


class _Trava:
    """Trava de instância única: o RocksDB do SurrealDB não aceita dois donos."""

    def __init__(self, caminho: Path) -> None:
        self.caminho = caminho
        self._arquivo: IO[bytes] | None = None

    def adquirir(self) -> bool:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        arquivo = self.caminho.open('a+b')
        try:
            if sys.platform == 'win32':
                import msvcrt

                arquivo.seek(0)
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            arquivo.close()
            return False
        self._arquivo = arquivo
        return True

    def liberar(self) -> None:
        if self._arquivo is None:
            return
        with contextlib.suppress(OSError):
            if sys.platform == 'win32':
                import msvcrt

                self._arquivo.seek(0)
                msvcrt.locking(self._arquivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._arquivo.fileno(), fcntl.LOCK_UN)
        self._arquivo.close()
        self._arquivo = None


class _GrupoWindows:
    """Job Object com KILL_ON_JOB_CLOSE: se o app morrer, o Windows mata os processos junto."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class _Basica(ctypes.Structure):
            _fields_ = [
                ('PerProcessUserTimeLimit', ctypes.c_int64),
                ('PerJobUserTimeLimit', ctypes.c_int64),
                ('LimitFlags', wintypes.DWORD),
                ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', wintypes.DWORD),
                ('Affinity', ctypes.c_size_t),
                ('PriorityClass', wintypes.DWORD),
                ('SchedulingClass', wintypes.DWORD),
            ]

        class _Io(ctypes.Structure):
            _fields_ = [(nome, ctypes.c_uint64) for nome in ('r', 'w', 'o', 'rt', 'wt', 'ot')]

        class _Estendida(ctypes.Structure):
            _fields_ = [
                ('BasicLimitInformation', _Basica),
                ('IoInfo', _Io),
                ('ProcessMemoryLimit', ctypes.c_size_t),
                ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t),
                ('PeakJobMemoryUsed', ctypes.c_size_t),
            ]

        self._kernel = ctypes.windll.kernel32
        self._job = self._kernel.CreateJobObjectW(None, None)
        info = _Estendida()
        info.BasicLimitInformation.LimitFlags = 0x2000
        self._kernel.SetInformationJobObject(self._job, 9, ctypes.byref(info), ctypes.sizeof(info))

    def incluir(self, processo: subprocess.Popen) -> None:
        self._kernel.AssignProcessToJobObject(self._job, int(processo._handle))  # noqa: SLF001


def _morrer_com_o_pai() -> None:
    with contextlib.suppress(Exception):
        import ctypes
        import signal

        ctypes.CDLL('libc.so.6', use_errno=True).prctl(1, signal.SIGTERM)


def _abrir(processo: Processo, log: IO[bytes]) -> subprocess.Popen:
    opcoes: dict = {}
    if sys.platform == 'win32':
        opcoes['creationflags'] = subprocess.CREATE_NO_WINDOW
    else:
        opcoes['start_new_session'] = True
        if sys.platform.startswith('linux'):
            opcoes['preexec_fn'] = _morrer_com_o_pai
    return subprocess.Popen(
        processo.argv,
        cwd=processo.cwd,
        env=processo.ambiente,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        **opcoes,
    )


def _responde(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as resposta:
            return resposta.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


@dataclass
class _Rodando:
    processo: Processo
    popen: subprocess.Popen
    log: IO[bytes]


@dataclass
class Supervisor:
    pastas: Pastas
    logs: Path
    chave_cifra: Callable[[], str]
    montar: Montador = processos_do_pacote
    ambiente_ia: Callable[[], Mapping[str, str]] = dict
    ao_subir: list[Callable[[Sessao], None]] = field(default_factory=list)
    ociosidade: float = OCIOSIDADE
    timeout_partida: float = TIMEOUT_PARTIDA
    relogio: Callable[[], float] = time.monotonic
    _rodando: list[_Rodando] = field(default_factory=list)
    _sessao: Sessao | None = None
    _ultimo_uso: float = 0.0
    _falhas: int = 0
    _trava: _Trava | None = None
    _grupo: object | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock)

    @property
    def indisponivel(self) -> bool:
        return self._falhas >= FALHAS_ATE_DESISTIR

    @property
    def sessao(self) -> Sessao | None:
        return self._sessao if self._vivos() else None

    def _vivos(self) -> bool:
        return bool(self._rodando) and all(r.popen.poll() is None for r in self._rodando)

    def usar(self) -> None:
        self._ultimo_uso = self.relogio()

    def garantir(self) -> Sessao:
        """A sessão em uso, subindo os processos se preciso."""
        with self._lock:
            self.usar()
            if self._sessao is not None and self._vivos():
                return self._sessao
            if self._rodando:
                logger.warning('open-notebook: um processo caiu; subindo de novo')
                self._parar_processos()
            if self.indisponivel:
                raise ErroDoAmbiente('a biblioteca não conseguiu abrir agora', DICA)
            raiz = instalacao.instalado(self.pastas)
            if raiz is None:
                raise ErroDoAmbiente(
                    'a biblioteca ainda não foi preparada', 'abra Estudar e clique em "Preparar agora"'
                )
            if self._trava is None:
                trava = _Trava(self.pastas.trava)
                if not trava.adquirir():
                    raise ErroDoAmbiente(
                        'a biblioteca já está aberta em outra janela do app', 'feche a outra janela'
                    )
                self._trava = trava
            nova_versao = instalacao.precisa_de_backup(self.pastas)
            if nova_versao:
                instalacao.fazer_backup(self.pastas, instalacao.ler_estado(self.pastas).atual or '')
            try:
                sessao = self._subir(raiz)
            except ErroDoAmbiente:
                self._falhas += 1
                if nova_versao and instalacao.voltar_ao_anterior(self.pastas):
                    return self.garantir()
                raise
            self._falhas = 0
            instalacao.registrar_partida(self.pastas)
            return sessao

    def _subir(self, raiz: Path) -> Sessao:
        self.pastas.banco.parent.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        porta_api = porta_livre()
        cifra = self.chave_cifra()
        segredos = Segredos(
            senha_api=secrets.token_urlsafe(32),
            senha_banco=senha_do_banco(cifra),
            token_embeddings=secrets.token_urlsafe(32),
            cifra=cifra,
        )
        sessao = Sessao(
            url=f'http://{HOST}:{porta_api}',
            senha=segredos.senha_api,
            porta_surreal=porta_livre(),
            porta_embeddings=porta_livre(),
            porta_api=porta_api,
            token_embeddings=segredos.token_embeddings,
        )
        if sys.platform == 'win32' and self._grupo is None:
            with contextlib.suppress(Exception):
                self._grupo = _GrupoWindows()
        try:
            for processo in self.montar(raiz, self.pastas, sessao, segredos, self.ambiente_ia()):
                log = (self.logs / f'open-notebook-{processo.nome}.log').open('ab')
                popen = _abrir(processo, log)
                if self._grupo is not None:
                    with contextlib.suppress(Exception):
                        self._grupo.incluir(popen)
                rodando = _Rodando(processo, popen, log)
                self._rodando.append(rodando)
                self._esperar(rodando)
            for gancho in self.ao_subir:
                gancho(sessao)
        except ErroDoAmbiente:
            self._parar_processos()
            raise
        except Exception as erro:
            self._parar_processos()
            logger.exception('open-notebook: falha ao subir')
            raise ErroDoAmbiente('a biblioteca não conseguiu abrir agora', DICA) from erro
        self._sessao = sessao
        logger.info('open-notebook: em uso (%s)', ', '.join(r.processo.nome for r in self._rodando))
        return sessao

    def _esperar(self, rodando: _Rodando) -> None:
        limite = self.relogio() + self.timeout_partida
        while True:
            if rodando.popen.poll() is not None:
                logger.error(
                    'open-notebook: %s saiu com %s; veja %s',
                    rodando.processo.nome,
                    rodando.popen.returncode,
                    self.logs / f'open-notebook-{rodando.processo.nome}.log',
                )
                raise ErroDoAmbiente('a biblioteca não conseguiu abrir agora', DICA)
            if rodando.processo.saude is None:
                time.sleep(0.5)
                if rodando.popen.poll() is None:
                    return
                continue
            if _responde(rodando.processo.saude):
                return
            if self.relogio() > limite:
                logger.error(
                    'open-notebook: %s não respondeu em %.0f s', rodando.processo.nome, self.timeout_partida
                )
                raise ErroDoAmbiente('a biblioteca demorou demais para abrir', DICA)
            time.sleep(0.2)

    def _parar_processos(self) -> None:
        for rodando in reversed(self._rodando):
            popen = rodando.popen
            if popen.poll() is None:
                with contextlib.suppress(OSError):
                    if sys.platform != 'win32':
                        os.killpg(popen.pid, 15)
                    else:
                        popen.terminate()
                try:
                    popen.wait(TIMEOUT_PARADA)
                except subprocess.TimeoutExpired:
                    with contextlib.suppress(OSError):
                        if sys.platform != 'win32':
                            os.killpg(popen.pid, 9)
                        else:
                            popen.kill()
                    popen.wait(TIMEOUT_PARADA)
            rodando.log.close()
        self._rodando.clear()
        self._sessao = None

    def parar(self) -> None:
        with self._lock:
            self._parar_processos()
            if self._trava is not None:
                self._trava.liberar()
                self._trava = None

    def parar_se_ocioso(self) -> bool:
        with self._lock:
            if self._rodando and self.relogio() - self._ultimo_uso >= self.ociosidade:
                logger.info('open-notebook: parado depois de %.0f s sem uso', self.ociosidade)
                self.parar()
                return True
            return False

    def vigiar(self, intervalo: float = 60.0) -> threading.Thread:
        """Linha de fundo que para os processos ociosos; morre com o app."""

        def laco() -> None:
            while True:
                time.sleep(intervalo)
                with contextlib.suppress(Exception):
                    self.parar_se_ocioso()

        linha = threading.Thread(target=laco, name='vigia-open-notebook', daemon=True)
        linha.start()
        return linha
