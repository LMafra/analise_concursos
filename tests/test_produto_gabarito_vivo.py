"""Identidade Gabarito Vivo: comando e superfície de produto."""

from concursos import produto
from concursos.atualizador import PADRAO_ARQUIVO
from concursos.gui import tema


def test_nome_e_comando_principais() -> None:
    assert produto.NOME == 'Gabarito Vivo'
    assert produto.COMANDO == 'gabarito-vivo'
    assert produto.PACOTE == 'gabarito-vivo'


def test_artefatos_aceitam_prefixo_novo() -> None:
    assert PADRAO_ARQUIVO.match('gabarito-vivo-0.7.0-linux-x86_64.AppImage')
    assert PADRAO_ARQUIVO.match('gabarito-vivo-0.7.0-windows-x64-setup.exe')
    assert not PADRAO_ARQUIVO.match('outro-app-0.7.0-linux-x86_64.AppImage')
    assert not PADRAO_ARQUIVO.match('concurso-analise-0.7.0-linux-x86_64.AppImage')


def test_tokens_sem_azul_material_padrao() -> None:
    assert '#1976D2' not in tema.CSS.upper()
    assert '--ca-primaria: #14282B' in tema.CSS
    assert 'prefers-reduced-motion' in tema.CSS
    assert 'min-width: 44px' in tema.CSS or 'min-width:44px' in tema.CSS.replace(' ', '')


def test_cli_tem_entry_points_no_pyproject() -> None:
    from pathlib import Path

    texto = Path('pyproject.toml').read_text(encoding='utf-8')
    assert 'gabarito-vivo = "concursos.cli:executar"' in texto
    assert 'gabarito-vivo-gui = "concursos.cli:executar_gui"' in texto
    assert 'concurso-analise' not in texto
    assert 'executar_legado' not in texto


def test_relatorio_root_usa_tokens() -> None:
    from concursos.design_tokens import css_root_do_relatorio

    css = css_root_do_relatorio()
    assert css.startswith(':root {')
    assert '--color-primary: #14282B' in css
    assert '--color-bg-base: #FAFAFA' in css
