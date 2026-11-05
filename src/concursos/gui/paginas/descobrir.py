import logging
import threading

from nicegui import run, ui

from concursos.aplicacao import integracoes
from concursos.aplicacao.opcoes import Opcoes
from concursos.aplicacao.resultados import abrir_no_navegador
from concursos.gui.componentes.consentimento import consentimento
from concursos.gui.estado import ESTADO
from concursos.gui.interacao import InteracaoCanceladaError, InteracaoGui
from concursos.gui.progresso import Andamento
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.integracoes.pci_mcp import REGIOES, DatasInscricao
from concursos.status import listar_concursos

logger = logging.getLogger('concursos')

QUALQUER = '(qualquer)'
SEM_ALVO = '(nenhum)'
COMO_IMPORTAR = (
    'O app abre a página da prova no seu navegador. Baixe lá o PDF da prova e o do gabarito (o PCI pede '
    'captcha); o app os encontra na pasta de downloads e cadastra o simulado.'
)


def prazo(datas: DatasInscricao) -> str:
    if not datas.fim:
        return datas.texto or 'sem data'
    dias = datas.dias_ate_fim
    if dias is None:
        return datas.fim
    if dias < 0:
        return f'{datas.fim} (encerradas)'
    return f'{datas.fim} ({dias} {"dia" if dias == 1 else "dias"})'


def lista(texto: str | None) -> list[str]:
    return [parte.strip() for parte in (texto or '').split(',') if parte.strip()]


def ou_nada(texto: str | None) -> str | None:
    return (texto or '').strip() or None


def ligar_pci(aba: str) -> None:
    try:
        contexto = ESTADO.contexto()
        integracoes.ligar_pci(contexto, integracoes.configuracao_pci(contexto).url)
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
        return
    ui.navigate.to(f'/integracoes?aba={aba}')


def desligar_pci(aba: str) -> None:
    try:
        integracoes.desligar_pci(ESTADO.contexto())
    except Exception as erro:  # noqa: BLE001
        mostrar_erro(erro)
        return
    ui.navigate.to(f'/integracoes?aba={aba}')


def pci_ligado(aba: str) -> bool:
    """Desligado, mostra o aviso e nenhuma consulta é feita."""
    configuracao = integracoes.configuracao_pci(ESTADO.contexto())
    if not configuracao.enabled:
        consentimento(integracoes.aviso_pci(configuracao.url, configuracao), 'pci', lambda: ligar_pci(aba))
        return False
    return True


