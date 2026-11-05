"""Tokens de design da GUI e o tema claro, escuro ou do sistema; os valores estão em `docs/modelo.md`.

Fora deste módulo, `gui/` não tem cor em hex, classe de cor do Quasar nem `gap-*` (teste): a cor vem
das classes `ca-*` daqui, e o espaçamento, de `gap()` num `style`.
"""

from dataclasses import dataclass, fields
from enum import StrEnum

from nicegui import ui

from concursos.modelo import TemaGui


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
    texto='#1E293B',
    texto_suave='#475569',
    borda='#CBD5E1',
    primaria='#1976D2',
    sobre_primaria='#FFFFFF',
    primaria_texto='#1565C0',
    foco='#1976D2',
    info_fundo='#E3F2FD',
    info_icone='#1976D2',
    info_texto='#0D47A1',
    sucesso_fundo='#E8F5E9',
    sucesso_icone='#2E7D32',
    sucesso_texto='#2E7D32',
    erro_fundo='#FFEBEE',
    erro_icone='#D32F2F',
    erro_texto='#C62828',
    alerta_fundo='#FFF8E1',
    alerta_icone='#E65100',
    alerta_texto='#B45309',
)

ESCURO = Paleta(
    fundo='#0F172A',
    superficie='#1E293B',
    texto='#F1F5F9',
    texto_suave='#CBD5E1',
    borda='#334155',
    primaria='#64B5F6',
    sobre_primaria='#0F172A',
    primaria_texto='#64B5F6',
    foco='#64B5F6',
    info_fundo='#0C2A4A',
    info_icone='#64B5F6',
    info_texto='#BFDBFE',
    sucesso_fundo='#14301B',
    sucesso_icone='#66BB6A',
    sucesso_texto='#86EFAC',
    erro_fundo='#3B1518',
    erro_icone='#EF5350',
    erro_texto='#FCA5A5',
    alerta_fundo='#3A2A0A',
    alerta_icone='#FFB74D',
    alerta_texto='#FCD34D',
)

# O `ui.colors` grava as cores no style do body, que venceria o `body.body--dark`: a primária vai como
# variável. As notificações do Quasar usam texto branco em positive/negative/info e escuro em warning.
CORES_DO_QUASAR = {
    'primary': 'var(--ca-primaria)',
    'positive': CLARO.sucesso_texto,
    'negative': CLARO.erro_texto,
    'info': CLARO.info_texto,
    'warning': '#FFB74D',
    'dark': ESCURO.superficie,
    'dark_page': ESCURO.fundo,
}

ESPACOS = {'xs': '4px', 'sm': '8px', 'md': '16px', 'lg': '24px', 'xl': '32px'}
RAIO_CARTAO = '8px'
RAIO_DIALOGO = '12px'
ELEVACAO_1 = '0 1px 2px rgb(0 0 0 / .08)'
ELEVACAO_2 = '0 8px 24px rgb(0 0 0 / .16)'
FONTE = '"Segoe UI", Roboto, "Noto Sans", Ubuntu, sans-serif'

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
@layer overrides {{
  .q-btn.bg-primary {{ color: var(--ca-sobre-primaria) !important; }}
  .text-primary, a, .nicegui-link {{ color: var(--ca-primaria-texto) !important; }}
  .q-header .q-btn {{ color: var(--ca-sobre-primaria) !important; }}
}}
:focus-visible {{ outline: 3px solid var(--ca-foco); outline-offset: 2px; }}
.ca-texto-suave {{ color: var(--ca-texto-suave); }}
.ca-borda {{ border: 1px solid var(--ca-borda); border-radius: {RAIO_CARTAO}; }}
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
