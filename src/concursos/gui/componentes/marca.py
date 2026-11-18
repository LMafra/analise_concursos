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

TAGLINE = 'diagnóstico pós-prova'


def bloco_da_marca(*, com_tagline: bool = True) -> None:
    with ui.row().classes('items-center q-pa-md').style(tema.gap('sm')).mark('marca-app'):
        ui.html(_SVG, sanitize=False)
        with ui.column().style('gap: 0'):
            ui.label(NOME).classes('text-lg font-bold')
            if com_tagline:
                ui.label(TAGLINE).classes('text-caption ca-texto-suave')
