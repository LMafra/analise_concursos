import logging
import shutil
from pathlib import Path, PureWindowsPath

from nicegui import events, run, ui

from concursos import planilha_tec
from concursos.aplicacao import cadastro, captura_tec, pratica
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.resultados import abrir_no_navegador, resultados
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro
from concursos.linguagem import rotulo_do_arquivo

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
        conteudo()


def conteudo() -> None:
    with ui.column().classes('w-full').style(tema.gap('md')):
        PainelTec()


class PainelTec:
    def __init__(self) -> None:
        ui.label(
            'Solte aqui o relatório do TEC (.csv ou .xlsx). Tudo fica salvo apenas neste computador.'
        ).classes('ca-texto-suave')
        with ui.expansion('Como conseguir o arquivo', icon='help').classes('w-full'):
            ui.label(COMO_CONSEGUIR).classes('text-sm').mark('como-conseguir')
        self.upload = (
            ui.upload(
                multiple=True,
                auto_upload=True,
                label='Soltar o relatório do TEC ou clicar para escolher',
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
        resumo_da_pratica()
        with ui.expansion('Instalar a captura do TEC', icon='extension').classes('w-full'):
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
                ui.label(rotulo_do_arquivo(copiado.name)).classes('font-mono text-sm')
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
                ui.label(rotulo_do_arquivo(previsao.arquivo.name)).classes('font-mono text-sm')
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


def resumo_da_pratica() -> None:
    """Uma linha de situação. O texto completo fica fechado, para a tela não virar um relatório."""
    try:
        achados = resultados(ESTADO.contexto())
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
        return
    if not achados.pratica:
        return
    situacao = _situacao_curta()
    if situacao:
        with ui.card().classes('w-full').style(tema.gap('xs')):
            ui.label('Situação atual da prática no TEC').classes('text-sm ca-texto-suave')
            ui.label(situacao).classes('text-h6 font-bold')
    with ui.expansion('Ver o resumo', icon='article').classes('w-full'):
        ui.markdown(achados.pratica).classes('w-full').mark('pratica')


def _situacao_curta() -> str | None:
    from concursos.analytics.dashboard_fontes import kpis_tec, metas_do_toml, metas_padrao
    from concursos.config.contexto import ler_toml

    try:
        contexto = ESTADO.contexto()
        metas = metas_padrao()
        if contexto.config_projeto.is_file():
            metas = metas_do_toml(ler_toml(contexto.config_projeto))
        painel = kpis_tec(contexto.analises_do_candidato, metas)
    except Exception:  # noqa: BLE001
        return None
    if not painel.kpis:
        return None
    return painel.kpis[0].valor


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
