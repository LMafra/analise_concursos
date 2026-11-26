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
    RAIO_GRANDE,
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
    fundo='#F8FAFC',
    superficie='#FFFFFF',
    texto='#14282B',
    texto_suave='#475569',
    borda='#E2E8F0',
    primaria='#14282B',
    sobre_primaria='#FFFFFF',
    primaria_texto='#14282B',
    foco='#14282B',
    info_fundo='#E6EFF0',
    info_icone='#14282B',
    info_texto='#14282B',
    sucesso_fundo='#ECFDF5',
    sucesso_icone='#117A4B',
    sucesso_texto='#117A4B',
    erro_fundo='#FEF2EE',
    erro_icone='#9A3412',
    erro_texto='#9A3412',
    alerta_fundo='#FFFBEB',
    alerta_icone='#92400E',
    alerta_texto='#92400E',
)

ESCURO = Paleta(
    fundo='#0D1719',
    superficie='#142225',
    texto='#EAF2F3',
    texto_suave='#A8BDC1',
    borda='#293F44',
    primaria='#4ADE80',
    sobre_primaria='#0D1719',
    primaria_texto='#4ADE80',
    foco='#4ADE80',
    info_fundo='#1F353A',
    info_icone='#A8BDC1',
    info_texto='#EAF2F3',
    sucesso_fundo='#112A20',
    sucesso_icone='#4ADE80',
    sucesso_texto='#4ADE80',
    erro_fundo='#2D1812',
    erro_icone='#F28B66',
    erro_texto='#FBCFC0',
    alerta_fundo='#2A200D',
    alerta_icone='#F59E0B',
    alerta_texto='#FCD34D',
)

# O `ui.colors` grava as cores no style do body, que venceria o `body.body--dark`: a primária vai como
# variável. As notificações do Quasar usam texto branco em positive/negative/info e escuro em warning.
CORES_DO_QUASAR = {
    'primary': 'var(--ca-primaria)',
    'positive': '#0E5A37',
    'negative': '#9A3412',
    'info': '#14282B',
    'warning': '#FCD34D',
    'dark': ESCURO.superficie,
    'dark_page': ESCURO.fundo,
}

