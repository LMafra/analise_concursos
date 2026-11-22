"""Migração única de `.concurso` para `.gabarito-vivo`."""

from pathlib import Path

from concursos.config.contexto import PASTA_ANTIGA, PASTA_HOME, migrar_pasta_antiga, resolver_home


def test_migrar_pasta_antiga_renomeia_quando_nova_ausente(tmp_path: Path) -> None:
    antiga = tmp_path / PASTA_ANTIGA
    antiga.mkdir()
    (antiga / 'config.toml').write_text('[analise]\n', encoding='utf-8')
    nova = tmp_path / PASTA_HOME
    resultado = migrar_pasta_antiga(nova)
    assert resultado == nova
    assert nova.is_dir()
    assert not antiga.exists()
    assert (nova / 'config.toml').exists()


def test_migrar_pasta_antiga_nao_toca_quando_nova_existe(tmp_path: Path) -> None:
    antiga = tmp_path / PASTA_ANTIGA
    antiga.mkdir()
    (antiga / 'velho.txt').write_text('a', encoding='utf-8')
    nova = tmp_path / PASTA_HOME
    nova.mkdir()
    (nova / 'novo.txt').write_text('b', encoding='utf-8')
    resultado = migrar_pasta_antiga(nova)
    assert resultado == nova
    assert antiga.exists()
    assert (nova / 'novo.txt').exists()


def test_resolver_home_migra_pasta_do_usuario(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    antiga = tmp_path / PASTA_ANTIGA
    antiga.mkdir()
    home = resolver_home({})
    assert home == tmp_path / PASTA_HOME
    assert home.is_dir()
    assert not antiga.exists()
