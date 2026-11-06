import logging
from pathlib import Path, PureWindowsPath

from nicegui import events, run, ui

from concursos.aplicacao import atualizador as atualizacao
from concursos.aplicacao import dicionario, ia, inicio
from concursos.aplicacao.cadastro import nova_pasta_de_envio
from concursos.aplicacao.preferencias import (
    PreferenciasAnalise,
    gravar_analise,
    gravar_tema_da_gui,
    ler_analise,
    tema_da_gui,
)
from concursos.calibracao import QUESTOES_CALIBRACAO
from concursos.config.contexto import resolver_home
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.cartao import cartao
from concursos.gui.componentes.situacao import situacao
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.modelo import CanalAtualizacao, TemaGui
from concursos.status import listar_concursos

logger = logging.getLogger('concursos')

SEM_ALVO = '(nenhum)'
EXPLICACAO_CONFIANCA = 'Abaixo deste valor, a marcação lida na folha fica marcada para você conferir.'
EXPLICACAO_TOPICO = 'Tópicos com acerto abaixo deste valor aparecem como fracos no relatório.'
EXPLICACAO_ALVO = (
    'O concurso que você vai prestar: a meta, a simulação, o desempate e a prática no TEC usam o edital dele.'
)


def pagina() -> None:
    if not exigir_projeto():
        return
    with ui.column().classes('w-full max-w-2xl').style(tema.gap('lg')):
        ui.label('Configurações').classes('text-2xl font-bold')
        try:
            secao_da_analise()
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
        secao_das_disciplinas()
        secao_do_projeto()
        secao_da_aparencia()
        SecaoDaIa()
        SecaoDaCalibracao()
        secao_avancada()


def controle_de_limiar(titulo: str, valor: float, explicacao: str, marca: str) -> ui.slider:
    ui.label(titulo).classes('font-bold')
    with ui.row().classes('items-center w-full no-wrap').style(tema.gap('md')):
        controle = rotulo(ui.slider(min=0.05, max=0.95, step=0.05, value=valor), titulo).classes('flex-grow')
        controle.mark(marca)
        ui.label().bind_text_from(controle, 'value', lambda v: f'{v:.2f}'.replace('.', ',')).classes(
            'w-12 font-mono'
        )
    ui.label(explicacao).classes('text-sm ca-texto-suave')
    return controle


def secao_da_analise() -> None:
    contexto = ESTADO.contexto()
    atuais = ler_analise(contexto)
    nomes = [p.name for p in listar_concursos(contexto.provas)] if contexto.provas.is_dir() else []
    with cartao('Análise', icone='analytics'):
        confianca = controle_de_limiar(
            'Limiar de confiança da leitura',
            atuais.limiar_confianca,
            EXPLICACAO_CONFIANCA,
            'limiar-confianca',
        )
        topico = controle_de_limiar(
            'Limiar de tópico fraco', atuais.limiar_topico_baixo, EXPLICACAO_TOPICO, 'limiar-topico'
        )
        opcoes = [SEM_ALVO, *nomes]
        alvo = (
            rotulo(
                ui.select(
                    opcoes,
                    label='Concurso-alvo',
                    value=atuais.concurso_alvo if atuais.concurso_alvo in nomes else SEM_ALVO,
                ),
                'concurso-alvo',
            )
            .classes('w-full')
            .mark('concurso-alvo')
        )
        ui.label(EXPLICACAO_ALVO).classes('text-sm ca-texto-suave')

        def salvar() -> None:
            preferencias = PreferenciasAnalise(
                round(confianca.value, 2),
                round(topico.value, 2),
                None if alvo.value == SEM_ALVO else alvo.value,
            )
            try:
                gravar_analise(ESTADO.contexto(), preferencias)
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            ui.notify('Configurações gravadas; valem na próxima análise.', type='positive')

        ui.button('Salvar', icon='save', on_click=salvar).mark('salvar-analise')


def secao_das_disciplinas() -> None:
    with cartao('Disciplinas e temas', icone='category'):
        ui.label('Junte nomes diferentes da mesma disciplina e diga se ela é geral ou específica.').classes(
            'text-sm ca-texto-suave'
        )
        ui.button('Abrir', icon='arrow_forward', on_click=lambda: ui.navigate.to('/disciplinas')).props(
            'flat'
        ).mark('abrir-disciplinas')
        ui.separator()
        situacao_do_dicionario()


