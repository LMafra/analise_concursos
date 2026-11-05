from pathlib import Path

from nicegui import app, ui

from concursos.gui.textos import rotulo


class SeletorDePasta(ui.dialog):
    """Navega pelas pastas do lado do servidor, quando não há a janela nativa (Linux, modo navegador)."""

    def __init__(self, inicial: Path) -> None:
        super().__init__()
        self.atual = inicial if inicial.is_dir() else Path.home()
        with self, ui.card().classes('w-[40rem] max-w-full'):
            ui.label('Escolha a pasta do projeto').classes('text-lg font-bold')
            self.caminho = rotulo(
                ui.input('Pasta', value=str(self.atual)).classes('w-full'), 'caminho da pasta'
            )
            self.caminho.on('keydown.enter', lambda: self._ir(Path(self.caminho.value)))
            self.lista = ui.list().props('bordered separator dense').classes('w-full max-h-80 overflow-auto')
            with ui.row().classes('w-full justify-end'):
                ui.button('Cancelar', on_click=lambda: self.submit(None)).props('flat')
                ui.button('Usar esta pasta', on_click=self._usar).mark('usar-pasta')
        self._mostrar()

    def _mostrar(self) -> None:
        self.caminho.value = str(self.atual)
        self.lista.clear()
        with self.lista:
            if self.atual.parent != self.atual:
                ui.item('.. (pasta de cima)', on_click=lambda: self._ir(self.atual.parent))
            try:
                pastas = sorted(p for p in self.atual.iterdir() if p.is_dir() and not p.name.startswith('.'))
            except OSError:
                pastas = []
            for pasta in pastas:
                ui.item(pasta.name, on_click=lambda p=pasta: self._ir(p))

    def _ir(self, pasta: Path) -> None:
        pasta = pasta.expanduser()
        if pasta.is_dir():
            self.atual = pasta
            self._mostrar()
        else:
            ui.notify(f'{pasta} não é uma pasta', type='warning')

    def _usar(self) -> None:
        self.submit(Path(self.caminho.value).expanduser())


async def escolher_pasta(inicial: Path) -> Path | None:
    """Diálogo nativo do sistema na janela; no navegador, o seletor do servidor."""
    janela = app.native.main_window
    if janela is not None:
        import webview

        escolhidas = await janela.create_file_dialog(webview.FileDialog.FOLDER, directory=str(inicial))
        return Path(escolhidas[0]) if escolhidas else None
    return await SeletorDePasta(inicial)
