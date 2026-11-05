"""Ponto de entrada do executável do PyInstaller; a lógica fica em `concursos.empacotado`, que tem teste."""

import multiprocessing
import sys

if __name__ == '__main__':
    multiprocessing.freeze_support()
    from concursos.empacotado import principal

    sys.exit(principal(sys.argv[1:]))
