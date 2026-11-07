from nicegui import ui

from concursos.aplicacao import conferencia
from concursos.aplicacao.conferencia import CampoAConfirmar, LinhaTopico, OpcaoTopico
from concursos.datas import data_br
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.cartao import cartao
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.reanalise import Reanalise
from concursos.gui.componentes.situacao import situacao
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.modelo import TipoCampo
from concursos.texto import abreviar
from concursos.topicos import NAO_MAPEADO

NENHUM = 'nenhum'
ROTULO_NENHUM = 'Nenhum (a questão não está no edital)'
TAMANHO_ENUNCIADO = 160
SALVO = 'Gravado. A análise é refeita só para este concurso.'


def pagina(concurso: str | None = None, aba: str | None = None) -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full max-w-5xl').style(tema.gap('md')):
        with ui.row().classes('items-center').style(tema.gap('sm')):
            ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/')).props(
                'flat round aria-label="voltar aos concursos"'
            )
            ui.label(f'Conferir {concurso or ""}'.strip()).classes('text-2xl font-bold')
        if not concurso:
            estado_vazio(
                'fact_check',
                'Escolha um concurso',
                'Abra a conferência pelo botão "Conferir" do concurso.',
                acao='Ver concursos',
                ao_clicar=lambda: ui.navigate.to('/'),
                marca='conferir-sem-concurso',
            )
            return
        try:
            linhas = conferencia.topicos_para_conferir(ESTADO.contexto(), concurso)
            opcoes = conferencia.opcoes_de_topico(ESTADO.contexto(), concurso)
            campos = conferencia.campos_a_confirmar(ESTADO.contexto(), concurso)
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        reanalise = Reanalise()
        with ui.tabs().classes('w-full') as abas:
            aba_topicos = ui.tab('Tópicos das questões', icon='topic').mark('aba-topicos')
            aba_edital = ui.tab('Dados do edital', icon='description').mark('aba-edital')
        inicial = aba_edital if aba == 'edital' or (campos and not linhas) else aba_topicos
        with ui.tab_panels(abas, value=inicial).classes('w-full'):
            with ui.tab_panel(aba_topicos):
                TopicosDasQuestoes(concurso, linhas, opcoes, reanalise)
            with ui.tab_panel(aba_edital):
                DadosDoEdital(concurso, campos, reanalise)


def valor_inicial(linha: LinhaTopico, opcoes: list[OpcaoTopico]) -> str | None:
    if linha.topico == NAO_MAPEADO:
        return NENHUM
    for indice, opcao in enumerate(opcoes):
        if linha.topico == opcao.topico and (not linha.disciplina or linha.disciplina == opcao.disciplina):
            return str(indice)
    return None


