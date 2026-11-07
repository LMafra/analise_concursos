from importlib.metadata import version
from pathlib import Path

from nicegui import app, run, ui

from concursos import doctor as diagnostico
from concursos.aplicacao import atualizador as atualizacao
from concursos.aplicacao import projeto, sobre
from concursos.aplicacao.resultados import abrir_no_navegador
from concursos.config.contexto import resolver_home
from concursos.gui import tema
from concursos.gui.componentes.cartao import cartao
from concursos.gui.componentes.dialogo import Dialogo
from concursos.gui.componentes.situacao import situacao
from concursos.gui.estado import ESTADO
from concursos.gui.progresso import arquivo_de_log
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro

PRIVACIDADE = (
    'Privacidade: tudo fica no seu computador. Só sai algo se você ligar a IA, a busca de concursos ou os '
    'avisos de versão nova; cada um mostra antes o que é enviado. Os seus livros não saem do computador.'
)
CONSULTA = 'Consulta o GitHub (só o arquivo da versão mais nova; nenhum dado seu vai junto).'
FORA_DO_EXECUTAVEL = 'Instalado pelo uv: atualize com `uv tool upgrade concurso-analise`.'
SEGUNDOS_PARA_FECHAR = 3


def versao() -> str:
    return version('concurso-analise')


def pagina() -> None:
    resumo = sobre.resumo_do_app(resolver_home())
    with ui.column().classes('w-full max-w-2xl').style(tema.gap('md')):
        ui.label(f'concurso-analise {versao()}').classes('text-2xl font-bold').mark('versao')
        with ui.row().classes('items-center').style(tema.gap('md')):
            ui.label(resumo.sistema).mark('sistema')
            situacao(
                f'Leitor de folhas: {resumo.leitor_de_folhas}',
                Tom.SUCESSO if resumo.leitor_pronto else Tom.ALERTA,
            ).mark('tesseract')
            situacao(
                f'Biblioteca: {resumo.biblioteca}', Tom.SUCESSO if resumo.biblioteca_pronta else Tom.INFO
            ).mark('biblioteca')
        log = arquivo_de_log()
        with ui.row().classes('items-center').style(tema.gap('sm')):
            ui.label('Registro de erros:' if log else 'Registro de erros: desligado nesta execução').mark(
                'log'
            )
            if log:
                ui.button(
                    'Abrir a pasta', icon='folder_open', on_click=lambda: abrir_no_navegador(Path(log).parent)
                ).props('flat dense').mark('abrir-registro')
        SecaoDeAtualizacao(resumo.biblioteca_pronta)
        if ESTADO.projeto is not None:
            secao_do_ambiente()
        ui.label(PRIVACIDADE).classes('ca-texto-suave')


def secao_do_ambiente() -> None:
    """O `doctor`: só leitura e sem rede."""
    with cartao('Ambiente', icone='health_and_safety'):
        saida = ui.label().classes('whitespace-pre-line font-mono text-sm').mark('diagnostico')

        async def conferir() -> None:
            botao.props(add='loading')
            try:
                itens = await run.io_bound(projeto.diagnosticar, ESTADO.contexto())
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            finally:
                botao.props(remove='loading')
            saida.set_text(diagnostico.formatar(itens))

        botao = (
            ui.button('Conferir o ambiente', icon='fact_check', on_click=conferir)
            .props('outline')
            .mark('conferir-ambiente')
        )


