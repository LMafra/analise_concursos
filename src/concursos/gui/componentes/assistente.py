import inspect
from collections.abc import Awaitable, Callable, Collection, Sequence

from nicegui import ui

from concursos.gui import tema
from concursos.gui.componentes.etapas import etapas

AntesDeAvancar = Callable[[int, bool], bool | Awaitable[bool]]


class Assistente:
    """Um passo por vez, com o indicador no topo, Voltar, Continuar e, nos opcionais, Pular.

    `antes_de_avancar(indice, pulou)` roda ao sair de um passo; devolvendo False, o passo fica. O último
    passo não tem Continuar: as ações dele são do conteúdo."""

    def __init__(
        self,
        titulos: Sequence[str],
        *,
        opcionais: Collection[int] = (),
        antes_de_avancar: AntesDeAvancar | None = None,
    ) -> None:
        self.titulos = list(titulos)
        self.opcionais = set(opcionais)
        self.antes_de_avancar = antes_de_avancar
        self.atual = 0
        with ui.column().classes('w-full').style(tema.gap('md')).mark('assistente'):
            self.topo = ui.column().classes('w-full').style(tema.gap('sm'))
            self.passos = [
                ui.column().classes('w-full').style(tema.gap('sm')).mark(f'passo-{indice + 1}')
                for indice in range(len(self.titulos))
            ]
            with ui.row().classes('w-full items-center').style(tema.gap('sm')):
                self.voltar = ui.button('Voltar', icon='arrow_back', on_click=self.anterior).props('flat')
                self.voltar.mark('voltar')
                ui.space()
                self.pular = ui.button('Pular', on_click=lambda: self.avancar(pulou=True)).props('flat')
                self.pular.mark('pular')
                self.continuar = ui.button('Continuar', icon='arrow_forward', on_click=self.avancar)
                self.continuar.mark('continuar')
        self._mostrar()

    def passo(self, indice: int) -> ui.column:
        return self.passos[indice]

    async def avancar(self, pulou: bool = False) -> None:
        if self.antes_de_avancar is not None:
            self.continuar.disable()
            try:
                seguir = self.antes_de_avancar(self.atual, pulou)
                if inspect.isawaitable(seguir):
                    seguir = await seguir
            finally:
                self.continuar.enable()
            if not seguir:
                return
        self.ir_para(self.atual + 1)

    def anterior(self) -> None:
        self.ir_para(self.atual - 1)

    def ir_para(self, indice: int) -> None:
        self.atual = max(0, min(indice, len(self.titulos) - 1))
        self._mostrar()

    def _mostrar(self) -> None:
        self.topo.clear()
        with self.topo:
            ui.label(f'Passo {self.atual + 1} de {len(self.titulos)}: {self.titulos[self.atual]}').classes(
                'text-lg font-bold'
            ).mark('titulo-passo')
            etapas(self.titulos, self.atual)
        for indice, coluna in enumerate(self.passos):
            coluna.set_visibility(indice == self.atual)
        self.voltar.set_visibility(self.atual > 0)
        self.pular.set_visibility(self.atual in self.opcionais)
        self.continuar.set_visibility(self.atual < len(self.titulos) - 1)
