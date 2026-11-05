from collections.abc import AsyncGenerator
from dataclasses import fields
from pathlib import Path

import pytest
from nicegui.testing.general_fixtures import pytest_configure  # noqa: F401
from nicegui.testing.user import User
from nicegui.testing.user_simulation import user_simulation

from concursos.gui.app import raiz
from concursos.gui.estado import ESTADO, Estado


@pytest.fixture(autouse=True)
def estado_limpo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O estado da janela é do processo; cada teste começa sem projeto, numa pasta temporária."""
    monkeypatch.chdir(tmp_path)
    for campo in fields(Estado):
        setattr(ESTADO, campo.name, campo.default)


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation(raiz) as usuario:
        yield usuario


@pytest.fixture
def projeto(tmp_path: Path) -> Path:
    pasta = tmp_path / 'meus concursos'
    ESTADO.abrir_projeto(pasta)
    return pasta
