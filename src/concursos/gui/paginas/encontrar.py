import logging
import threading
from collections.abc import Callable

from nicegui import run, ui

from concursos.aplicacao import integracoes, simulados
from concursos.aplicacao.nomes import opcoes_de_concurso
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.resultados import abrir_no_navegador
from concursos.datas import data_br
from concursos.gui import tema
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.consentimento import consentimento
from concursos.gui.componentes.dialogo import ver_texto
from concursos.gui.componentes.situacao import situacao
from concursos.gui.estado import ESTADO
from concursos.gui.interacao import InteracaoCanceladaError, InteracaoGui
from concursos.gui.progresso import Andamento
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.integracoes.pci_mcp import REGIOES, DatasInscricao
from concursos.municipios import municipios, ufs

logger = logging.getLogger('concursos')

QUALQUER = '(qualquer)'
SEM_ALVO = '(nenhum)'
COMO_IMPORTAR = (
    'O app abre a página da prova no seu navegador. Baixe lá o PDF da prova e o do gabarito (o PCI pede '
    'captcha); o app os encontra na pasta de downloads e cadastra o simulado.'
)
EXPLICACAO_TERMO = (
    'O termo são as palavras procuradas no nome das provas do PCI; só aparecem as provas que têm todas elas. '
    'Sem termo, o app usa as duas primeiras palavras do cargo do concurso-alvo, primeiro com a banca e depois '
    'sem ela. Nada achado? Use menos palavras, ex.: "auditor tcu".'
)
TERMO_LIVRE = 'ex.: auditor sefaz df'


def prazo(datas: DatasInscricao) -> str:
    if not datas.fim:
        return datas.texto or 'sem data'
    fim = data_br(datas.fim)
    dias = datas.dias_ate_fim
    if dias is None:
        return fim
    if dias < 0:
        return f'{fim} (encerradas)'
    return f'{fim} ({dias} {"dia" if dias == 1 else "dias"})'


def lista(texto: str | None) -> list[str]:
    return [parte.strip() for parte in (texto or '').split(',') if parte.strip()]


def ou_nada(texto: str | None) -> str | None:
    return (texto or '').strip() or None


def escolhido(valor: str | None) -> str | None:
    return None if valor in (None, '', QUALQUER) else valor


def ligar_pci(recarregar: Callable[[], None]) -> None:
    try:
        contexto = ESTADO.contexto()
        integracoes.ligar_pci(contexto, integracoes.configuracao_pci(contexto).url)
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
        return
    recarregar()


def desligar_pci(recarregar: Callable[[], None]) -> None:
    try:
        integracoes.desligar_pci(ESTADO.contexto())
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
        return
    recarregar()


def pci_ligado(recarregar: Callable[[], None]) -> bool:
    """Desligado, mostra o aviso e nenhuma consulta é feita."""
    configuracao = integracoes.configuracao_pci(ESTADO.contexto())
    if not configuracao.enabled:
        consentimento(
            integracoes.aviso_pci(configuracao.url, configuracao), 'pci', lambda: ligar_pci(recarregar)
        )
        return False
    return True


