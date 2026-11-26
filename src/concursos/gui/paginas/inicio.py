import logging
from pathlib import Path

from nicegui import run, ui

from concursos.aplicacao import exemplo, inicio
from concursos.aplicacao.opcoes import Opcoes
from concursos.gui import tema
from concursos.gui.componentes.assistente import Assistente
from concursos.gui.componentes.aviso import aviso
from concursos.gui.componentes.relatorio import relatorio
from concursos.gui.estado import ESTADO
from concursos.gui.paginas.projeto import exigir_projeto
from concursos.gui.tema import Tom
from concursos.gui.textos import mostrar_erro, rotulo
from concursos.linguagem import rotulo_do_arquivo

logger = logging.getLogger('concursos')

TITULOS = ['Seu nome', 'Pasta', 'Primeiro resultado']
PASSO_NOME, PASSO_PASTA, PASSO_RESULTADO = range(3)


def pagina() -> None:
    if not exigir_projeto():
        return
    Onboarding()


class Onboarding:
    """Três passos: nome, pasta, primeiro resultado. PCI/IA ficam para o momento do uso."""

    def __init__(self) -> None:
        self.contexto = ESTADO.contexto()
        atuais = inicio.respostas_atuais(self.contexto)
        raiz = self.contexto.raiz
        with ui.column().classes('w-full max-w-3xl').style(tema.gap('md')):
            ui.label('Bem-vindo ao Gabarito Vivo').classes('text-2xl font-bold')
            self.assistente = Assistente(TITULOS, antes_de_avancar=self.antes_de_avancar)
        with self.assistente.passo(PASSO_NOME):
            ui.label('O seu nome aparece nos relatórios e fica só neste computador.').classes(
                'ca-texto-suave'
            )
            self.nome = (
                rotulo(ui.input('Seu nome', value=atuais.nome or ''), 'seu nome')
                .classes('w-full')
                .mark('nome')
            )
            self.cargo = (
                rotulo(
                    ui.input('Cargo que você busca', value=atuais.cargo or ''),
                    'cargo que você busca',
                )
                .classes('w-full')
                .mark('cargo')
            )
            self.nome.on('keydown.enter', lambda: self.assistente.avancar())
        with self.assistente.passo(PASSO_PASTA):
            ui.label(f'As provas e as análises ficam em {raiz}.').mark('pasta-do-projeto')
            ui.label(
                f'Cada concurso é uma subpasta em {rotulo_do_arquivo("provas/")}, e os relatórios vão para '
                f'{rotulo_do_arquivo("analises/")}. Seus dados pertencem a você.'
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
        with self.assistente.passo(PASSO_RESULTADO):
            ui.label(
                'Cadastre sua última prova ou use o concurso de exemplo para ver o diagnóstico em seguida.'
            )
            with ui.row().classes('items-center').style(tema.gap('sm')):
                self.botao_exemplo = ui.button(
                    'Usar concurso de exemplo', icon='auto_awesome', on_click=self.ver_exemplo
                ).mark('ver-exemplo')
                ui.button('Cadastrar minha prova', icon='add', on_click=self.cadastrar_prova).props(
                    'outline'
                ).mark('cadastrar-prova')
            self.resultado = ui.column().classes('w-full').style(tema.gap('sm'))

    async def antes_de_avancar(self, indice: int, pulou: bool) -> bool:
        del pulou
        try:
            if indice == PASSO_NOME:
                inicio.validar_nome(self.nome.value or '')
            elif indice == PASSO_PASTA:
                await self.gravar()
        except Exception as erro:  # noqa: BLE001
            logger.debug('falha no onboarding pela GUI', exc_info=True)
            mostrar_erro(erro)
            return False
        return True

    async def gravar(self) -> None:
        respostas = inicio.respostas_do_formulario(
            self.contexto,
            self.nome.value or '',
            self.provas.value or '',
            self.analises.value or '',
            False,
            cargo=self.cargo.value or '',
        )
        opcoes = await run.io_bound(inicio.concluir_onboarding, Opcoes(self.contexto), respostas)
        ESTADO.candidato = opcoes.contexto.candidato

    async def cadastrar_prova(self) -> None:
        await self.gravar()
        ui.navigate.to('/novo')

    async def ver_exemplo(self) -> None:
        await self.gravar()
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
                'Primeiro raio-X concluído!',
                'Este é um concurso de exemplo. Nada mudou no seu projeto. Abrindo o diagnóstico…',
                tom=Tom.SUCESSO,
            ).mark('exemplo-pronto')
            relatorio(indice)
        if _tem_diagnostico(indice):
            ui.timer(1.5, lambda: ui.navigate.to('/resultados'), once=True)
        else:
            ui.timer(1.5, lambda: ui.navigate.to('/'), once=True)


def _tem_diagnostico(indice: Path) -> bool:
    return indice.is_file() and indice.stat().st_size > 0
