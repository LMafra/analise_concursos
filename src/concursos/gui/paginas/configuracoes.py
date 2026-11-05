import logging

from nicegui import ui

from concursos.aplicacao import atualizador as atualizacao
from concursos.aplicacao import ia
from concursos.aplicacao.preferencias import PreferenciasAnalise, gravar_analise, ler_analise
from concursos.config.contexto import resolver_home
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.modelo import CanalAtualizacao
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
    with ui.column().classes('w-full max-w-2xl gap-6'):
        ui.label('Configurações').classes('text-2xl font-bold')
        try:
            secao_da_analise()
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
        secao_do_projeto()
        SecaoDaIa()
        secao_avancada()


def controle_de_limiar(titulo: str, valor: float, explicacao: str, marca: str) -> ui.slider:
    ui.label(titulo).classes('font-bold')
    with ui.row().classes('items-center w-full no-wrap gap-4'):
        controle = rotulo(ui.slider(min=0.05, max=0.95, step=0.05, value=valor), titulo).classes('flex-grow')
        controle.mark(marca)
        ui.label().bind_text_from(controle, 'value', lambda v: f'{v:.2f}'.replace('.', ',')).classes(
            'w-12 font-mono'
        )
    ui.label(explicacao).classes('text-sm text-grey-8')
    return controle


def secao_da_analise() -> None:
    contexto = ESTADO.contexto()
    atuais = ler_analise(contexto)
    nomes = [p.name for p in listar_concursos(contexto.provas)] if contexto.provas.is_dir() else []
    with ui.card().classes('w-full'):
        ui.label('Análise').classes('text-lg font-bold')
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
        ui.label(EXPLICACAO_ALVO).classes('text-sm text-grey-8')

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


def secao_do_projeto() -> None:
    with ui.card().classes('w-full'):
        ui.label('Pasta do projeto').classes('text-lg font-bold')
        with ui.row().classes('items-center gap-2'):
            ui.label(str(ESTADO.projeto)).classes('font-mono text-sm')
            ui.button('Trocar', icon='folder_open', on_click=lambda: ui.navigate.to('/projeto')).props('flat')


class SecaoDaIa:
    """Desligada por padrão; ligar pede o provedor, mostra o que é enviado e guarda a chave no cofre."""

    def __init__(self) -> None:
        estado = ia.estado_da_ia(ESTADO.contexto())
        with ui.card().classes('w-full'):
            ui.label('IA para ler editais').classes('text-lg font-bold')
            self.usar = ui.checkbox(
                'Usar IA para ler editais (requer chave)', value=estado.ligada, on_change=self.alternar
            ).mark('usar-ia')
            self.situacao = ui.label(self.descrever(estado)).classes('text-sm').mark('situacao-ia')
            with ui.column().classes('w-full gap-2') as self.formulario:
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
                self.aviso = ui.label(ia.aviso(self.provedor.value)).classes('text-sm bg-amber-1 p-2 rounded')
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
                ).classes('text-sm text-grey-8')
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
        ui.label(EXPLICACAO_AVISO).classes('text-sm text-grey-8')
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
