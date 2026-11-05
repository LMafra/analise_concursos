"""Interface gráfica local (NiceGUI): só monta telas e chama `concursos.aplicacao`."""

import os

from concursos.config.contexto import resolver_home

# A NiceGUI fixa a pasta de armazenamento ao ser importada; sem isso, ela cria `.nicegui/` na pasta do projeto.
os.environ.setdefault('NICEGUI_STORAGE_PATH', str(resolver_home() / 'gui'))