RAIO_DIALOGO = '12px'
BARRA_SUPERIOR = '6px'
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
:root {{ {_variaveis(CLARO)} --ca-contorno: #94A3B8; }}
body.body--dark {{ {_variaveis(ESCURO)} --ca-contorno: #557075; }}
body {{ font-family: {FONTE}; background: var(--ca-fundo); color: var(--ca-texto);
  border-top: {BARRA_SUPERIOR} solid var(--ca-primaria); }}
.q-card {{ background: var(--ca-superficie); color: var(--ca-texto); border-radius: {RAIO_GRANDE};
  border: 1px solid var(--ca-borda); box-shadow: none; }}
.nicegui-card {{ padding: {ESPACOS['lg']}; gap: {ESPACOS['md']}; }}
.q-dialog .q-card {{ border-radius: {RAIO_DIALOGO}; box-shadow: {ELEVACAO_2}; }}
.q-header {{ background: var(--ca-superficie); color: var(--ca-texto);
  border-bottom: 1px solid var(--ca-borda); }}
.q-drawer {{ background: var(--ca-superficie); color: var(--ca-texto); }}
.q-notification__actions {{ color: inherit; }}
.q-notification__message {{ white-space: pre-line; }}
@layer overrides {{
  .q-btn.bg-primary {{ color: var(--ca-sobre-primaria) !important; }}
  .text-primary, a, .nicegui-link {{ color: var(--ca-primaria-texto) !important; }}
  .q-header .q-btn {{ color: var(--ca-texto) !important; }}
  .q-btn:not(.q-btn--round):not(.q-btn--dense),
  .q-btn.ca-alvo, button.ca-alvo {{ min-width: {ALVO_MINIMO} !important; min-height: {ALVO_MINIMO} !important; }}
  .q-btn--dense.ca-alvo {{ padding-top: 8px !important; padding-bottom: 8px !important; }}
  .q-btn-group .q-btn {{ min-width: {ALVO_MINIMO} !important; min-height: {ALVO_MINIMO} !important; }}
  .q-uploader .q-btn {{ min-width: {ALVO_MINIMO} !important; min-height: {ALVO_MINIMO} !important; }}
  .q-uploader__header .q-btn {{ color: var(--ca-sobre-primaria) !important; }}
  .ca-soltar .q-uploader__header {{ background: var(--ca-fundo) !important; color: var(--ca-texto) !important; }}
  .ca-soltar .q-uploader__title {{ color: var(--ca-texto) !important; white-space: normal !important;
    text-align: center !important; }}
  .ca-soltar .q-uploader__header .q-btn {{ position: relative !important;
    background: var(--ca-primaria) !important; color: var(--ca-sobre-primaria) !important;
    border-radius: {RAIO_CARTAO} !important; min-width: 12rem !important; padding: 0 !important; }}
  .ca-soltar .q-uploader__header .q-btn__content {{ position: absolute !important; inset: 0 !important;
    display: flex !important; align-items: center !important; justify-content: center !important;
    width: auto !important; }}
  .ca-soltar .q-uploader__header .q-icon {{ display: none !important; }}
  .q-field--dense .q-field__control {{ min-height: {ALVO_MINIMO} !important; }}
  .ca-seletor .q-field__control:before {{ border: 1px solid var(--ca-contorno) !important;
    border-radius: {RAIO_CARTAO} !important; }}
  .ca-seletor:hover .q-field__control:before {{ border-color: var(--ca-texto) !important; }}
  .ca-seletor.q-field--focused .q-field__control:before,
  .ca-seletor.q-field--highlighted .q-field__control:before {{ border-width: 1px !important; }}
  .ca-seletor .q-field__control:after, .ca-seletor .q-field__label,
  .ca-seletor .q-field__bottom {{ display: none !important; }}
  .ca-seletor .q-field__control {{ background: var(--ca-superficie) !important;
    color: var(--ca-texto) !important; border-radius: {RAIO_CARTAO} !important;
    min-height: {ALVO_MINIMO} !important; height: {ALVO_MINIMO} !important;
    padding: 0 {ESPACOS['sm']} 0 {ESPACOS['md']} !important; }}
  .ca-seletor .q-field__native, .ca-seletor .q-field__marginal {{
    min-height: {ALVO_MINIMO} !important; height: {ALVO_MINIMO} !important; }}
  .ca-seletor .q-select__dropdown-icon {{ color: var(--ca-texto-suave) !important; }}
  @media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }}
  }}
}}
:focus-visible {{ outline: 3px solid var(--ca-foco); outline-offset: 2px; }}
.ca-texto-suave {{ color: var(--ca-texto-suave); }}
.ca-titulo-pagina {{ margin: 0; font-size: clamp(1.65rem, 1.35rem + 1vw, 2.125rem);
  font-weight: 800; letter-spacing: -0.015em; line-height: 1.1; color: var(--ca-texto); }}
.nicegui-row.ca-cabecalho {{ display: flex; flex-wrap: wrap; align-items: flex-end;
  justify-content: space-between; width: 100%; gap: {ESPACOS['md']}; }}
.nicegui-column.ca-filtros {{ align-items: stretch; flex: 0 0 auto; width: max-content;
  min-width: min(100%, 260px); max-width: 100%; margin-left: auto; gap: {ESPACOS['sm']}; }}
.nicegui-column.ca-campo {{ align-items: stretch; width: 100%; gap: {ESPACOS['xs']}; }}
.ca-rotulo-campo {{ display: block; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.01em;
  line-height: 1.3; color: var(--ca-texto-suave); }}
.ca-seletor {{ width: 100%; cursor: pointer; }}
.ca-seletor-lista {{ background: var(--ca-superficie); color: var(--ca-texto);
  border: 1px solid var(--ca-contorno); border-radius: {RAIO_CARTAO}; }}
.ca-avatar {{ display: inline-flex; align-items: center; justify-content: center;
  width: 2.5rem; height: 2.5rem; border-radius: 9999px; flex-shrink: 0;
  background: var(--ca-info-fundo); color: var(--ca-primaria-texto); font-weight: 700;
  font-size: 0.875rem; letter-spacing: 0.02em; }}
.ca-grade-cartoes {{ display: grid; width: 100%;
  grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr)); gap: {ESPACOS['md']}; }}
