"""Se a GUI abre na janela do sistema ou no navegador, e se o usuário precisa saber por quê."""

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path

from concursos.modelo import DecisaoJanela

WEBVIEW2 = r'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
CHAVES_WEBVIEW2: tuple[tuple[str, str], ...] = (
    ('HKLM', rf'SOFTWARE\WOW6432Node\{WEBVIEW2}'),
    ('HKLM', rf'SOFTWARE\{WEBVIEW2}'),
    ('HKCU', rf'Software\{WEBVIEW2}'),
)
URL_WEBVIEW2 = 'https://developer.microsoft.com/microsoft-edge/webview2/'
VARIAVEL_JANELA_FALHOU = 'CONCURSO_JANELA_FALHOU'
TITULO_AVISO = 'Componente de janela indisponível; o app abre no navegador.'
TEXTO_AVISO = (
    'O concurso-analise abre numa janela própria com o Microsoft Edge WebView2, que não está instalado ou não '
    'abriu neste computador. Tudo funciona igual no navegador. Para ter a janela, instale o WebView2 '
    '(gratuito, da Microsoft) e abra o app de novo.'
)

LerRegistro = Callable[[str, str], str | None]
VersaoPeloLoader = Callable[[], str | None]


def ler_registro_windows(raiz: str, chave: str) -> str | None:
    import winreg

    base = winreg.HKEY_LOCAL_MACHINE if raiz == 'HKLM' else winreg.HKEY_CURRENT_USER
    try:
        with winreg.OpenKey(base, chave) as aberta:
            valor, _ = winreg.QueryValueEx(aberta, 'pv')
    except OSError:
        return None
    return valor if isinstance(valor, str) else None


def caminho_do_loader() -> Path | None:
    """O `WebView2Loader.dll` que vem com o pywebview, sem importar o pywebview."""
    especificacao = importlib.util.find_spec('webview')
    if especificacao is None or especificacao.origin is None:
        return None
    caminho = (
        Path(especificacao.origin).parent / 'lib' / 'runtimes' / 'win-x64' / 'native' / 'WebView2Loader.dll'
    )
    return caminho if caminho.is_file() else None


def versao_pelo_loader_windows() -> str | None:
    """Pergunta ao próprio loader da Microsoft, que acha o runtime mesmo fora das chaves do registro."""
    import ctypes

    caminho = caminho_do_loader()
    if caminho is None:
        return None
    loader = ctypes.WinDLL(str(caminho))
    versao = ctypes.c_void_p()
    if (
        loader.GetAvailableCoreWebView2BrowserVersionString(None, ctypes.byref(versao)) != 0
        or not versao.value
    ):
        return None
    try:
        return ctypes.wstring_at(versao.value) or None
    finally:
        ctypes.windll.ole32.CoTaskMemFree(versao)


def webview2_no_registro(ler_registro: LerRegistro) -> bool:
    for raiz, chave in CHAVES_WEBVIEW2:
        versao = ler_registro(raiz, chave)
        if versao and versao != '0.0.0.0':
            return True
    return False


def decidir_janela(
    sistema: str = sys.platform,
    *,
    navegador: bool = False,
    ler_registro: LerRegistro | None = None,
    versao_pelo_loader: VersaoPeloLoader | None = None,
) -> DecisaoJanela:
    """No Linux, o navegador (WebKitGTK e Qt variam demais); no Windows, a janela só com o WebView2."""
    if navegador:
        return DecisaoJanela.NAVEGADOR_PEDIDO
    if sistema.startswith('linux'):
        return DecisaoJanela.NAVEGADOR_LINUX
    if sistema != 'win32':
        return DecisaoJanela.NATIVA
    if webview2_no_registro(ler_registro or ler_registro_windows):
        return DecisaoJanela.NATIVA
    try:
        versao = (versao_pelo_loader or versao_pelo_loader_windows)()
    except (OSError, AttributeError):
        versao = None
    return DecisaoJanela.NATIVA if versao else DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2


def mostrar_aviso(decisao: DecisaoJanela, *, dispensado: bool, janela_falhou: bool) -> bool:
    """A falha da janela avisa sempre: o "Entendi" valia para a falta do WebView2, não para uma janela quebrada."""
    if janela_falhou:
        return True
    return decisao is DecisaoJanela.NAVEGADOR_SEM_WEBVIEW2 and not dispensado


def comando_para_reabrir(*, congelado: bool, executavel: str, projeto: Path | None) -> list[str]:
    if congelado:
        comando = [executavel, 'gui', '--browser']
    else:
        comando = [
            executavel,
            '-c',
            'import sys; from concursos.cli import main; sys.exit(main(sys.argv[1:]))',
            'gui',
            '--browser',
        ]
    return [*comando, '--project', str(projeto)] if projeto is not None else comando