def situacao_do_dicionario() -> None:
    try:
        atual = dicionario.situacao(ESTADO.contexto())
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
        return
    ui.label('Dicionário de temas').classes('font-bold')
    if not atual.existe:
        situacao('Não usado. Ele ajuda a achar o tema de cada questão.', Tom.INFO)
    elif atual.ligado:
        situacao(f'Usado, com {atual.entradas} temas.', Tom.SUCESSO)
    else:
        situacao('Desligado.', Tom.INFO)
    if atual.ultimo is not None:
        ui.label(dicionario.resumo_do_ultimo(atual.ultimo)).classes('text-sm')
        if atual.ultimo.alerta and atual.ligado:
            situacao('O último teste mostrou piora: veja os detalhes.', Tom.ALERTA)
    ui.button(
        'Ver detalhes', icon='arrow_forward', on_click=lambda: ui.navigate.to('/disciplinas?aba=temas')
    ).props('flat').mark('abrir-dicionario')


def secao_do_projeto() -> None:
    with cartao('Pasta do projeto', icone='folder'), ui.row().classes('items-center').style(tema.gap('sm')):
        ui.label(str(ESTADO.projeto)).classes('font-mono text-sm')
        ui.button('Trocar', icon='folder_open', on_click=lambda: ui.navigate.to('/projeto')).props('flat')


TEMAS = {TemaGui.SISTEMA.value: 'O do sistema', TemaGui.CLARO.value: 'Claro', TemaGui.ESCURO.value: 'Escuro'}


def secao_da_aparencia() -> None:
    config_global = resolver_home() / 'config.toml'
    with cartao('Aparência', icone='contrast'):

        def trocar(evento) -> None:
            escolhido = TemaGui(evento.value)
            gravar_tema_da_gui(config_global, escolhido)
            ui.dark_mode(tema.VALOR_DO_MODO[escolhido])

        rotulo(ui.toggle(TEMAS, value=tema_da_gui(config_global).value, on_change=trocar), 'tema').mark(
            'tema-gui'
        )


class SecaoDaIa:
    """Desligada por padrão; ligar pede o provedor, mostra o que é enviado e guarda a chave no cofre."""

    def __init__(self) -> None:
        estado = ia.estado_da_ia(ESTADO.contexto())
        with cartao('IA para ler editais', icone='smart_toy'):
            self.usar = ui.checkbox(
                'Usar IA para ler editais (requer chave)', value=estado.ligada, on_change=self.alternar
            ).mark('usar-ia')
            self.situacao = ui.label(self.descrever(estado)).classes('text-sm').mark('situacao-ia')
            with ui.column().classes('w-full').style(tema.gap('sm')) as self.formulario:
                self.provedor = (
                    rotulo(
                        ui.select(
                            ia.provedores(),
                            label='Provedor',
                            value=estado.provedor or ia.provedores()[0],
                            on_change=lambda e: self.aviso.set_text(ia.aviso(e.value)),
                        ),
                        'provedor de IA',
                    )
                    .classes('w-full')
                    .mark('provedor-ia')
                )
                with aviso('O que vai para o provedor', tom=Tom.ALERTA).mark('aviso-ia-cartao'):
                    self.aviso = ui.label(ia.aviso(self.provedor.value)).classes(
                        'text-sm whitespace-pre-line'
                    )
                    self.aviso.mark('aviso-ia')
                self.chave = (
                    rotulo(
                        ui.input('Chave da API', password=True, password_toggle_button=True),
                        'chave da API',
                    )
                    .classes('w-full')
                    .mark('chave-ia')
                )
                ui.label(
                    'A chave vai para o cofre do sistema (ou para ~/.concurso/.env, só seu), nunca para os '
                    'arquivos de configuração.'
                ).classes('text-sm ca-texto-suave')
                ui.button('Concordo e ligar', icon='check', on_click=self.ligar).mark('ligar-ia')
            self.formulario.set_visibility(estado.ligada)

    @staticmethod
    def descrever(estado: ia.EstadoIa) -> str:
        if not estado.ligada:
            return 'Desligada: a leitura do edital é só local.'
        if estado.variavel_chave is None:
            return f'Ligada: {estado.provedor} (local, sem chave).'
        if estado.chave_em is None:
            return f'Ligada: {estado.provedor}, mas sem chave; informe a chave abaixo.'
        return f'Ligada: {estado.provedor}; chave em {estado.chave_em}.'

    def alternar(self, evento) -> None:
        if evento.value:
            self.formulario.set_visibility(True)
            return
        self.formulario.set_visibility(False)
        try:
            ia.desligar_ia(ESTADO.contexto())
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        self.situacao.set_text(self.descrever(ia.estado_da_ia(ESTADO.contexto())))

    def ligar(self) -> None:
        try:
            ia.ligar_ia(ESTADO.contexto(), self.provedor.value, self.chave.value)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha ao ligar a IA', exc_info=True)
            mostrar_erro(erro)
            return
        self.chave.value = ''
        self.situacao.set_text(self.descrever(ia.estado_da_ia(ESTADO.contexto())))
        ui.notify('IA ligada.', type='positive')