.ca-radio-cartoes {{ display: grid; width: 100%;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: {ESPACOS['sm']}; }}
.ca-radio-cartao {{ min-height: 48px; border: 1px solid var(--ca-borda); border-radius: {RAIO_CARTAO};
  background: var(--ca-superficie); color: var(--ca-texto); font-weight: 600; }}
.ca-radio-cartao[aria-pressed="true"] {{ border-color: var(--ca-primaria);
  background: var(--ca-info-fundo); color: var(--ca-primaria-texto); }}
.ca-barra-salvar {{ position: sticky; bottom: 0; z-index: 20; display: flex; flex-wrap: wrap;
  justify-content: space-between; align-items: center; gap: {ESPACOS['md']};
  margin-top: {ESPACOS['lg']}; padding: {ESPACOS['md']} {ESPACOS['lg']};
  background: var(--ca-superficie); border: 1px solid var(--ca-borda); border-radius: {RAIO_GRANDE};
  box-shadow: {ELEVACAO_1}; }}
.ca-busca {{ display: flex; flex-direction: column; gap: {ESPACOS['xs']}; min-width: min(100%, 16rem); }}
.ca-borda {{ border: 1px solid var(--ca-borda); border-radius: {RAIO_CARTAO}; }}
.q-card.ca-borda {{ border-radius: {RAIO_GRANDE}; }}
.ca-alvo {{ min-width: {ALVO_MINIMO}; min-height: {ALVO_MINIMO}; }}
.ca-grade-respostas {{ display: grid; grid-template-columns: 1fr; gap: {ESPACOS['sm']}; }}
@media (min-width: 768px) {{ .ca-grade-respostas {{ grid-template-columns: 1fr 1fr; }} }}
@media (min-width: 1024px) {{ .ca-grade-respostas {{ grid-template-columns: 1fr 1fr 1fr; }} }}
{_tons()}
.ca-aviso {{ background: var(--ca-tom-fundo); color: var(--ca-texto); border-left: 4px solid var(--ca-tom-icone);
  border-radius: {RAIO_CARTAO}; padding: {ESPACOS['md']}; box-shadow: none; }}
.ca-icone-tom {{ color: var(--ca-tom-icone); }}
.ca-situacao {{ color: var(--ca-tom-texto); font-weight: 500; }}
.ca-etapa {{ color: var(--ca-texto-suave); }}
.ca-etapa-atual {{ color: var(--ca-primaria-texto); font-weight: 600; }}
.ca-etapa-feita {{ color: var(--ca-sucesso-texto); }}
.nicegui-log .q-scrollarea__content {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
.ca-pilula {{ display: inline-flex; align-items: center; gap: {ESPACOS['xs']};
  border: 1px solid var(--ca-borda); border-radius: 9999px; padding: {ESPACOS['xs']} {ESPACOS['sm']};
  color: var(--ca-texto-suave); background: var(--ca-superficie); }}
.ca-pessoa {{ border-top: 1px solid var(--ca-borda); padding: {ESPACOS['md']}; }}
.q-drawer .q-btn[aria-current="page"] {{ background: var(--ca-info-fundo); font-weight: 600; }}
.ca-hero {{ background: var(--ca-superficie); border: 1px solid var(--ca-borda);
  border-left: {BARRA_SUPERIOR} solid var(--ca-tom-icone); border-radius: {RAIO_GRANDE};
  padding: {ESPACOS['lg']}; box-shadow: {ELEVACAO_1}; }}
.ca-metrica {{ border-left: 4px solid var(--ca-tom-icone); box-shadow: none;
  padding: {ESPACOS['md']} {ESPACOS['lg']}; }}
.ca-grade-acoes {{ display: grid; width: 100%; align-items: stretch;
  grid-template-columns: repeat(auto-fit, minmax(min(280px, 100%), 1fr)); gap: {ESPACOS['md']}; }}
.ca-acao {{ height: 100%; justify-content: space-between; align-items: stretch;
  border-left: 4px solid var(--ca-alerta-icone); }}
.ca-acao .ca-situacao {{ width: fit-content; background: var(--ca-tom-fundo);
  border: 1px solid var(--ca-tom-icone); border-radius: 9999px;
  padding: {ESPACOS['xs']} {ESPACOS['md']}; font-size: 0.75rem; font-weight: 700; line-height: 1.3; }}
.ca-acao-titulo {{ font-size: 1.0625rem; font-weight: 700; line-height: 1.3; }}
.ca-acao-nota {{ font-size: 0.9rem; color: var(--ca-texto-suave); }}
.ca-botoes {{ display: flex; flex-wrap: wrap; align-items: center; gap: {ESPACOS['sm']}; }}
.nicegui-column.ca-lista-livros {{ align-items: stretch; width: 100%; gap: {ESPACOS['sm']}; }}
.ca-linha-livro {{ display: flex; flex-direction: column; align-items: stretch; gap: {ESPACOS['sm']};
  width: 100%; box-sizing: border-box; background: var(--ca-superficie);
  border: 1px solid var(--ca-borda); border-left: 4px solid var(--ca-tom-icone);
  border-radius: {RAIO_GRANDE}; padding: {ESPACOS['md']} {ESPACOS['lg']}; }}
.ca-linha-livro-corpo {{ display: flex; flex-wrap: wrap; justify-content: space-between;
  align-items: center; gap: {ESPACOS['md']}; }}
.ca-linha-livro .ca-situacao {{ width: fit-content; background: var(--ca-tom-fundo);
  border: 1px solid var(--ca-tom-icone); border-radius: 9999px;
  padding: {ESPACOS['xs']} {ESPACOS['md']}; font-size: 0.75rem; font-weight: 700; line-height: 1.3; }}
.ca-acrescentar-livro {{ width: 100%; border-top: 1px solid var(--ca-borda);
  padding-top: {ESPACOS['lg']}; }}
.ca-grade-form {{ display: grid; width: 100%; align-items: end;
  grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr)); gap: {ESPACOS['md']}; }}