class PainelDescobrir:
    def __init__(self, aba: str) -> None:
        self.concursos = []
        if not pci_ligado(aba):
            return
        ui.label(
            'Sem filtro, a busca usa os cargos e a UF do seu perfil. Separe vários cargos por vírgula.'
        ).classes('text-sm text-grey-8')
        with ui.row().classes('w-full items-end gap-2'):
            self.cargo = rotulo(ui.input('Cargo'), 'cargo').classes('min-w-64').mark('filtro-cargo')
            self.uf = rotulo(ui.input('UF', placeholder='ex.: DF'), 'UF').classes('w-24').mark('filtro-uf')
            self.cidade = rotulo(ui.input('Cidade'), 'cidade').classes('min-w-48').mark('filtro-cidade')
            self.regiao = (
                rotulo(ui.select([QUALQUER, *REGIOES], label='Região', value=QUALQUER), 'região')
                .classes('min-w-40')
                .mark('filtro-regiao')
            )
            self.botao = ui.button('Buscar', icon='search', on_click=self.buscar).mark('buscar-pci')
        self.resultado = ui.column().classes('w-full gap-2')
        ui.separator()
        ui.label('Acompanhando no radar de prazos').classes('text-lg font-bold')
        self.acompanhados()
        for linha in integracoes.linhas_do_radar(ESTADO.contexto()):
            ui.label(linha).classes('text-sm')
        ui.button('Desligar o PCI', on_click=lambda: desligar_pci(aba)).props('flat').mark('desligar-pci')

    async def buscar(self) -> None:
        self.botao.disable()
        try:
            self.concursos = await run.io_bound(
                integracoes.descobrir,
                Opcoes(ESTADO.contexto()),
                cargos=lista(self.cargo.value),
                uf=ou_nada(self.uf.value),
                cidade=ou_nada(self.cidade.value),
                regiao=None if self.regiao.value == QUALQUER else self.regiao.value,
            )
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha na busca do PCI pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            self.botao.enable()
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
                        p for p in (concurso.uf, concurso.cargos_resumo, concurso.vagas_salario) if p
                    )
                    ui.label(detalhes).classes('text-sm')
                    ui.label(f'Inscrições até {prazo(concurso.datas)}').classes('text-sm')
                    with ui.row():
                        ui.button(
                            'Abrir',
                            icon='open_in_new',
                            on_click=lambda c=concurso: abrir_no_navegador(c.link),
                        ).props('flat').mark(f'abrir-{concurso.id}')
                        ui.button(
                            'Acompanhar no radar',
                            icon='notifications',
                            on_click=lambda c=concurso: self.acompanhar(c.id),
                        ).props('outline').mark(f'acompanhar-{concurso.id}')

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

    @ui.refreshable_method
    def acompanhados(self) -> None:
        try:
            itens = integracoes.interesses(ESTADO.contexto()).itens
        except Exception as erro:  # noqa: BLE001
            mostrar_erro(erro)
            return
        if not itens:
            ui.label('Nenhum ainda. Use "Acompanhar no radar" num resultado da busca.').classes('text-sm')
            return
        for item in itens:
            with ui.row().classes('items-center gap-2').mark(f'interesse-{item["id"]}'):
                ui.label(item['titulo'])
                if item.get('fim'):
                    ui.label(f'inscrições até {item["fim"]}').classes('text-sm text-grey-8')
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
    def __init__(self, aba: str) -> None:
        self.achados: integracoes.ProvasAnteriores | None = None
        self.andamento = Andamento()
        if not pci_ligado(aba):
            return
        contexto = ESTADO.contexto()
        nomes = [p.name for p in listar_concursos(contexto.provas)] if contexto.provas.is_dir() else []
        ui.label(
            'Busque pelo concurso-alvo (o cargo e o órgão do concurso.yaml dele) ou por um termo livre.'
        ).classes('text-sm text-grey-8')
        with ui.column().classes('w-full gap-2') as self.recipiente:
            with ui.row().classes('w-full items-end gap-2'):
                self.alvo = (
                    rotulo(
                        ui.select([SEM_ALVO, *nomes], label='Concurso-alvo', value=SEM_ALVO), 'concurso-alvo'
                    )
                    .classes('min-w-48')
                    .mark('alvo-provas')
                )
                self.termo = (
                    rotulo(ui.input('Termo', placeholder='ex.: auditor sefaz df'), 'termo da busca')
                    .classes('min-w-64')
                    .mark('termo-provas')
                )
                self.botao = ui.button('Buscar', icon='search', on_click=self.buscar).mark('buscar-provas')
            ui.label(COMO_IMPORTAR).classes('text-sm')
            self.resultado = ui.column().classes('w-full gap-2')
            self.importacao = ui.column().classes('w-full')
            with ui.expansion('Mensagens da importação', icon='list').classes('w-full'):
                self.mensagens = ui.log(max_lines=500).classes('h-40 w-full').mark('mensagens-importacao')
        ui.timer(0.2, self.atualizar)

    def atualizar(self) -> None:
        for linha in self.andamento.retirar_linhas():
            self.mensagens.push(linha)

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
        if self.achados is None:
            return
        with self.resultado:
            ui.label(f'Busca: {self.achados.termo}').classes('text-sm text-grey-8')
            if not self.achados.provas:
                ui.label('Nenhuma prova anterior encontrada; tente outro termo.')
                return
            for prova in self.achados.provas:
                with ui.card().classes('w-full').mark(f'prova-{prova.id}'):
                    ui.label(prova.descricao).classes('font-bold')
                    ano = f' ({prova.ano})' if prova.ano else ''
                    ui.label(f'{prova.orgao}{ano} · {prova.organizadora}').classes('text-sm')
                    with ui.row():
                        ui.button(
                            'Abrir', icon='open_in_new', on_click=lambda p=prova: abrir_no_navegador(p.link)
                        ).props('flat')
                        ui.button(
                            'Importar como simulado',
                            icon='download',
                            on_click=lambda p=prova: self.importar(p.id),
                        ).props('outline').mark(f'importar-{prova.id}')

    async def importar(self, identificador: int) -> None:
        if ESTADO.ocupado or self.achados is None:
            return
        ESTADO.ocupado = True
        cancelar = threading.Event()
        self.importacao.clear()
        with self.importacao, ui.card().classes('w-full').mark('importando'):
            ui.label('Esperando os PDFs na pasta de downloads…')
            ui.button('Cancelar', icon='close', on_click=cancelar.set).mark('cancelar-importacao')
        opcoes = Opcoes(
            ESTADO.contexto(),
            interacao=InteracaoGui(self.recipiente, self.andamento.escrever),
            saida=self.andamento.escrever,
        )
        try:
            codigo = await run.io_bound(
                integracoes.importar_simulado,
                opcoes,
                self.achados.provas,
                identificador,
                self.achados.alvo,
                integracoes.espera_cancelavel(cancelar),
            )
        except integracoes.ImportacaoCanceladaError:
            ui.notify('Importação cancelada; o que você já baixou continua na pasta de downloads.')
            return
        except InteracaoCanceladaError:
            ui.notify('Cadastro do simulado cancelado.')
            return
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha ao importar o simulado pela GUI', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            ESTADO.ocupado = False
            self.importacao.clear()
            self.atualizar()
        if codigo != 0:
            ui.notify('O simulado não foi cadastrado; veja as mensagens da importação.', type='warning')
            return
        with self.importacao, ui.card().classes('bg-green-1 w-full').mark('simulado-importado'):
            ui.label('Importação terminada; confira as mensagens da importação.').classes('font-bold')
            ui.button('Ver concursos', on_click=lambda: ui.navigate.to('/'))