EXPLICACAO_AVISO = (
    'Ao abrir, consulta o GitHub no máximo uma vez por dia e mostra no cabeçalho quando há versão nova. '
    'Só o arquivo da versão mais nova é pedido; nenhum dado seu vai junto. Instalar continua pedindo o seu clique.'
)
CANAIS = {
    CanalAtualizacao.STABLE.value: 'stable: versões testadas',
    CanalAtualizacao.BETA.value: 'beta: versões novas antes das outras pessoas, que podem ter problemas',
}


def secao_avancada() -> None:
    config_global = resolver_home() / 'config.toml'
    atuais = atualizacao.ler_preferencias(config_global)
    with ui.expansion('Avançado', icon='tune').classes('w-full').mark('avancado'):
        ui.label('Atualizações').classes('font-bold')
        aviso = ui.checkbox('Avisar quando houver versão nova', value=atuais.verificar_ao_abrir).mark(
            'verificar-ao-abrir'
        )
        ui.label(EXPLICACAO_AVISO).classes('text-sm ca-texto-suave')
        canal = (
            rotulo(ui.select(CANAIS, label='Canal', value=atuais.canal.value), 'canal de atualização')
            .classes('w-full')
            .mark('canal-atualizacao')
        )

        def gravar() -> None:
            try:
                atualizacao.gravar_preferencias(
                    config_global, atualizacao.Preferencias(CanalAtualizacao(canal.value), bool(aviso.value))
                )
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
            ui.notify('Preferência de atualização gravada.', type='positive')

        aviso.on_value_change(gravar)
        canal.on_value_change(gravar)


class SecaoDaCalibracao:
    """Ajusta a leitura das folhas por uma folha preenchida e as respostas digitadas dela."""

    def __init__(self) -> None:
        self.folha: Path | None = None
        with cartao('Calibrar a leitura da folha', icone='tune'):
            ui.label(
                f'Envie uma folha de respostas já preenchida e digite as {QUESTOES_CALIBRACAO} primeiras '
                'respostas dela (use - para branco). O app ajusta a leitura das suas folhas por ela.'
            ).classes('text-sm')
            ui.upload(label='Folha preenchida', auto_upload=True, on_upload=self.receber_folha).props(
                'accept=".pdf,.png,.jpg,.jpeg"'
            ).classes('w-full').mark('folha-calibracao')
            self.digitadas = rotulo(
                ui.input(f'Respostas das {QUESTOES_CALIBRACAO} primeiras questões', placeholder='ABCD-'),
                'respostas para a calibração',
            ).mark('calibracao')
            self.botao = (
                ui.button('Calibrar', icon='tune', on_click=self.calibrar).props('outline').mark('calibrar')
            )

    async def receber_folha(self, evento: events.UploadEventArguments) -> None:
        destino = nova_pasta_de_envio(ESTADO.contexto()) / Path(PureWindowsPath(evento.file.name).name).name
        await evento.file.save(destino)
        self.folha = destino

    async def calibrar(self) -> None:
        if self.folha is None or not (self.digitadas.value or '').strip():
            ui.notify('Envie a folha e digite as respostas dela antes de calibrar.', type='warning')
            return
        self.botao.disable()
        try:
            await run.io_bound(inicio.salvar_calibracao, ESTADO.contexto(), self.folha, self.digitadas.value)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha na calibração', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            self.botao.enable()
        ESTADO.forcar_proxima_analise = True
        ui.notify('Calibração gravada; a próxima análise relê as folhas.', type='positive')