.ca-soltar.q-uploader {{ width: 100%; box-shadow: none; background: var(--ca-fundo);
  border: 1px dashed var(--ca-borda); border-radius: {RAIO_GRANDE}; }}
.ca-soltar .q-uploader__header {{ padding: {ESPACOS['lg']}; }}
.ca-soltar .q-uploader__header-content > .flex {{ flex-direction: column; align-items: center;
  justify-content: center; width: 100%; margin: 0; }}
.ca-soltar .q-uploader__header-content > .flex > * {{ margin-left: 0; margin-right: 0; }}
.ca-soltar .q-uploader__header .col {{ flex: 0 0 auto; width: 100%; max-width: 100%; align-items: center; }}
.ca-soltar .q-uploader__header .q-btn {{ margin-top: {ESPACOS['md']}; }}
.ca-soltar .q-uploader__list:empty {{ display: none; }}
.ca-soltar .q-uploader__subtitle {{ display: none; }}
.ca-soltar .q-uploader__header .q-btn__content::after {{ content: 'Adicionar livro';
  position: static; display: block; width: auto; margin: 0; pointer-events: none;
  font-size: 0.875rem; font-weight: 600; line-height: 1.2; text-align: center; }}
.nicegui-column.ca-lista-provas {{ display: grid; width: 100%;
  grid-template-columns: minmax(0, 1.5fr) auto auto; }}
.ca-linha-prova {{ display: grid; grid-template-columns: minmax(0, 1.5fr) auto auto;
  width: 100%; box-sizing: border-box; gap: {ESPACOS['md']}; align-items: center;
  background: var(--ca-superficie); border: 1px solid var(--ca-borda); border-radius: {RAIO_GRANDE};
  padding: {ESPACOS['md']} {ESPACOS['lg']}; }}
.ca-lista-provas > .ca-linha-prova {{ grid-column: 1 / -1; grid-template-columns: subgrid; }}
.ca-grafico-caixa {{ background: var(--ca-superficie); border: 1px solid var(--ca-borda);
  border-radius: {RAIO_GRANDE}; padding: {ESPACOS['lg']}; }}
.ca-grafico-svg {{ width: 100%; height: auto; display: block; overflow: visible; }}
@media (max-width: 860px) {{
  .nicegui-column.ca-lista-provas, .ca-linha-prova {{ grid-template-columns: 1fr; }}
}}
"""


def aplicar_tema(modo: TemaGui) -> ui.dark_mode:
    ui.colors(**CORES_DO_QUASAR)
    ui.add_css(CSS)
    return ui.dark_mode(VALOR_DO_MODO[modo])
