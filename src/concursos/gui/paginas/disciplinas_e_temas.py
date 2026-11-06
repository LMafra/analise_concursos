from dataclasses import replace

from nicegui import ui

from concursos.aplicacao import conferencia
from concursos.aplicacao.conferencia import GrupoDisciplinas
from concursos.gui import tema
from concursos.gui.componentes.cartao import cartao
from concursos.gui.componentes.dialogo import Dialogo
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.reanalise import Reanalise
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.modelo import Bloco

BLOCOS = {Bloco.GERAL.value: 'Conhecimentos gerais', Bloco.ESPECIFICO.value: 'Conhecimentos específicos'}
EXPLICACAO_TAXONOMIA = (
    'Cada concurso escreve o nome da disciplina de um jeito. Junte os nomes que são a mesma disciplina, '
    'para comparar a sua evolução entre os concursos.'
)


def pagina(aba: str | None = None) -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full max-w-4xl').style(tema.gap('md')):
        with ui.row().classes('items-center').style(tema.gap('sm')):
            ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/configuracoes')).props(
                'flat round aria-label="voltar às configurações"'
            )
            ui.label('Disciplinas e temas').classes('text-2xl font-bold')
        reanalise = Reanalise()
        with ui.tabs().classes('w-full') as abas:
            aba_disciplinas = ui.tab('Disciplinas', icon='category').mark('aba-disciplinas')
        with ui.tab_panels(abas, value=aba_disciplinas).classes('w-full'), ui.tab_panel(aba_disciplinas):
            Disciplinas(reanalise)


class Disciplinas:
    def __init__(self, reanalise: Reanalise) -> None:
        self.reanalise = reanalise
        self.marcadas: set[str] = set()
        with ui.column().classes('w-full').style(tema.gap('sm')) as self.raiz:
            ui.label(EXPLICACAO_TAXONOMIA).classes('ca-texto-suave')
            self.conteudo = ui.column().classes('w-full').style(tema.gap('sm'))
        self.desenhar()

    def desenhar(self) -> None:
        self.conteudo.clear()
        self.marcadas.clear()
        try:
            self.atual = conferencia.taxonomia(ESTADO.contexto())
        except Exception as erro:  # noqa: BLE001
            with self.raiz:
                mostrar_erro(erro)
            return
        with self.conteudo:
            if not self.atual.grupos and not self.atual.soltas:
                estado_vazio(
                    'category',
                    'Nenhuma disciplina ainda',
                    'As disciplinas aparecem depois da primeira análise.',
                    marca='sem-disciplinas',
                )
                return
            for grupo in self.atual.grupos:
                self.grupo(grupo)
            if self.atual.soltas:
                with cartao('Nomes ainda não juntados', icone='call_split'):
                    for nome in self.atual.soltas:
                        ui.checkbox(nome, on_change=lambda e, n=nome: self.marcar(n, e.value)).mark(
                            f'solta-{nome}'
                        )
                    ui.button('Juntar os marcados', icon='merge', on_click=self.pedir_juntar).mark(
                        'juntar-disciplinas'
                    )

    def grupo(self, grupo: GrupoDisciplinas) -> None:
        with cartao():
            with ui.row().classes('items-center w-full').style(tema.gap('sm')):
                ui.label(grupo.canonica).classes('text-lg font-bold flex-grow')
                rotulo(
                    ui.toggle(
                        BLOCOS,
                        value=grupo.bloco.value,
                        on_change=lambda e, g=grupo: self.trocar_bloco(g, Bloco(e.value)),
                    ),
                    f'bloco de {grupo.canonica}',
                ).mark(f'bloco-{grupo.canonica}')
                ui.button(
                    'Separar', icon='call_split', on_click=lambda g=grupo: self.separar(g.canonica)
                ).props('flat dense').mark(f'separar-{grupo.canonica}')
            if grupo.nomes:
                ui.label('Também aparece como: ' + '; '.join(grupo.nomes)).classes('text-sm ca-texto-suave')

    def marcar(self, nome: str, marcado: bool) -> None:
        if marcado:
            self.marcadas.add(nome)
        else:
            self.marcadas.discard(nome)

    def pedir_juntar(self) -> None:
        with self.raiz:
            if not self.marcadas:
                ui.notify('Marque os nomes que são a mesma disciplina.')
                return
            marcadas = sorted(self.marcadas)
            opcoes = list(dict.fromkeys([*marcadas, *(g.canonica for g in self.atual.grupos)]))
            dialogo = Dialogo('Juntar disciplinas', marca='dialogo-juntar')
            with dialogo.corpo:
                ui.label('Nomes: ' + '; '.join(marcadas))
                nome = rotulo(
                    ui.select(
                        opcoes, value=marcadas[0], label='Nome da disciplina', new_value_mode='add-unique'
                    ),
                    'nome da disciplina',
                ).classes('w-full')
                nome.mark('nome-da-disciplina')
                bloco = rotulo(ui.toggle(BLOCOS, value=Bloco.GERAL.value), 'bloco').mark('bloco-novo')
            with dialogo.acoes:
                ui.button('Cancelar', on_click=dialogo.close).props('flat')
                ui.button(
                    'Juntar',
                    icon='merge',
                    on_click=lambda: self.juntar(dialogo, marcadas, nome.value, Bloco(bloco.value)),
                ).mark('confirmar-juntar')
            dialogo.open()

    def juntar(self, dialogo: Dialogo, nomes: list[str], canonica: str, bloco: Bloco) -> None:
        dialogo.close()
        self.gravar(lambda: conferencia.juntar_disciplinas(ESTADO.contexto(), nomes, canonica or '', bloco))

    def trocar_bloco(self, grupo: GrupoDisciplinas, bloco: Bloco) -> None:
        grupos = [replace(g, bloco=bloco) if g.canonica == grupo.canonica else g for g in self.atual.grupos]
        self.gravar(lambda: conferencia.gravar_taxonomia(ESTADO.contexto(), grupos))

    def separar(self, canonica: str) -> None:
        self.gravar(lambda: conferencia.separar_disciplina(ESTADO.contexto(), canonica))

    def gravar(self, acao) -> None:
        with self.raiz:
            try:
                mudou = acao()
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            self.desenhar()
            if mudou:
                ui.notify('Gravado. A análise é refeita com as disciplinas novas.', type='positive')
                ui.timer(0.1, self.reanalise.iniciar, once=True)
