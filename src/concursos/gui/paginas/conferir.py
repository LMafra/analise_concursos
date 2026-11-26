from nicegui import ui

from concursos.aplicacao import conferencia
from concursos.aplicacao.conferencia import CampoAConfirmar, LinhaTopico, OpcaoTopico
from concursos.datas import data_br
from concursos.gui import tema
from concursos.gui.componentes import toasts
from concursos.gui.componentes.campo import cabecalho_da_pagina
from concursos.gui.componentes.campo import campo as campo_com_rotulo
from concursos.gui.componentes.estado_vazio import estado_vazio
from concursos.gui.componentes.navegacao import voltar
from concursos.gui.componentes.reanalise import Reanalise
from concursos.gui.componentes.situacao import situacao
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro
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
        voltar('Voltar para Minhas Provas', '/')
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
        pendentes = sum(1 for linha in linhas if linha.pendente)

        def selo() -> None:
            if pendentes:
                situacao(
                    f'{pendentes} questões aguardando conferência',
                    Tom.ALERTA,
                    icone='priority_high',
                )
            elif linhas:
                situacao('Tudo conferido', Tom.SUCESSO, icone='check')

        cabecalho_da_pagina(
            f'Conferir — {concurso}',
            'Confirme os tópicos sugeridos pela leitura automática e complete o que o edital '
            'não trouxe fechado.',
            ao_lado=selo,
        )
        reanalise = Reanalise()
        if campos:
            DadosDoEdital(concurso, campos, reanalise)
        TopicosDasQuestoes(concurso, linhas, opcoes, reanalise)


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
            with ui.element('div').classes('ca-barra-salvar'):
                with ui.column().style(tema.gap('xs')):
                    ui.label(f'Alterações em {self.concurso}').classes('font-bold')
                    ui.label(
                        'Ao salvar, atualizamos seu diagnóstico e voltamos para Minhas Provas.'
                    ).classes('text-sm ca-texto-suave')
                with ui.row().classes('items-center').style(tema.gap('sm')):
                    ui.button(
                        'Cancelar',
                        on_click=lambda: toasts.sujo_ao_sair(self._topicos_sujos, '/'),
                    ).props('outline no-caps').classes('ca-alvo')
                    ui.button('Salvar alterações', on_click=self.salvar).props('no-caps').classes(
                        'ca-alvo'
                    ).mark('salvar-topicos')

    def _topicos_sujos(self) -> bool:
        return any(self.escolhas[chave].value != self.iniciais[chave] for chave in self.escolhas)

    def linha(self, linha: LinhaTopico) -> None:
        opcoes = {NENHUM: ROTULO_NENHUM, **{str(i): o.rotulo for i, o in enumerate(self.opcoes)}}
        inicial = valor_inicial(linha, self.opcoes)
        with ui.card().classes('w-full').style(tema.gap('sm')):
            with ui.row().classes('w-full items-center justify-between flex-wrap').style(tema.gap('sm')):
                ui.label(f'Questão {linha.questao}').classes('font-bold')
                situacao(
                    'Tópico sugerido' if linha.pendente else 'Conferido',
                    Tom.ALERTA if linha.pendente else Tom.SUCESSO,
                    icone='priority_high' if linha.pendente else 'check',
                )
            ui.label(abreviar(linha.enunciado, TAMANHO_ENUNCIADO)).classes('text-sm ca-texto-suave')
            sugerido = 'nenhum' if linha.topico_sugerido == NAO_MAPEADO else linha.topico_sugerido
            ui.label(f'O app sugeriu: {abreviar(sugerido, TAMANHO_ENUNCIADO)}').classes(
                'text-sm ca-texto-suave'
            )
            seletor = campo_com_rotulo(
                'Tópico da questão (editável)',
                ui.select(opcoes, value=inicial, with_input=True, clearable=True),
                marca=f'topico-{linha.prova}-{linha.questao}',
            )
        self.escolhas[linha.chave] = seletor
        self.iniciais[linha.chave] = inicial

    def salvar(self) -> None:
        from concursos.aplicacao import lixeira

        mudadas = {
            chave: None if seletor.value == NENHUM else self.opcoes[int(seletor.value)]
            for chave, seletor in self.escolhas.items()
            if seletor.value != self.iniciais[chave] and seletor.value is not None
        }
        with self.raiz:
            if not mudadas:
                toasts.sucesso('Nada mudou.')
                return
            revisao = ESTADO.contexto().provas / self.concurso / 'revisao' / 'questoes_revisado.csv'
            anterior = lixeira.snapshot_arquivo(revisao)
            try:
                conferencia.gravar_topicos(ESTADO.contexto(), self.concurso, mudadas)
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            self.iniciais.update({chave: self.escolhas[chave].value for chave in mudadas})

            def desfazer() -> None:
                lixeira.restaurar_arquivo(revisao, anterior)
                self.reanalise.iniciar(self.concurso)

            toasts.com_desfazer(f'{SALVO} Desfazer?', desfazer)
            ui.timer(0.1, lambda: self.reanalise.iniciar(self.concurso), once=True)


