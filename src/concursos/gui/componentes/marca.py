"""Marca gráfica local (sem rede) para o drawer e o chrome."""

from nicegui import ui

from concursos.gui import tema
from concursos.produto import NOME

# Folha de respostas + check; cores via tokens da GUI.
_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="40" height="40" aria-hidden="true">
  <rect x="4" y="4" width="56" height="56" rx="12" fill="var(--ca-primaria)"/>
  <circle cx="20" cy="22" r="4" fill="none" stroke="var(--ca-sobre-primaria)" stroke-width="3"/>
  <circle cx="32" cy="22" r="4" fill="none" stroke="var(--ca-sobre-primaria)" stroke-width="3"/>
  <circle cx="44" cy="22" r="4" fill="var(--ca-sobre-primaria)"/>
  <circle cx="20" cy="34" r="4" fill="none" stroke="var(--ca-sobre-primaria)" stroke-width="3"/>
  <circle cx="32" cy="34" r="4" fill="none" stroke="var(--ca-sobre-primaria)" stroke-width="3"/>
  <circle cx="44" cy="34" r="4" fill="none" stroke="var(--ca-sobre-primaria)" stroke-width="3"/>
  <path d="M18 48 L28 56 L48 32" fill="none" stroke="var(--ca-foco)" stroke-width="5"
    stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""

TAGLINE = 'Acompanhamento calmo dos seus concursos'


def cartao_da_pessoa() -> None:
    """Nome e cargo digitados pela pessoa. Sem candidato, o cartão não aparece."""
    from concursos.candidatos import cargo_almejado, ler_perfil_global
    from concursos.config.contexto import resolver_home
    from concursos.gui.estado import ESTADO

    if ESTADO.projeto is None:
        return
    try:
        candidato = ESTADO.candidato or ESTADO.contexto().candidato
    except Exception:  # noqa: BLE001
        return
    if not candidato:
        return
    home = resolver_home()
    perfil = ler_perfil_global(home, candidato)
    nome = str(perfil.get('nome') or candidato)
    cargo = cargo_almejado(home, candidato)
    with ui.row().classes('w-full items-center ca-pessoa').style(tema.gap('sm')).mark('cartao-pessoa'):
        ui.label(_iniciais(nome)).classes('ca-avatar').props('aria-hidden=true')
        with ui.column().style(tema.gap('xs')):
            ui.label(nome).classes('font-bold')
            if cargo:
                ui.label(cargo).classes('text-sm ca-texto-suave')
            else:
                ui.button(
                    'Dizer o cargo que você busca',
                    on_click=lambda: ui.navigate.to('/configuracoes'),
                ).props('flat dense no-caps').classes('ca-alvo')


def _iniciais(nome: str) -> str:
    partes = [parte for parte in nome.split() if parte]
    if not partes:
        return '?'
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def bloco_da_marca(*, com_tagline: bool = True) -> None:
    with ui.row().classes('items-center q-pa-md').style(tema.gap('sm')).mark('marca-app'):
        ui.html(_SVG, sanitize=False)
        with ui.column().style('gap: 0'):
            ui.label(NOME).classes('text-lg font-bold')
            if com_tagline:
                ui.label(TAGLINE).classes('text-caption ca-texto-suave')