class TopicosDasQuestoes:
    """Uma linha por questão, as pendentes primeiro; só as linhas mexidas são gravadas."""

    def __init__(
        self, concurso: str, linhas: list[LinhaTopico], opcoes: list[OpcaoTopico], reanalise: Reanalise
    ) -> None:
        self.concurso = concurso
        self.opcoes = opcoes
        self.reanalise = reanalise
        self.escolhas: dict[tuple[int, str], ui.select] = {}
        self.iniciais: dict[tuple[int, str], str | None] = {}
        with ui.column().classes('w-full').style(tema.gap('sm')) as self.raiz:
            if not linhas:
                estado_vazio(
                    'topic',
                    'Nada para conferir aqui',
                    'Os tópicos aparecem depois que o concurso é analisado com o edital.',
                    marca='sem-topicos',
                )
                return
            pendentes = [linha for linha in linhas if linha.pendente]
            confiaveis = [linha for linha in linhas if not linha.pendente]
            ui.label(
                'Escolha o tópico do edital de cada questão. Deixe em branco para manter o que o app sugeriu.'
            ).classes('ca-texto-suave')
            if pendentes:
                situacao(f'{len(pendentes)} questões sem um tópico confiável', Tom.ALERTA)
                for linha in pendentes:
                    self.linha(linha)
            else:
                situacao('Todas as questões têm um tópico confiável', Tom.SUCESSO)
            if confiaveis:
                with ui.expansion(f'Questões já com tópico ({len(confiaveis)})', icon='done_all').classes(
                    'w-full'
                ):
                    for linha in confiaveis:
                        self.linha(linha)
            ui.button('Salvar e refazer a análise', icon='save', on_click=self.salvar).mark('salvar-topicos')

    def linha(self, linha: LinhaTopico) -> None:
        opcoes = {NENHUM: ROTULO_NENHUM, **{str(i): o.rotulo for i, o in enumerate(self.opcoes)}}
        inicial = valor_inicial(linha, self.opcoes)
        with cartao():
            ui.label(f'Questão {linha.questao} ({linha.prova})').classes('font-bold')
            ui.label(abreviar(linha.enunciado, TAMANHO_ENUNCIADO)).classes('text-sm')
            sugerido = 'nenhum' if linha.topico_sugerido == NAO_MAPEADO else linha.topico_sugerido
            ui.label(f'O app sugeriu: {abreviar(sugerido, TAMANHO_ENUNCIADO)}').classes(
                'text-sm ca-texto-suave'
            )
            seletor = rotulo(
                ui.select(opcoes, value=inicial, label='Tópico do edital', with_input=True, clearable=True),
                f'tópico da questão {linha.questao}',
            ).classes('w-full')
            seletor.mark(f'topico-{linha.prova}-{linha.questao}')
        self.escolhas[linha.chave] = seletor
        self.iniciais[linha.chave] = inicial

    def salvar(self) -> None:
        mudadas = {
            chave: None if seletor.value == NENHUM else self.opcoes[int(seletor.value)]
            for chave, seletor in self.escolhas.items()
            if seletor.value != self.iniciais[chave] and seletor.value is not None
        }
        with self.raiz:
            if not mudadas:
                ui.notify('Nada mudou.')
                return
            try:
                conferencia.gravar_topicos(ESTADO.contexto(), self.concurso, mudadas)
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            self.iniciais.update({chave: self.escolhas[chave].value for chave in mudadas})
            ui.notify(SALVO, type='positive')
            ui.timer(0.1, lambda: self.reanalise.iniciar(self.concurso), once=True)


class DadosDoEdital:
    def __init__(self, concurso: str, campos: list[CampoAConfirmar], reanalise: Reanalise) -> None:
        self.concurso = concurso
        self.reanalise = reanalise
        self.entradas: dict[str, ui.input] = {}
        with ui.column().classes('w-full').style(tema.gap('sm')) as self.raiz:
            if not campos:
                estado_vazio(
                    'task_alt',
                    'O edital trouxe tudo',
                    'Nenhum dado do edital ficou para você confirmar.',
                    marca='sem-campos',
                )
                return
            aviso(
                'O app não achou estes dados no edital',
                'Preencha os que você souber; os vazios ficam com o valor padrão da banca.',
                tom=Tom.ALERTA,
            )
            for campo in campos:
                self.campo(campo)
            ui.button('Salvar e refazer a análise', icon='save', on_click=self.salvar).mark('salvar-campos')

    def campo(self, campo: CampoAConfirmar) -> None:
        with cartao():
            if campo.tipo is TipoCampo.DATA:
                entrada = ui.input(campo.rotulo, value=data_br(campo.valor), placeholder='DD/MM/AAAA').props(
                    'mask="##/##/####"'
                )
            else:
                entrada = ui.input(campo.rotulo, value=campo.valor).props('inputmode=decimal')
            entrada.classes('w-full').mark(f'campo-{campo.campo}')
            ui.label(campo.explicacao).classes('text-sm ca-texto-suave')
        self.entradas[campo.campo] = entrada

    def salvar(self) -> None:
        valores = {campo: entrada.value or '' for campo, entrada in self.entradas.items()}
        with self.raiz:
            try:
                mudou = conferencia.gravar_campos(ESTADO.contexto(), self.concurso, valores)
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            if not mudou:
                ui.notify('Nada mudou.')
                return
            ui.notify(SALVO, type='positive')
            ui.timer(0.1, lambda: self.reanalise.iniciar(self.concurso), once=True)