class PainelEncontrar:
    def __init__(self, recarregar: Callable[[], None]) -> None:
        self.concursos = []
        if not pci_ligado(recarregar):
            return
        configuracao = integracoes.configuracao_pci(ESTADO.contexto())
        uf = configuracao.uf.upper()
        ui.label(
            'Sem filtro, a busca usa os cargos e a UF do seu perfil. Separe vários cargos por vírgula.'
        ).classes('text-sm ca-texto-suave')
        with ui.row().classes('w-full items-end').style(tema.gap('sm')):
            self.cargo = (
                rotulo(ui.input('Cargo', value=', '.join(configuracao.cargos)), 'cargo')
                .classes('min-w-64')
                .mark('filtro-cargo')
            )
            self.uf = (
                rotulo(
                    ui.select([QUALQUER, *ufs()], label='UF', value=uf or QUALQUER, on_change=self.trocar_uf),
                    'UF',
                )
                .classes('w-28')
                .mark('filtro-uf')
            )
            self.cidade = (
                rotulo(
                    ui.select(
                        municipios(uf),
                        label='Cidade',
                        value=configuracao.cidade if configuracao.cidade in municipios(uf) else None,
                        with_input=True,
                        clearable=True,
                    ),
                    'cidade',
                )
                .classes('min-w-48')
                .mark('filtro-cidade')
            )
            self.cidade.set_enabled(bool(uf))
            self.regiao = (
                rotulo(
                    ui.select(
                        [QUALQUER, *REGIOES],
                        label='Região',
                        value=configuracao.regiao if configuracao.regiao in REGIOES else QUALQUER,
                    ),
                    'região',
                )
                .classes('min-w-40')
                .mark('filtro-regiao')
            )
            self.botao = ui.button('Buscar', icon='search', on_click=self.buscar).mark('buscar-pci')
            self.lembrar = ui.checkbox('Lembrar estes filtros').mark('lembrar-filtros')
        with ui.row().classes('items-center').style(tema.gap('sm')):
            self.atualizado = ui.label().classes('text-sm ca-texto-suave').mark('situacao-cache')
            self.atualizar = (
                ui.button('Atualizar agora', icon='refresh', on_click=lambda: self.buscar(refresh=True))
                .props('flat dense')
                .mark('atualizar-pci')
            )
        self.mostrar_cache()
        self.resultado = ui.column().classes('w-full').style(tema.gap('sm'))
        ui.separator()
        ui.label('Acompanhando no radar de prazos').classes('text-lg font-bold')
        self.acompanhados()
        for linha in integracoes.linhas_do_radar(ESTADO.contexto()):
            ui.label(linha).classes('text-sm')
        ui.button('Desligar o PCI', on_click=lambda: desligar_pci(recarregar)).props('flat').mark(
            'desligar-pci'
        )

    def trocar_uf(self, evento) -> None:
        uf = escolhido(evento.value)
        self.cidade.set_options(municipios(uf), value=None)
        self.cidade.set_enabled(uf is not None)

    def mostrar_cache(self) -> None:
        try:
            texto = integracoes.situacao_do_cache(ESTADO.contexto())
        except Exception:  # noqa: BLE001
            logger.debug('falha ao ler o cache do PCI', exc_info=True)
            texto = None
        self.atualizado.set_text(texto or '')
        self.atualizado.set_visibility(texto is not None)
        self.atualizar.set_visibility(texto is not None)

    def filtros(self) -> dict:
        return {
            'cargos': lista(self.cargo.value),
            'uf': escolhido(self.uf.value),
            'cidade': escolhido(self.cidade.value),
            'regiao': escolhido(self.regiao.value),
        }

    async def buscar(self, refresh: bool = False) -> None:
        filtros = self.filtros()
        if self.lembrar.value:
            try:
                integracoes.gravar_filtros_pci(ESTADO.contexto(), **filtros)
            except Exception as erro:  # noqa: BLE001
                mostrar_erro(erro)
                return
        self.botao.disable()
        try:
            self.concursos = await run.io_bound(
                integracoes.descobrir, Opcoes(ESTADO.contexto()), refresh=refresh, **filtros
            )
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha na busca do PCI pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            self.botao.enable()
        self.mostrar_cache()
        self.mostrar()

    def mostrar(self) -> None:
        self.resultado.clear()
        with self.resultado:
            if not self.concursos:
                ui.label('Nenhum concurso com esses filtros.')
                return
            for concurso in self.concursos:
                with ui.card().classes('w-full').mark(f'concurso-{concurso.id}'):
                    ui.label(concurso.titulo).classes('font-bold')
                    detalhes = ' · '.join(
                        p for p in (integracoes.regiao_do_concurso(concurso), concurso.cargos_resumo) if p
                    )
                    ui.label(detalhes).classes('text-sm').mark(f'regiao-{concurso.id}')
                    if concurso.vagas_salario:
                        ui.label(concurso.vagas_salario).classes('text-sm')
                    ui.label(f'Inscrições até {prazo(concurso.datas)}').classes('text-sm')
                    with ui.row():
                        ui.button(
                            'Ver página',
                            icon='open_in_new',
                            on_click=lambda c=concurso: abrir_no_navegador(c.link),
                        ).props('flat').mark(f'abrir-{concurso.id}')
                        ui.button(
                            'Acompanhar',
                            icon='notifications',
                            on_click=lambda c=concurso: self.acompanhar(c.id),
                        ).props('outline').mark(f'acompanhar-{concurso.id}')
                        ui.button(
                            'Adicionar ao meu projeto',
                            icon='library_add',
                            on_click=lambda c=concurso: self.adicionar(c.id),
                        ).mark(f'adicionar-{concurso.id}')

    def acompanhar(self, identificador: int) -> None:
        mensagens: list[str] = []
        try:
            integracoes.registrar_interesse(
                Opcoes(ESTADO.contexto(), saida=mensagens.append), self.concursos, identificador
            )
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        ui.notify(' '.join(mensagens), type='positive')
        self.acompanhados.refresh()

    def adicionar(self, identificador: int) -> None:
        mensagens: list[str] = []
        try:
            integracoes.adicionar_ao_projeto(
                Opcoes(ESTADO.contexto(), saida=mensagens.append), self.concursos, identificador
            )
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        ui.notify('Concurso adicionado. Falta o edital e os arquivos da prova.', type='positive')
        ui.navigate.to('/')

    @ui.refreshable_method
    def acompanhados(self) -> None:
        try:
            itens = integracoes.interesses(ESTADO.contexto()).itens
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        if not itens:
            ui.label('Nenhum ainda. Use "Acompanhar" num resultado da busca.').classes('text-sm')
            return
        for item in itens:
            with ui.row().classes('items-center').style(tema.gap('sm')).mark(f'interesse-{item["id"]}'):
                ui.label(item['titulo'])
                if item.get('fim'):
                    ui.label(f'inscrições até {data_br(item["fim"])}').classes('text-sm ca-texto-suave')
                ui.button('Deixar de acompanhar', on_click=lambda i=item['id']: self.esquecer(i)).props(
                    'flat dense'
                ).mark(f'esquecer-{item["id"]}')

    def esquecer(self, identificador: int) -> None:
        try:
            integracoes.esquecer_interesse(Opcoes(ESTADO.contexto()), identificador)
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        self.acompanhados.refresh()


