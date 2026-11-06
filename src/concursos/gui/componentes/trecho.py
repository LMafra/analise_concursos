import html

from nicegui import ui

from concursos.aplicacao.estudo import TrechoEncontrado
from concursos.aplicacao.resultados import abrir_no_navegador
from concursos.gui import tema
from concursos.livros.indice import FIM_DESTAQUE, INICIO_DESTAQUE


def com_destaque(texto: str) -> str:
    """O trecho escapado, com as palavras encontradas em negrito."""
    seguro = html.escape(texto)
    return seguro.replace(INICIO_DESTAQUE, '<strong>').replace(FIM_DESTAQUE, '</strong>')


def onde_esta(trecho: TrechoEncontrado) -> str:
    if trecho.de_livro:
        return f'{trecho.nome}, p. {trecho.pagina}'
    return f'{trecho.nome} — {trecho.secao}' if trecho.secao else trecho.nome


def trecho(achado: TrechoEncontrado) -> ui.card:
    """Um trecho para conferir: de onde veio (arquivo e página) em cima, o texto e o botão de abrir."""
    with ui.card().classes('w-full ca-borda').style(f'{tema.gap("xs")}; box-shadow: none') as cartao:
        with ui.row().classes('w-full items-center justify-between no-wrap').style(tema.gap('sm')):
            with ui.row().classes('items-center no-wrap').style(tema.gap('xs')):
                ui.icon('menu_book' if achado.de_livro else 'insights', size='xs').props('aria-hidden=true')
                ui.label(onde_esta(achado)).classes('font-bold').mark('trecho-origem')
            ui.button(
                'Abrir arquivo', icon='open_in_new', on_click=lambda: abrir_no_navegador(achado.caminho)
            ).props('flat dense')
        ui.html(f'“{com_destaque(achado.texto)}”', sanitize=False).classes('text-sm')
    return cartao
