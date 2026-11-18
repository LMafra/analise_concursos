"""Tokens de design da GUI e o tema claro, escuro ou do sistema; os valores estão em `docs/modelo.md`
e o manual em `docs/marca-gabarito-vivo.md`.

Fora deste módulo, `gui/` não tem cor em hex, classe de cor do Quasar nem `gap-*` (teste): a cor vem
das classes `ca-*` daqui, e o espaçamento, de `gap()` num `style`.
"""

from dataclasses import dataclass, fields
from enum import StrEnum

from nicegui import ui

from concursos.design_tokens import (
    ELEVACAO_1,
    ESPACOS,
    FONTE,
    RAIO_CARTAO,
    css_root_do_relatorio,
)
from concursos.modelo import TemaGui

__all__ = ['css_root_do_relatorio', 'aplicar_tema', 'gap', 'Tom', 'ICONE_DO_TOM', 'CLARO', 'ESCURO']


class Tom(StrEnum):
    INFO = 'info'
    SUCESSO = 'sucesso'
    ALERTA = 'alerta'
    ERRO = 'erro'


ICONE_DO_TOM = {Tom.INFO: 'info', Tom.SUCESSO: 'check_circle', Tom.ALERTA: 'warning', Tom.ERRO: 'error'}


@dataclass(frozen=True)
class Paleta:
    fundo: str
    superficie: str
    texto: str
    texto_suave: str
    borda: str
    primaria: str
    sobre_primaria: str
    primaria_texto: str
    foco: str
    info_fundo: str
    info_icone: str
    info_texto: str
    sucesso_fundo: str
    sucesso_icone: str
    sucesso_texto: str
    erro_fundo: str
    erro_icone: str
    erro_texto: str
    alerta_fundo: str
    alerta_icone: str
    alerta_texto: str


CLARO = Paleta(
    fundo='#FAFAFA',
    superficie='#FFFFFF',
    texto='#14282B',
    texto_suave='#475569',
    borda='#CBD5E1',
    primaria='#14282B',
    sobre_primaria='#FFFFFF',
    primaria_texto='#14282B',
    foco='#117A4B',
    info_fundo='#E6F0F0',
    info_icone='#14282B',
    info_texto='#14282B',
    sucesso_fundo='#E6F4ED',
    sucesso_icone='#0E5A37',
    sucesso_texto='#0E5A37',
    erro_fundo='#FCEBE6',
    erro_icone='#8C2D0D',
    erro_texto='#8C2D0D',
    alerta_fundo='#FEF3C7',
    alerta_icone='#92400E',
    alerta_texto='#92400E',
)

ESCURO = Paleta(
    fundo='#121E20',
    superficie='#1A2C2F',
    texto='#E6ECEC',
    texto_suave='#94A3B8',
    borda='#2D4246',
    primaria='#4ADE80',
    sobre_primaria='#121E20',
    primaria_texto='#4ADE80',
    foco='#4ADE80',
    info_fundo='#1A2C2F',
    info_icone='#94A3B8',
    info_texto='#E6ECEC',
    sucesso_fundo='#143324',
    sucesso_icone='#4ADE80',
    sucesso_texto='#4ADE80',
    erro_fundo='#3A1C14',
    erro_icone='#F87171',
    erro_texto='#F87171',
    alerta_fundo='#3B2D11',
    alerta_icone='#FCD34D',
    alerta_texto='#FCD34D',
)

# O `ui.colors` grava as cores no style do body, que venceria o `body.body--dark`: a primária vai como
# variável. As notificações do Quasar usam texto branco em positive/negative/info e escuro em warning.
CORES_DO_QUASAR = {
    'primary': 'var(--ca-primaria)',
    'positive': '#0E5A37',
    'negative': '#8C2D0D',
    'info': '#14282B',
    'warning': '#FCD34D',
    'dark': ESCURO.superficie,
    'dark_page': ESCURO.fundo,
}

RAIO_DIALOGO = '12px'
ELEVACAO_2 = '0 8px 24px rgb(0 0 0 / .16)'
ALVO_MINIMO = '44px'

VALOR_DO_MODO: dict[TemaGui, bool | None] = {
    TemaGui.SISTEMA: None,
    TemaGui.CLARO: False,
    TemaGui.ESCURO: True,
}


def gap(linha: str, coluna: str | None = None) -> str:
    if coluna is None:
        return f'gap: {ESPACOS[linha]}'
    return f'row-gap: {ESPACOS[linha]}; column-gap: {ESPACOS[coluna]}'


def _variaveis(paleta: Paleta) -> str:
    return ' '.join(
        f'--ca-{campo.name.replace("_", "-")}: {getattr(paleta, campo.name)};' for campo in fields(paleta)
    )


def _tons() -> str:
    return '\n'.join(
        f'.ca-tom-{tom} {{ --ca-tom-fundo: var(--ca-{tom}-fundo); --ca-tom-icone: var(--ca-{tom}-icone); '
        f'--ca-tom-texto: var(--ca-{tom}-texto); }}'
        for tom in Tom
    )


CSS = f"""
:root {{ {_variaveis(CLARO)} }}
body.body--dark {{ {_variaveis(ESCURO)} }}
body {{ font-family: {FONTE}; background: var(--ca-fundo); color: var(--ca-texto); }}
.q-card {{ background: var(--ca-superficie); color: var(--ca-texto); border-radius: {RAIO_CARTAO};
  box-shadow: {ELEVACAO_1}; }}
.q-dialog .q-card {{ border-radius: {RAIO_DIALOGO}; box-shadow: {ELEVACAO_2}; }}
.q-header {{ background: var(--ca-primaria); color: var(--ca-sobre-primaria); }}
.q-drawer {{ background: var(--ca-superficie); color: var(--ca-texto); }}
.q-notification__actions {{ color: inherit; }}
.q-notification__message {{ white-space: pre-line; }}
@layer overrides {{
  .q-btn.bg-primary {{ color: var(--ca-sobre-primaria) !important; }}
  .text-primary, a, .nicegui-link {{ color: var(--ca-primaria-texto) !important; }}
  .q-header .q-btn {{ color: var(--ca-sobre-primaria) !important; }}
  @media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }}
  }}
}}
:focus-visible {{ outline: 3px solid var(--ca-foco); outline-offset: 2px; }}
.ca-texto-suave {{ color: var(--ca-texto-suave); }}
.ca-borda {{ border: 1px solid var(--ca-borda); border-radius: {RAIO_CARTAO}; }}
.ca-alvo {{ min-width: {ALVO_MINIMO}; min-height: {ALVO_MINIMO}; }}
{_tons()}
.ca-aviso {{ background: var(--ca-tom-fundo); color: var(--ca-texto); border-left: 4px solid var(--ca-tom-icone);
  border-radius: {RAIO_CARTAO}; padding: {ESPACOS['md']}; box-shadow: none; }}
.ca-icone-tom {{ color: var(--ca-tom-icone); }}
.ca-situacao {{ color: var(--ca-tom-texto); font-weight: 500; }}
.ca-etapa {{ color: var(--ca-texto-suave); }}
.ca-etapa-atual {{ color: var(--ca-primaria-texto); font-weight: 600; }}
.ca-etapa-feita {{ color: var(--ca-sucesso-texto); }}
.nicegui-log .q-scrollarea__content {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
"""


def aplicar_tema(modo: TemaGui) -> ui.dark_mode:
    ui.colors(**CORES_DO_QUASAR)
    ui.add_css(CSS)
    return ui.dark_mode(VALOR_DO_MODO[modo])
