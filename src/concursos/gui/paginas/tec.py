import logging
import shutil
from pathlib import Path, PureWindowsPath

from nicegui import events, run, ui

from concursos import planilha_tec
from concursos.aplicacao import cadastro, captura_tec, pratica
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.resultados import abrir_no_navegador
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.dialogo import ver_texto
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
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


COMO_CONSEGUIR = (
    'Como conseguir o arquivo: no TEC, exporte o histórico das questões que resolveu para uma planilha, ou '
    'use a captura tec-erros (abaixo), que guarda cada erro enquanto você resolve. O app não acessa o TEC: '
    'ele só lê o arquivo que você trouxer.'
)
SEM_COLUNA = ''


def pagina() -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full max-w-4xl').style(tema.gap('md')):
        ui.label('Importar do TEC').classes('text-2xl font-bold')
        PainelTec()


class PainelTec:
    def __init__(self) -> None:
        ui.label(
            'Solte a planilha que você exportou do TEC (.csv ou .xlsx) ou os arquivos tec-erros-*.json da '
            'captura (computador e tablet juntos) e, se usa o caderno de erros, o caderno-estado.json. A prática '
            'entra na próxima análise.'
        ).classes('text-sm')
        ui.label(COMO_CONSEGUIR).classes('text-sm').mark('como-conseguir')
        self.upload = (
            ui.upload(
                multiple=True,
                auto_upload=True,
                label='Soltar a planilha ou as exportações, ou clicar para escolher',
                on_multi_upload=self.receber,
            )
            .props('accept=".json,.csv,.xlsx"')
            .classes('w-full')
            .mark('soltar-tec')
        )
        self.conferencia = ui.column().classes('w-full')
        self.resultado = ui.column().classes('w-full')
        self.envio: Path | None = None
        self.colunas: list[tuple[pratica.PrevisaoPlanilha, dict[str, ui.select]]] = []
        saidas_da_ultima_analise()
        ui.separator()
        instrucoes_da_captura()

    async def receber(self, evento: events.MultiUploadEventArguments) -> None:
        contexto = ESTADO.contexto()
        envio = cadastro.nova_pasta_de_envio(contexto)
        previsoes: list[pratica.PrevisaoPlanilha] = []
        try:
            caminhos = []
            for arquivo in evento.files:
                caminho = envio / Path(PureWindowsPath(arquivo.name).name).name
                await arquivo.save(caminho)
                caminhos.append(caminho)
            exportacoes = [c for c in caminhos if not pratica.eh_planilha(c)]
            copiados = (
                await run.io_bound(pratica.importar_exportacoes, Opcoes(contexto), exportacoes)
                if exportacoes
                else []
            )
            for planilha in (c for c in caminhos if pratica.eh_planilha(c)):
                previsoes.append(await run.io_bound(pratica.prever_planilha, contexto, planilha))
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha ao importar a prática pela GUI', exc_info=True)
            mostrar_erro(erro)
            shutil.rmtree(envio, ignore_errors=True)
            return
        finally:
            self.upload.reset()
        if previsoes:
            self.descartar_envio()
            self.envio = envio
            self.conferir(previsoes)
        else:
            shutil.rmtree(envio, ignore_errors=True)
        if copiados:
            self.mostrar_copiados(copiados)

    def mostrar_copiados(self, copiados: list[Path]) -> None:
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

    def conferir(self, previsoes: list[pratica.PrevisaoPlanilha]) -> None:
        self.conferencia.clear()
        self.colunas = []
        with self.conferencia, ui.card().classes('w-full').mark('conferir-colunas'):
            ui.label('Confira as colunas').classes('font-bold')
            ui.label(
                'O app reconheceu as colunas pelo nome. Troque a que estiver errada; Disciplina e Resultado são '
                'obrigatórias. Uma planilha com as mesmas colunas já vem conferida da próxima vez.'
            ).classes('text-sm')
            for previsao in previsoes:
                ui.label(previsao.arquivo.name).classes('font-mono text-sm')
                opcoes = {SEM_COLUNA: 'Nenhuma', **{c: c for c in previsao.cabecalho if c}}
                selects = {}
                with ui.row().classes('w-full').style(tema.gap('md')):
                    for campo in planilha_tec.CAMPOS:
                        obrigatorio = campo in planilha_tec.OBRIGATORIOS
                        selects[campo] = (
                            ui.select(
                                opcoes,
                                value=previsao.mapeamento[campo] or SEM_COLUNA,
                                label=planilha_tec.ROTULOS[campo] + (' (obrigatória)' if obrigatorio else ''),
                            )
                            .classes('min-w-40')
                            .mark(f'coluna-{campo}')
                        )
                if previsao.amostra:
                    colunas = [
                        {'name': c, 'label': c, 'field': c, 'align': 'left'} for c in previsao.cabecalho if c
                    ]
                    ui.table(columns=colunas, rows=previsao.amostra).props('dense flat').classes('w-full')
                self.colunas.append((previsao, selects))
            ui.label(
                'Na análise, o app pergunta a qual tópico do edital vai cada assunto que ele não reconheceu.'
            ).classes('text-sm')
            ui.button('Importar e analisar', icon='play_arrow', on_click=self.importar_planilhas).mark(
                'importar-planilha'
            )

    async def importar_planilhas(self) -> None:
        contexto = ESTADO.contexto()
        try:
            for previsao, selects in self.colunas:
                mapeamento = {campo: select.value or None for campo, select in selects.items()}
                await run.io_bound(pratica.importar_planilha, Opcoes(contexto), previsao.arquivo, mapeamento)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha ao importar a planilha do TEC pela GUI', exc_info=True)
            with self.conferencia:
                mostrar_erro(erro)
            return
        self.descartar_envio()
        analisar()

    def descartar_envio(self) -> None:
        if self.envio is not None:
            shutil.rmtree(self.envio, ignore_errors=True)
            self.envio = None


def saidas_da_ultima_analise() -> None:
    saidas = pratica.saidas_da_pratica(ESTADO.contexto())
    if saidas.resumo is None and saidas.simulado is None:
        return
    with ui.row().style(tema.gap('sm')).mark('saidas-pratica'):
        if saidas.resumo is not None:
            ui.button(
                'Ver prioridades',
                icon='flag',
                on_click=lambda: ver_texto('Prioridades da prática', saidas.resumo),
            ).props('outline').mark('ver-prioridades')
        if saidas.simulado is not None:
            ui.button(
                'Ver simulado com meus erros',
                icon='quiz',
                on_click=lambda: abrir_no_navegador(saidas.simulado),
            ).props('outline').mark('ver-simulado-tec')


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