class PainelProvasAnteriores:
    def __init__(self, recarregar: Callable[[], None]) -> None:
        self.achados: integracoes.ProvasAnteriores | None = None
        self.andamento = Andamento()
        self.marcadas: dict[int, ui.checkbox] = {}
        if not pci_ligado(recarregar):
            return
        contexto = ESTADO.contexto()
        opcoes = {SEM_ALVO: SEM_ALVO, **opcoes_de_concurso(contexto)}
        with ui.column().classes('w-full').style(tema.gap('sm')) as self.recipiente:
            with ui.row().classes('w-full items-end').style(tema.gap('sm')):
                self.alvo = (
                    rotulo(
                        ui.select(opcoes, label='Concurso-alvo', value=SEM_ALVO, on_change=self.trocar_alvo),
                        'concurso-alvo',
                    )
                    .classes('min-w-48')
                    .mark('alvo-provas')
                )
                self.termo = (
                    rotulo(ui.input('Termo', placeholder=TERMO_LIVRE), 'termo da busca')
                    .classes('min-w-64')
                    .mark('termo-provas')
                )
                self.botao = ui.button('Buscar', icon='search', on_click=self.buscar).mark('buscar-provas')
            with ui.row().classes('items-start no-wrap').style(tema.gap('xs')):
                ui.icon('info', size='sm').props('aria-hidden=true')
                ui.label(EXPLICACAO_TERMO).classes('text-sm').mark('explicacao-termo')
            ui.label(COMO_IMPORTAR).classes('text-sm')
            self.resultado = ui.column().classes('w-full').style(tema.gap('sm'))
            self.importacao = ui.column().classes('w-full')
            self.focado = ui.column().classes('w-full')
            with ui.expansion('Mensagens da importação', icon='list').classes('w-full'):
                self.mensagens = ui.log(max_lines=500).classes('h-40 w-full').mark('mensagens-importacao')
        self.mostrar_focado(None)
        ui.timer(0.2, self.atualizar)

    def atualizar(self) -> None:
        for linha in self.andamento.retirar_linhas():
            self.mensagens.push(linha)
            if linha.startswith('Passo ') and hasattr(self, 'passo'):
                self.passo.set_text(linha)

    def trocar_alvo(self, evento) -> None:
        alvo = None if evento.value == SEM_ALVO else evento.value
        termos = integracoes.termos_previstos(ESTADO.contexto(), alvo)
        self.termo.props(f'placeholder="{termos[0] if termos else TERMO_LIVRE}"')

    async def buscar(self) -> None:
        self.botao.disable()
        termo = ou_nada(self.termo.value)
        try:
            self.achados = await run.io_bound(
                integracoes.provas_anteriores,
                Opcoes(ESTADO.contexto()),
                concurso=None if self.alvo.value == SEM_ALVO else self.alvo.value,
                termos=[termo] if termo else None,
            )
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha na busca de provas anteriores pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            self.botao.enable()
        self.mostrar()

    def mostrar(self) -> None:
        self.resultado.clear()
        self.marcadas = {}
        if self.achados is None:
            return
        raiz = ESTADO.contexto().provas
        with self.resultado:
            ui.label(f'Busca: {self.achados.termo}').classes('text-sm ca-texto-suave').mark('termo-usado')
            if not self.achados.provas:
                ui.label('Nenhuma prova anterior encontrada; tente outro termo.')
                return
            for prova in self.achados.provas:
                with ui.card().classes('w-full').mark(f'prova-{prova.id}'):
                    with ui.row().classes('items-center').style(tema.gap('sm')):
                        self.marcadas[prova.id] = ui.checkbox().mark(f'selecionar-{prova.id}')
                        ui.label(prova.descricao).classes('font-bold')
                        if integracoes.ja_importada(raiz, prova):
                            situacao('importada', Tom.SUCESSO, icone='check_circle')
                    ano = f' ({prova.ano})' if prova.ano else ''
                    ui.label(f'{prova.orgao}{ano} · {prova.organizadora}').classes('text-sm')
                    with ui.row():
                        ui.button(
                            'Ver página',
                            icon='open_in_new',
                            on_click=lambda p=prova: abrir_no_navegador(p.link),
                        ).props('flat')
                        ui.button(
                            'Importar como simulado',
                            icon='download',
                            on_click=lambda p=prova: self.importar([p.id]),
                        ).props('outline').mark(f'importar-{prova.id}')
            with ui.row().style(tema.gap('sm')):
                ui.button(
                    'Importar selecionadas',
                    icon='checklist',
                    on_click=lambda: self.importar([i for i, caixa in self.marcadas.items() if caixa.value]),
                ).props('outline').mark('importar-selecionadas')
                ui.button(
                    'Importar todas',
                    icon='download_for_offline',
                    on_click=lambda: self.importar([p.id for p in self.achados.provas]),
                ).mark('importar-todas')

    async def importar(self, identificadores: list[int]) -> None:
        if ESTADO.ocupado or self.achados is None:
            return
        if not identificadores:
            ui.notify('Marque pelo menos uma prova.', type='warning')
            return
        ESTADO.ocupado = True
        cancelar = threading.Event()
        self.importacao.clear()
        with self.importacao, ui.card().classes('w-full').mark('importando'):
            self.passo = ui.label('Esperando os PDFs na pasta de downloads…').mark('passo-importacao')
            ui.linear_progress(show_value=False).props('indeterminate')
            ui.button('Cancelar', icon='close', on_click=cancelar.set).mark('cancelar-importacao')
        opcoes = Opcoes(
            ESTADO.contexto(),
            interacao=InteracaoGui(self.recipiente, self.andamento.escrever),
            saida=self.andamento.escrever,
        )
        try:
            lote = await run.io_bound(
                integracoes.importar_simulados,
                opcoes,
                self.achados.provas,
                identificadores,
                self.achados.alvo,
                integracoes.espera_cancelavel(cancelar),
            )
        except InteracaoCanceladaError:
            ui.notify('Cadastro do simulado cancelado.')
            return
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha ao importar os simulados pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            ESTADO.ocupado = False
            self.importacao.clear()
            self.atualizar()
        with self.recipiente:
            await self.concluir(lote)

    async def concluir(self, lote: integracoes.LoteDeSimulados) -> None:
        self.mostrar()
        if lote.cancelado:
            ui.notify('Importação cancelada; o que você já baixou continua na pasta de downloads.')
        if not lote.importadas:
            if lote.falhas:
                ui.notify('Nenhuma prova foi importada; veja as mensagens da importação.', type='warning')
            return
        with (
            self.importacao,
            aviso(f'Importação terminada: {lote.resumo()}.', tom=Tom.SUCESSO).mark('simulado-importado'),
        ):
            ui.button('Ver concursos', on_click=lambda: ui.navigate.to('/'))
        try:
            focado = await run.io_bound(simulados.simulado_focado_do_projeto, Opcoes(ESTADO.contexto()))
        except Exception:  # noqa: BLE001
            logger.debug('falha ao montar o simulado focado pela GUI', exc_info=True)
            return
        self.mostrar_focado(focado)

    def mostrar_focado(self, focado) -> None:
        self.focado.clear()
        texto = simulados.texto_do_simulado_focado(ESTADO.contexto())
        if texto is None:
            return
        resumo = (
            f'Simulado focado: {focado.total} questões das provas anteriores nos seus tópicos mais fracos'
            if focado is not None
            else 'Simulado focado: as questões das provas anteriores nos seus tópicos mais fracos'
        )
        with self.focado, ui.row().classes('items-center').style(tema.gap('sm')).mark('simulado-focado'):
            ui.icon('track_changes', size='sm').props('aria-hidden=true')
            ui.label(resumo)
            ui.button('Ver', on_click=lambda: ver_texto('Simulado focado', texto)).props('flat dense').mark(
                'ver-simulado-focado'
            )