class SecaoDeAtualizacao:
    """A consulta só acontece no clique; instalar pede confirmação e mostra o progresso do download."""

    def __init__(self, biblioteca_pronta: bool = False) -> None:
        self.fracao = 0.0
        self.do_app = atualizacao.no_executavel()
        self.da_biblioteca = biblioteca_pronta
        with cartao('Atualizações', icone='update'):
            if not self.do_app:
                ui.label(FORA_DO_EXECUTAVEL).classes('font-mono text-sm').mark('atualizar-pelo-uv')
                if not self.da_biblioteca:
                    return
            self.canal = atualizacao.ler_preferencias(resolver_home() / 'config.toml').canal
            with ui.row().classes('items-center').style(tema.gap('sm')):
                self.botao = ui.button(self.rotulo(), icon='update', on_click=self.verificar).mark(
                    'verificar-atualizacoes'
                )
                if self.do_app:
                    ui.label(f'canal {self.canal.value}').classes('text-sm ca-texto-suave')
            ui.label(CONSULTA).classes('text-sm ca-texto-suave')
            self.situacao = ui.label().mark('situacao-atualizacao')
            self.area = ui.column().classes('w-full').style(tema.gap('sm'))
            self.situacao_biblioteca = ui.label().mark('situacao-biblioteca')
            self.area_biblioteca = ui.column().classes('w-full').style(tema.gap('sm'))
            if self.do_app and ESTADO.novidade is not None:
                self.mostrar(ESTADO.novidade)

    def rotulo(self) -> str:
        if self.do_app and self.da_biblioteca:
            return 'Verificar atualizações do app e da biblioteca'
        return 'Verificar atualizações da biblioteca' if self.da_biblioteca else 'Verificar atualizações'

    async def verificar(self) -> None:
        self.botao.disable()
        try:
            if self.do_app:
                await self.verificar_o_app()
            if self.da_biblioteca:
                await self.verificar_a_biblioteca()
        finally:
            self.botao.enable()

    async def verificar_a_biblioteca(self) -> None:
        self.situacao_biblioteca.set_text('Procurando a versão nova da biblioteca…')
        self.area_biblioteca.clear()
        try:
            pacote = await run.io_bound(sobre.biblioteca_nova, resolver_home())
        except Exception as erro:  # noqa: BLE001
            self.situacao_biblioteca.set_text('')
            with self.area_biblioteca:
                mostrar_erro(erro)
            return
        if pacote is None:
            self.situacao_biblioteca.set_text('A biblioteca já está na versão mais nova.')
            return
        versao_nova = pacote.manifesto.versao
        self.situacao_biblioteca.set_text(f'Biblioteca: versão {versao_nova} disponível.')
        with self.area_biblioteca:
            ui.button(
                'Atualizar a biblioteca', icon='download', on_click=lambda: self.confirmar_biblioteca(pacote)
            ).mark('instalar-biblioteca')

    def confirmar_biblioteca(self, pacote) -> None:  # noqa: ANN001
        versao_nova = pacote.manifesto.versao
        with self.area_biblioteca:
            dialogo = Dialogo(f'Atualizar a biblioteca para a {versao_nova}?')
        with dialogo.corpo:
            ui.label(
                f'São cerca de {pacote.artefato.tamanho // 1_000_000} MB do GitHub. O app confere o arquivo antes '
                'de usar; se estiver corrompido, avisa e não instala. Antes de usar a versão nova, o app guarda uma cópia da biblioteca; se ela não '
                'abrir, o app volta à anterior. Seus livros continuam lá.'
            )
        with dialogo.acoes:
            ui.button('Cancelar', on_click=dialogo.close).props('flat')

            async def seguir() -> None:
                dialogo.close()
                await self.atualizar_biblioteca(versao_nova)

            ui.button('Atualizar', on_click=seguir).mark('confirmar-biblioteca')
        dialogo.open()

    async def atualizar_biblioteca(self, versao_nova: str) -> None:
        self.area_biblioteca.clear()
        with self.area_biblioteca:
            ui.label('Baixando…')
            ui.linear_progress(show_value=False).bind_value_from(self, 'fracao').mark('progresso-biblioteca')
        try:
            await run.io_bound(
                sobre.atualizar_biblioteca,
                resolver_home(),
                lambda _texto, fracao: setattr(self, 'fracao', fracao),
            )
        except Exception as erro:  # noqa: BLE001
            self.area_biblioteca.clear()
            with self.area_biblioteca:
                mostrar_erro(erro)
            return
        self.area_biblioteca.clear()
        self.situacao_biblioteca.set_text(
            f'Biblioteca atualizada para a {versao_nova}; seus livros continuam lá.'
        )

    async def verificar_o_app(self) -> None:
        self.situacao.set_text('Consultando o GitHub…')
        try:
            novidade = await run.io_bound(atualizacao.verificar, self.canal)
        except Exception as erro:  # noqa: BLE001
            self.situacao.set_text('')
            mostrar_erro(erro)
            return
        ESTADO.novidade = novidade
        if novidade is None:
            self.area.clear()
            self.situacao.set_text(
                f'Você já tem a versão mais nova do canal {self.canal.value} ({versao()}).'
            )
            return
        self.mostrar(novidade)

    def mostrar(self, novidade: atualizacao.Novidade) -> None:
        self.situacao.set_text(f'Versão {novidade.versao} disponível ({novidade.canal.value}).')
        self.area.clear()
        with self.area:
            ui.link('O que mudou', novidade.notas, new_tab=True).mark('notas-atualizacao')
            ui.button('Baixar e instalar', icon='download', on_click=lambda: self.confirmar(novidade)).mark(
                'instalar-atualizacao'
            )

    def confirmar(self, novidade: atualizacao.Novidade) -> None:
        megas = novidade.artefato.tamanho // 1_000_000
        with self.area:
            dialogo = Dialogo(f'Baixar e instalar a {novidade.versao}?')
        with dialogo.corpo:
            ui.label(
                f'São {megas} MB do GitHub. A atualização é segura: se o arquivo estiver corrompido, o app '
                'avisa e não instala. Os seus projetos e análises não mudam.'
            )
        with dialogo.acoes:
            ui.button('Cancelar', on_click=dialogo.close).props('flat')

            async def seguir() -> None:
                dialogo.close()
                await self.instalar(novidade)

            ui.button('Baixar e instalar', on_click=seguir).mark('confirmar-atualizacao')
        dialogo.open()

    def progredir(self, baixado: int, total: int) -> None:
        self.fracao = baixado / total if total else 0.0

    async def instalar(self, novidade: atualizacao.Novidade) -> None:
        self.area.clear()
        with self.area:
            ui.label('Baixando…')
            ui.linear_progress(show_value=False).bind_value_from(self, 'fracao').mark('progresso-atualizacao')
        try:
            instalacao = await run.io_bound(atualizacao.instalar, novidade, progresso=self.progredir)
        except Exception as erro:  # noqa: BLE001
            self.area.clear()
            mostrar_erro(erro)
            return
        self.area.clear()
        if instalacao.setup_em_andamento:
            self.situacao.set_text('O instalador continua sozinho e reabre o app no fim. O app fecha agora.')
            with self.area:
                ui.timer(SEGUNDOS_PARA_FECHAR, app.shutdown, once=True)
            return
        self.reabrir(instalacao)

    def reabrir(self, instalacao: atualizacao.Instalacao) -> None:
        """O diálogo nasce na área da seção: o de confirmação, de onde veio o clique, já fechou."""
        self.situacao.set_text(f'Atualizado para {instalacao.versao}.')
        with self.area:
            dialogo = Dialogo(f'Atualizado para {instalacao.versao}. Reabrir agora?')
        with dialogo.acoes:
            ui.button('Depois', on_click=dialogo.close).props('flat')

            def agora() -> None:
                atualizacao.reabrir(instalacao)
                app.shutdown()

            ui.button('Reabrir agora', on_click=agora).mark('reabrir-agora')
        dialogo.open()
