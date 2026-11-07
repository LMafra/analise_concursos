import logging

from nicegui import run, ui

from concursos.aplicacao import atualizador as atualizacao
from concursos.aplicacao import exemplo, inicio
from concursos.aplicacao.opcoes import Opcoes
from concursos.gui import tema
from concursos.gui.componentes.assistente import Assistente
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.cartao import cartao
from concursos.gui.componentes.relatorio import relatorio
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.configuracoes import EXPLICACAO_AVISO, SecaoDaIa
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.linguagem import rotulo_do_arquivo

logger = logging.getLogger('concursos')

TITULOS = ['Seu nome', 'Pasta', 'Opcionais', 'Primeiro resultado']
PASSO_NOME, PASSO_PASTA, PASSO_OPCIONAIS, PASSO_RESULTADO = range(4)


def pagina() -> None:
    if not exigir_projeto():
        return
    Onboarding()


class Onboarding:
    """As perguntas do `init` em 4 passos; grava ao sair dos opcionais, e o último mostra um resultado."""

    def __init__(self) -> None:
        self.contexto = ESTADO.contexto()
        atuais = inicio.respostas_atuais(self.contexto)
        raiz = self.contexto.raiz
        with ui.column().classes('w-full max-w-3xl').style(tema.gap('md')):
            ui.label('Bem-vindo ao concurso-analise').classes('text-2xl font-bold')
            self.assistente = Assistente(
                TITULOS, opcionais={PASSO_OPCIONAIS}, antes_de_avancar=self.antes_de_avancar
            )
        with self.assistente.passo(PASSO_NOME):
            ui.label('O seu nome aparece nos relatórios e fica só neste computador.').classes(
                'ca-texto-suave'
            )
            self.nome = (
                rotulo(ui.input('Seu nome', value=atuais.nome or ''), 'seu nome')
                .classes('w-full')
                .mark('nome')
            )
            self.nome.on('keydown.enter', lambda: self.assistente.avancar())
        with self.assistente.passo(PASSO_PASTA):
            ui.label(f'As provas e as análises ficam em {raiz}.').mark('pasta-do-projeto')
            ui.label(
                f'Cada concurso é uma subpasta em {rotulo_do_arquivo("provas/")}, e os relatórios vão para '
                f'{rotulo_do_arquivo("analises/")}. Os arquivos não saem deste computador.'
            ).classes('ca-texto-suave')
            ui.button(
                'Usar outra pasta', icon='folder_open', on_click=lambda: ui.navigate.to('/projeto')
            ).props('flat')
            with ui.expansion('Avançado', icon='tune').classes('w-full').mark('avancado-pastas'):
                self.provas = (
                    rotulo(
                        ui.input('Pasta das provas', value=inicio.pasta_no_formulario(atuais.provas, raiz)),
                        'pasta das provas',
                    )
                    .classes('w-full')
                    .mark('pasta-provas')
                )
                self.analises = (
                    rotulo(
                        ui.input(
                            'Pasta das análises', value=inicio.pasta_no_formulario(atuais.analises, raiz)
                        ),
                        'pasta das análises',
                    )
                    .classes('w-full')
                    .mark('pasta-analises')
                )
        with self.assistente.passo(PASSO_OPCIONAIS):
            ui.label(
                'Os dois começam desligados. Ligue só o que quiser; dá para mudar depois em Configurações.'
            ).classes('ca-texto-suave')
            SecaoDaIa()
            with cartao('Aviso de versão nova', icone='new_releases'):
                ligado = atualizacao.ler_preferencias(self.contexto.config_global).verificar_ao_abrir
                self.aviso_de_versao = ui.checkbox('Avisar quando houver versão nova', value=ligado).mark(
                    'opcional-atualizacao'
                )
                ui.label(EXPLICACAO_AVISO).classes('text-sm ca-texto-suave')
        with self.assistente.passo(PASSO_RESULTADO):
            ui.label(
                'Tudo pronto. Veja o app funcionando com um concurso de exemplo, ou cadastre a sua prova.'
            )
            with ui.row().classes('items-center').style(tema.gap('sm')):
                self.botao_exemplo = ui.button(
                    'Ver com um exemplo', icon='auto_awesome', on_click=self.ver_exemplo
                ).mark('ver-exemplo')
                ui.button(
                    'Cadastrar minha prova', icon='add', on_click=lambda: ui.navigate.to('/novo')
                ).props('outline').mark('cadastrar-prova')
                ui.button('Ir para os concursos', on_click=lambda: ui.navigate.to('/')).props('flat').mark(
                    'ir-para-concursos'
                )
            self.resultado = ui.column().classes('w-full').style(tema.gap('sm'))

    async def antes_de_avancar(self, indice: int, pulou: bool) -> bool:
        try:
            if indice == PASSO_NOME:
                inicio.validar_nome(self.nome.value or '')
            elif indice == PASSO_OPCIONAIS:
                await self.gravar(pulou)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha no onboarding pela GUI', exc_info=True)
            mostrar_erro(erro)
            return False
        return True

    async def gravar(self, pulou: bool) -> None:
        respostas = inicio.respostas_do_formulario(
            self.contexto, self.nome.value or '', self.provas.value or '', self.analises.value or '', False
        )
        opcoes = await run.io_bound(inicio.concluir_onboarding, Opcoes(self.contexto), respostas)
        if not pulou:
            atualizacao.gravar_aviso(self.contexto.config_global, bool(self.aviso_de_versao.value))
        ESTADO.candidato = opcoes.contexto.candidato

    async def ver_exemplo(self) -> None:
        self.botao_exemplo.disable()
        self.resultado.clear()
        with self.resultado, ui.row().classes('items-center').style(tema.gap('sm')) as espera:
            ui.spinner()
            ui.label('Analisando o exemplo…')
        try:
            indice = await run.io_bound(exemplo.analisar_exemplo, self.contexto.home)
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha no exemplo', exc_info=True)
            mostrar_erro(erro)
            return
        finally:
            espera.delete()
            self.botao_exemplo.enable()
        with self.resultado:
            aviso(
                'Este é o relatório de um concurso de exemplo',
                'A candidata é fictícia, e nada mudou no seu projeto. Para ver o seu, cadastre a sua prova.',
                tom=Tom.SUCESSO,
            ).mark('exemplo-pronto')
            relatorio(indice)
