import logging
from dataclasses import replace

from nicegui import run, ui

from concursos.analytics.dicionario_topicos import EntradaTema, SugestaoTermo
from concursos.aplicacao import conferencia, dicionario
from concursos.aplicacao.conferencia import GrupoDisciplinas
from concursos.aplicacao.dicionario import rotulo_do_tema
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.cartao import cartao
from concursos.gui.componentes.dialogo import Dialogo
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.reanalise import Reanalise
from concursos.gui.componentes.situacao import situacao
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.modelo import Bloco

logger = logging.getLogger(__name__)

BLOCOS = {Bloco.GERAL.value: 'Conhecimentos gerais', Bloco.ESPECIFICO.value: 'Conhecimentos específicos'}
EXPLICACAO_TAXONOMIA = (
    'Cada concurso escreve o nome da disciplina de um jeito. Junte os nomes que são a mesma disciplina, '
    'para comparar a sua evolução entre os concursos.'
)
EXPLICACAO_DICIONARIO = (
    'Palavras que ajudam o app a achar o tema do edital de cada questão. Por exemplo, "acento grave" '
    'leva ao tema Crase. Teste o ganho com as questões que você já conferiu antes de confiar nele.'
)
ABA_TEMAS = 'temas'


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
            aba_temas = ui.tab('Dicionário de temas', icon='menu_book').mark('aba-temas')
        inicial = aba_temas if aba == ABA_TEMAS else aba_disciplinas
        with ui.tab_panels(abas, value=inicial).classes('w-full'):
            with ui.tab_panel(aba_disciplinas):
                Disciplinas(reanalise)
            with ui.tab_panel(aba_temas):
                DicionarioDeTemas(reanalise)


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


def _rotulo_da_disciplina(disciplina: str) -> str:
    return disciplina.replace('_', ' ').capitalize()


