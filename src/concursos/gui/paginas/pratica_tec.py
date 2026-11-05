import logging
import shutil
from pathlib import Path, PureWindowsPath

from nicegui import events, run, ui

from concursos.aplicacao import cadastro, captura_tec, pratica
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.resultados import abrir_no_navegador
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.estado import ESTADO
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro

logger = logging.getLogger('concursos')

PASSOS_CHROME = [
    'Clique em "Abrir a pasta da extensão".',
    'No Chrome, abra chrome://extensions e ligue o Modo do desenvolvedor, no canto superior direito.',
    'Clique em Carregar sem compactação e escolha a pasta extensao-chrome que abriu.',
    'Num caderno do TEC, quando errar uma questão, aparece "Erro guardado". No ícone da extensão, use '
    'Baixar JSON e solte o arquivo aqui em cima.',
]
PASSOS_ANDROID = [
    'Instale o Firefox pela Play Store e, nele, a extensão Violentmonkey (menu ⋮, Extensões).',
    'Copie o arquivo tec-erros.user.js para o tablet (clique em "Abrir a pasta dos arquivos") e abra-o no '
    'Firefox; o Violentmonkey pede para confirmar a instalação.',
    'Resolva os cadernos pelo site do TEC no Firefox. No botão "✗", use Baixar JSON e traga o arquivo para '
    'cá.',
]


class PainelTec:
    def __init__(self) -> None:
        ui.label('Importar a prática').classes('text-lg font-bold')
        ui.label(
            'Solte os arquivos tec-erros-*.json exportados pela captura (computador e tablet juntos) e, se usa '
            'o caderno de erros, o caderno-estado.json. A prática entra na próxima análise.'
        ).classes('text-sm')
        self.upload = (
            ui.upload(
                multiple=True,
                auto_upload=True,
                label='Soltar as exportações ou clicar para escolher',
                on_multi_upload=self.receber,
            )
            .props('accept=".json"')
            .classes('w-full')
            .mark('soltar-tec')
        )
        self.resultado = ui.column().classes('w-full')
        ui.separator()
        instrucoes_da_captura()

    async def receber(self, evento: events.MultiUploadEventArguments) -> None:
        contexto = ESTADO.contexto()
        envio = cadastro.nova_pasta_de_envio(contexto)
        try:
            caminhos = []
            for arquivo in evento.files:
                caminho = envio / Path(PureWindowsPath(arquivo.name).name).name
                await arquivo.save(caminho)
                caminhos.append(caminho)
            copiados = await run.io_bound(pratica.importar_exportacoes, Opcoes(contexto), caminhos)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha ao importar a prática pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            shutil.rmtree(envio, ignore_errors=True)
            self.upload.reset()
        self.resultado.clear()
        with (
            self.resultado,
            aviso(f'{len(copiados)} arquivo(s) copiados para {copiados[0].parent}.', tom=Tom.SUCESSO).mark(
                'tec-importado'
            ),
        ):
            for copiado in copiados:
                ui.label(copiado.name).classes('font-mono text-sm')
            ui.button('Analisar agora', icon='play_arrow', on_click=analisar)


def analisar() -> None:
    ESTADO.pedir_analise = True
    ui.navigate.to('/analise')


def passos(titulo: str, itens: list[str]) -> None:
    ui.label(titulo).classes('font-bold')
    with ui.element('ol').classes('list-decimal pl-6'):
        for item in itens:
            with ui.element('li'):
                ui.label(item)


def instrucoes_da_captura() -> None:
    ui.label('Instalar a captura do TEC').classes('text-lg font-bold')
    captura = captura_tec.localizar()
    if captura is None:
        with ui.column().mark('sem-captura'):
            ui.label('Os arquivos da captura não vêm com esta instalação. Veja como obtê-los e instalar:')
            ui.link(captura_tec.INSTRUCOES, captura_tec.INSTRUCOES, new_tab=True)
        return
    with ui.column().classes('w-full').style(tema.gap('md')).mark('captura-tec'):
        passos('No Chrome (computador)', PASSOS_CHROME)
        with ui.row():
            ui.button(
                'Abrir a pasta da extensão',
                icon='folder_open',
                on_click=lambda: abrir_no_navegador(captura.extensao),
            ).mark('abrir-extensao')
        passos('No tablet Android', PASSOS_ANDROID)
        ui.button(
            'Abrir a pasta dos arquivos',
            icon='folder_open',
            on_click=lambda: abrir_no_navegador(captura.pasta),
        ).props('outline').mark('abrir-pasta-captura')
        ui.label('Caderno de erros').classes('font-bold')
        ui.label(
            'Uma página que funciona sem internet: importa as exportações e mostra os erros para revisar.'
        ).classes('text-sm')
        ui.button(
            'Abrir o caderno de erros', icon='menu_book', on_click=lambda: abrir_no_navegador(captura.caderno)
        ).props('outline').mark('abrir-caderno')
