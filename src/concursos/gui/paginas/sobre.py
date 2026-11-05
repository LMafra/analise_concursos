import platform
import shutil
from importlib.metadata import version
from pathlib import Path

from nicegui import ui

from concursos.aplicacao.resultados import abrir_no_navegador
from concursos.empacotado import embutido
from concursos.gui.progresso import arquivo_de_log

PRIVACIDADE = (
    'Nada sai do seu computador, salvo as integrações que você ligar (IA para ler editais, open-notebook, '
    'PCI Concursos), e cada uma mostra antes o que envia. A janela só atende no próprio computador '
    '(127.0.0.1).'
)


def versao() -> str:
    return version('concurso-analise')


def pagina() -> None:
    with ui.column().classes('w-full max-w-2xl gap-3'):
        ui.label(f'concurso-analise {versao()}').classes('text-2xl font-bold').mark('versao')
        ui.label(f'{platform.system()} {platform.machine()}, Python {platform.python_version()}')
        log = arquivo_de_log()
        with ui.row().classes('items-center gap-2'):
            ui.label(f'Log: {log}' if log else 'Log: desligado nesta execução').mark('log')
            if log:
                ui.button(
                    'Abrir a pasta', icon='folder_open', on_click=lambda: abrir_no_navegador(Path(log).parent)
                ).props('flat dense')
        tesseract = shutil.which('tesseract')
        ui.label(
            f'Tesseract: {"embutido" if embutido(tesseract) else tesseract}'
            if tesseract
            else 'Tesseract: não encontrado; PDFs escaneados (sem texto) não são lidos, e as respostas '
            'podem ser digitadas se a folha não for lida'
        ).mark('tesseract')
        ui.label(PRIVACIDADE).classes('text-grey-8')