class DadosDoEdital:
    def __init__(self, concurso: str, campos: list[CampoAConfirmar], reanalise: Reanalise) -> None:
        self.concurso = concurso
        self.reanalise = reanalise
        self.entradas: dict[str, ui.input] = {}
        self.iniciais: dict[str, str] = {}
        with ui.column().classes('w-full').style(tema.gap('sm')) as self.raiz:
            if not campos:
                estado_vazio(
                    'task_alt',
                    'O edital trouxe tudo',
                    'Nenhum dado do edital ficou para você confirmar.',
                    marca='sem-campos',
                )
                return
            with ui.card().classes('w-full ca-metrica ca-tom-alerta').style(tema.gap('md')):
                ui.label('O edital deixou isto em aberto').classes('text-lg font-bold')
                ui.label(
                    'Esses campos ajudam a medir sua distância exata até a aprovação.'
                ).classes('text-sm ca-texto-suave')
                with ui.element('div').classes('ca-grade-form'):
                    for item in campos:
                        self.campo(item)
            with ui.element('div').classes('ca-barra-salvar'):
                with ui.column().style(tema.gap('xs')):
                    ui.label(f'Alterações em {self.concurso}').classes('font-bold')
                    ui.label(
                        'Ao salvar, atualizamos seu diagnóstico e voltamos para Minhas Provas.'
                    ).classes('text-sm ca-texto-suave')
                with ui.row().classes('items-center').style(tema.gap('sm')):
                    ui.button(
                        'Cancelar',
                        on_click=lambda: toasts.sujo_ao_sair(self._campos_sujos, '/'),
                    ).props('outline no-caps')
                    ui.button('Salvar alterações', on_click=self.salvar).props('no-caps').classes(
                        'ca-alvo'
                    ).mark('salvar-campos')

    def _campos_sujos(self) -> bool:
        return any(
            (entrada.value or '') != self.iniciais.get(chave, '') for chave, entrada in self.entradas.items()
        )

    def campo(self, item: CampoAConfirmar) -> None:
        if item.tipo is TipoCampo.DATA:
            inicial = data_br(item.valor)
            entrada = ui.input(value=inicial, placeholder='DD/MM/AAAA').props('mask="##/##/####"')
            ajuda = ui.label('').classes('text-sm').mark(f'erro-{item.campo}')

            def validar_data(e=None, entrada=entrada, ajuda=ajuda) -> None:  # noqa: ANN001
                texto = (entrada.value or '').strip()
                if not texto:
                    ajuda.set_text('')
                    return
                if len(texto) != 10 or texto[2] != '/' or texto[5] != '/':
                    ajuda.set_text('Use o formato DD/MM/AAAA.')
                    return
                ajuda.set_text('')

            entrada.on('blur', validar_data)
        else:
            inicial = item.valor or ''
            entrada = ui.input(value=inicial).props('inputmode=decimal')
        campo_com_rotulo(item.rotulo, entrada, marca=f'campo-{item.campo}')
        ui.label(item.explicacao).classes('text-sm ca-texto-suave')
        self.entradas[item.campo] = entrada
        self.iniciais[item.campo] = inicial

    def salvar(self) -> None:
        valores = {campo: entrada.value or '' for campo, entrada in self.entradas.items()}
        with self.raiz:
            try:
                mudou = conferencia.gravar_campos(ESTADO.contexto(), self.concurso, valores)
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            if not mudou:
                toasts.sucesso('Nada mudou.')
                return
            toasts.sucesso(SALVO)
            ui.timer(0.1, lambda: self.reanalise.iniciar(self.concurso), once=True)