class DicionarioDeTemas:
    def __init__(self, reanalise: Reanalise) -> None:
        self.reanalise = reanalise
        self.sugeridas: list[SugestaoTermo] | None = None
        self.aceitas = 0
        with ui.column().classes('w-full').style(tema.gap('sm')) as self.raiz:
            ui.label(EXPLICACAO_DICIONARIO).classes('ca-texto-suave')
            self.conteudo = ui.column().classes('w-full').style(tema.gap('sm'))
        self.desenhar()

    def desenhar(self) -> None:
        self.conteudo.clear()
        contexto = ESTADO.contexto()
        try:
            self.situacao = dicionario.situacao(contexto)
            entradas = dicionario.temas(contexto)
        except Exception as erro:  # noqa: BLE001
            with self.conteudo:
                mostrar_erro(erro)
            return
        with self.conteudo:
            self.cabecalho()
            self.sugestoes()
            if entradas:
                with cartao('Termos de cada tema', icone='edit_note'):
                    ui.label(
                        'Separe os termos por vírgula. Deixe vazio para tirar o tema do dicionário.'
                    ).classes('text-sm ca-texto-suave')
                    for entrada in entradas:
                        self.tema(entrada)

    def cabecalho(self) -> None:
        situacao_atual = self.situacao
        with cartao():
            with ui.row().classes('items-center w-full').style(tema.gap('sm')):
                rotulo(
                    ui.switch(
                        'Usar o dicionário',
                        value=situacao_atual.ligado and situacao_atual.existe,
                        on_change=lambda e: self.ligar(e.value),
                    ),
                    'usar o dicionário de temas',
                ).mark('usar-dicionario').set_enabled(situacao_atual.existe)
                ui.button(
                    'Começar com o dicionário inicial', icon='auto_awesome', on_click=self.iniciar
                ).props('flat').mark('iniciar-dicionario')
                ui.button('Testar ganho', icon='science', on_click=self.testar).props('flat').mark(
                    'testar-ganho'
                ).set_enabled(situacao_atual.entradas > 0)
            if not situacao_atual.existe:
                situacao('Ainda sem dicionário: comece com o inicial ou aceite termos sugeridos.', Tom.INFO)
            elif not situacao_atual.ligado:
                situacao(f'Desligado ({situacao_atual.entradas} temas guardados).', Tom.INFO)
            else:
                situacao(f'Ligado, com {situacao_atual.entradas} temas.', Tom.SUCESSO)
            ultimo = situacao_atual.ultimo
            if ultimo is not None:
                ui.label(dicionario.resumo_do_ultimo(ultimo)).mark('ultimo-teste')
                if ultimo.alerta and situacao_atual.ligado:
                    with aviso(
                        'O dicionário piorou a sugestão de tema',
                        'Algumas questões que o app acertava passaram a errar. Desligue o dicionário ou '
                        'revise os termos.',
                        tom=Tom.ALERTA,
                    ).mark('alerta-dicionario'):
                        ui.button(
                            'Desligar o dicionário', icon='toggle_off', on_click=lambda: self.ligar(False)
                        ).props('flat').mark('desligar-dicionario')

    def sugestoes(self) -> None:
        with cartao('Termos sugeridos pelas suas conferências', icone='lightbulb'):
            ui.label('Palavras que se repetem nas questões que você conferiu para um mesmo tema.').classes(
                'text-sm ca-texto-suave'
            )
            if self.sugeridas is None:
                ui.button(
                    'Sugerir termos das minhas revisões', icon='lightbulb', on_click=self.sugerir
                ).props('flat').mark('sugerir-termos')
                return
            if self.aceitas:
                ui.button(
                    f'Refazer a análise com os {self.aceitas} termos aceitos',
                    icon='refresh',
                    on_click=self.refazer,
                ).mark('refazer-analise')
            if not self.sugeridas:
                situacao('Nenhuma sugestão. Confira mais tópicos das questões e tente de novo.', Tom.INFO)
                return
            for sugestao in self.sugeridas:
                with ui.row().classes('items-center w-full no-wrap').style(tema.gap('sm')):
                    ui.label(f'"{sugestao.termo}" → {sugestao.nome_topico} ({sugestao.n} questões)').classes(
                        'flex-grow'
                    )
                    ui.button(
                        'Aceitar', icon='check', on_click=lambda s=sugestao: self.decidir(s, aceitar=True)
                    ).props('flat dense').mark(f'aceitar-{sugestao.chave}')
                    ui.button(
                        'Recusar', icon='close', on_click=lambda s=sugestao: self.decidir(s, aceitar=False)
                    ).props('flat dense').mark(f'recusar-{sugestao.chave}')

    def tema(self, entrada: EntradaTema) -> None:
        chave = f'{entrada.disciplina}/{entrada.topico}'
        titulo = f'{rotulo_do_tema(entrada)} · {_rotulo_da_disciplina(entrada.disciplina)}'
        with ui.expansion(titulo).classes('w-full').mark(f'tema-{chave}'):
            termos = rotulo(ui.input('Termos', value=', '.join(entrada.termos)), f'termos de {titulo}')
            termos.classes('w-full').mark(f'termos-{chave}')
            expressoes = rotulo(
                ui.input('Expressões', value=', '.join(entrada.expressoes)), f'expressões de {titulo}'
            )
            expressoes.classes('w-full').mark(f'expressoes-{chave}')
            ui.button(
                'Salvar',
                icon='save',
                on_click=lambda: self.gravar(
                    lambda: dicionario.gravar_topico(
                        ESTADO.contexto(),
                        entrada.disciplina,
                        entrada.topico,
                        dicionario.termos_do_texto(termos.value or ''),
                        dicionario.termos_do_texto(expressoes.value or ''),
                    )
                ),
            ).props('flat').mark(f'salvar-{chave}')

    def ligar(self, usar: bool) -> None:
        self.gravar(lambda: dicionario.ligar(ESTADO.contexto(), usar) or True)

    def iniciar(self) -> None:
        self.gravar(lambda: dicionario.iniciar(ESTADO.contexto()) >= 0)

    def decidir(self, sugestao: SugestaoTermo, aceitar: bool) -> None:
        acao = dicionario.aceitar if aceitar else dicionario.recusar
        if self.sugeridas is not None:
            self.sugeridas = [s for s in self.sugeridas if s.chave != sugestao.chave]
        self.aceitas += aceitar
        self.gravar(lambda: acao(ESTADO.contexto(), sugestao), reanalisar=False)

    def refazer(self) -> None:
        self.aceitas = 0
        self.desenhar()
        with self.raiz:
            ui.timer(0.1, self.reanalise.iniciar, once=True)

    async def sugerir(self) -> None:
        with self.raiz:
            try:
                self.sugeridas = await run.io_bound(dicionario.sugestoes, ESTADO.contexto())
            except Exception as erro:  # noqa: BLE001
                logger.debug('falha ao sugerir termos pela GUI', exc_info=True)
                mostrar_erro(erro)
                return
            self.desenhar()

    async def testar(self) -> None:
        with self.raiz:
            ui.notify('Testando o dicionário com as questões que você conferiu…')
            try:
                await run.io_bound(dicionario.avaliar, ESTADO.contexto())
            except Exception as erro:  # noqa: BLE001
                logger.debug('falha ao testar o dicionário pela GUI', exc_info=True)
                mostrar_erro(erro)
                return
            self.desenhar()

    def gravar(self, acao, reanalisar: bool = True) -> None:
        with self.raiz:
            try:
                mudou = acao()
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            self.desenhar()
            if mudou and reanalisar:
                ui.notify('Gravado. A análise é refeita com o dicionário.', type='positive')
                ui.timer(0.1, self.reanalise.iniciar, once=True)
