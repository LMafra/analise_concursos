import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import TimeoutError as TempoEsgotado

from nicegui import ui

ESPERA_MAXIMA = 30 * 60


class InteracaoCanceladaError(Exception):
    """O usuário fechou a pergunta sem responder."""


class InteracaoGui:
    """O protocolo `Interacao` em diálogos.

    Só a thread de trabalho (`run.io_bound`) chama os métodos: cada pergunta abre o diálogo no loop da
    interface e a thread espera a resposta. Chamar do próprio loop travaria a interface.
    """

    def __init__(self, recipiente: ui.element, mostrar: Callable[[str], None]) -> None:
        self._recipiente = recipiente
        self._mostrar = mostrar
        self._loop = asyncio.get_running_loop()

    def escolher(self, pergunta: str, opcoes: list[str], sugestao: str | None = None) -> str:
        resposta = self._no_loop(lambda: self._escolha(pergunta, opcoes, sugestao))
        if resposta is None:
            raise InteracaoCanceladaError(pergunta)
        return resposta

    def perguntar(self, pergunta: str, sugestao: str | None = None) -> str | None:
        resposta = self._no_loop(lambda: self._texto(pergunta, sugestao))
        if resposta is None:
            raise InteracaoCanceladaError(pergunta)
        return resposta.strip() or sugestao

    def confirmar(self, pergunta: str, padrao: bool = False) -> bool:
        return self._no_loop(lambda: self._sim_ou_nao(pergunta, padrao)) is True

    def mostrar(self, texto: str) -> None:
        self._mostrar(texto)

    def _no_loop(self, abrir: Callable[[], Awaitable]):
        try:
            rodando = asyncio.get_running_loop()
        except RuntimeError:
            rodando = None
        if rodando is self._loop:
            raise RuntimeError('InteracaoGui só pode ser chamada da thread de trabalho')
        futuro = asyncio.run_coroutine_threadsafe(abrir(), self._loop)
        try:
            return futuro.result(timeout=ESPERA_MAXIMA)
        except TempoEsgotado:
            futuro.cancel()
            raise InteracaoCanceladaError('a pergunta ficou sem resposta') from None

    async def _dialogo(self, pergunta: str, corpo: Callable[[ui.dialog], None]):
        with (
            self._recipiente,
            ui.dialog() as dialogo,
            ui.card().classes('min-w-96 max-w-2xl').mark('pergunta'),
        ):
            ui.label(pergunta).classes('font-bold whitespace-pre-line')
            corpo(dialogo)
        try:
            return await dialogo
        finally:
            dialogo.delete()

    async def _escolha(self, pergunta: str, opcoes: list[str], sugestao: str | None) -> str | None:
        def corpo(dialogo: ui.dialog) -> None:
            escolha = ui.radio(opcoes, value=sugestao if sugestao in opcoes else None).mark('opcoes')
            escolha.props(f'aria-label="{pergunta}"')
            with ui.row():
                ui.button(
                    'OK', on_click=lambda: escolha.value is not None and dialogo.submit(escolha.value)
                ).mark('ok')
                ui.button('Cancelar', on_click=lambda: dialogo.submit(None)).props('flat').mark('cancelar')

        return await self._dialogo(pergunta, corpo)

    async def _texto(self, pergunta: str, sugestao: str | None) -> str | None:
        def corpo(dialogo: ui.dialog) -> None:
            campo = ui.input(value=sugestao or '').classes('w-full').mark('resposta')
            campo.props(f'aria-label="{pergunta}"')
            campo.on('keydown.enter', lambda: dialogo.submit(campo.value))
            with ui.row():
                ui.button('OK', on_click=lambda: dialogo.submit(campo.value)).mark('ok')
                ui.button('Cancelar', on_click=lambda: dialogo.submit(None)).props('flat').mark('cancelar')

        return await self._dialogo(pergunta, corpo)

    async def _sim_ou_nao(self, pergunta: str, padrao: bool) -> bool | None:
        def corpo(dialogo: ui.dialog) -> None:
            with ui.row():
                sim = ui.button('Sim', on_click=lambda: dialogo.submit(True)).mark('sim')
                nao = ui.button('Não', on_click=lambda: dialogo.submit(False)).mark('nao')
                (nao if padrao else sim).props('flat')

        return await self._dialogo(pergunta, corpo)
