import hashlib
import logging
import shutil
import tomllib
from pathlib import Path

import pytest
import yaml
from conftest import analisar, criar_concurso

from concursos.cli import main
from concursos.config.contexto import resolver_contexto
from concursos.migracao import MigracaoError, candidato_padrao, executar_migracao, planejar_migracao

CONCURSO = {
    'nome': 'alfa',
    'banca': 'fgv',
    'formato': 'multipla_escolha',
    'pontuacao': 'simples',
    'provas': {'unica': {'gabarito': 'gabarito.txt', 'itens': [1, 4]}},
    'respostas': {'arquivo': 'respostas.txt'},
}
ARQUIVOS = {
    'gabarito.txt': '1 A\n2 B\n3 C\n4 D\n',
    'respostas.txt': '1 A\n2 B\n3 D\n4 D\n',
}
CONFIG_LEGADA = 'limiar_topico_baixo: 0.4\n'
TAXONOMIA_LEGADA = 'Língua Portuguesa:\n  bloco: geral\n'


@pytest.fixture
def legado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um projeto das fases 1 a 3 já analisado pelo comando antigo."""
    raiz = tmp_path / 'projeto'
    raiz.mkdir()
    monkeypatch.chdir(raiz)
    criar_concurso(raiz / 'provas', 'alfa', CONCURSO, ARQUIVOS)
    (raiz / 'config.yaml').write_text(CONFIG_LEGADA, encoding='utf-8')
    (raiz / 'taxonomia.yaml').write_text(TAXONOMIA_LEGADA, encoding='utf-8')
    assert analisar(Path('provas'), Path('analises')) == 0
    return raiz


def hashes(raiz: Path) -> dict[str, str]:
    return {
        p.relative_to(raiz).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(raiz.rglob('*'))
        if p.is_file() and p.name != '.manifesto.json'
    }


def config_toml(raiz: Path) -> dict:
    return tomllib.loads((raiz / '.concurso' / 'config.toml').read_text(encoding='utf-8'))


def backups(home: Path) -> list[Path]:
    return sorted(home.glob('backup-*')) if home.is_dir() else []


def test_arvore_legada_migra_preservando_o_hash_de_cada_saida(legado):
    antes = hashes(legado / 'analises')
    mtime = (legado / 'analises' / 'alfa' / 'relatorio.md').stat().st_mtime_ns
    slug = candidato_padrao()

    assert main([]) == 0

    depois = hashes(legado / 'analises' / slug)
    assert {chave: depois.get(chave) for chave in antes} == antes
    assert (legado / 'analises' / slug / 'alfa' / 'relatorio.md').stat().st_mtime_ns == mtime
    assert not (legado / 'analises' / 'alfa').exists()
    assert not (legado / 'analises' / 'consolidado').exists()


def test_respostas_e_identificador_vao_para_o_candidato(legado):
    concurso = legado / 'provas' / 'alfa' / 'concurso.yaml'
    dados = yaml.safe_load(concurso.read_text(encoding='utf-8'))
    dados['resultado_oficial'] = {'arquivo': 'resultado.txt', 'identificador': 12345678}
    concurso.write_text(yaml.safe_dump(dados), encoding='utf-8')
    slug = candidato_padrao()
    contexto = resolver_contexto(candidato=slug)

    executar_migracao(planejar_migracao(contexto), contexto)

    perfil = yaml.safe_load(
        (legado / 'provas' / 'alfa' / 'candidatos' / slug / 'candidato.yaml').read_text(encoding='utf-8')
    )
    assert perfil['respostas'] == {'arquivo': '../../respostas.txt'}
    assert perfil['resultado_oficial'] == {'identificador': '12345678'}
    restante = yaml.safe_load(concurso.read_text(encoding='utf-8'))
    assert 'respostas' not in restante
    assert restante['resultado_oficial'] == {'arquivo': 'resultado.txt'}
    assert (legado / 'provas' / 'alfa' / 'respostas.txt').exists()


def test_configuracao_e_taxonomia_vao_para_o_projeto(legado):
    assert main([]) == 0

    config = config_toml(legado)
    assert config['analise'] == {'limiar_topico_baixo': 0.4}
    assert config['candidato']['ultimo'] == candidato_padrao()
    assert config['migracao']['versao'] == 4
    taxonomia = legado / '.concurso' / 'taxonomia.yaml'
    assert taxonomia.read_text(encoding='utf-8') == TAXONOMIA_LEGADA
    assert not (legado / 'config.yaml').exists()
    assert not (legado / 'taxonomia.yaml').exists()


def test_backup_tem_tudo_o_que_mudou_com_o_mesmo_hash(legado, home_isolada):
    originais = {
        'raiz/config.yaml': legado / 'config.yaml',
        'raiz/taxonomia.yaml': legado / 'taxonomia.yaml',
        'provas/alfa/concurso.yaml': legado / 'provas' / 'alfa' / 'concurso.yaml',
        'analises/alfa/relatorio.md': legado / 'analises' / 'alfa' / 'relatorio.md',
    }
    esperado = {chave: hashlib.sha256(p.read_bytes()).hexdigest() for chave, p in originais.items()}

    assert main([]) == 0

    (backup,) = backups(home_isolada)
    copiado = {chave: hashlib.sha256((backup / chave).read_bytes()).hexdigest() for chave in esperado}
    assert copiado == esperado
    assert (backup / 'hashes.json').exists()


def test_backup_corrompido_aborta_sem_mudar_nada(legado, monkeypatch, capsys):
    antes = hashes(legado)

    def copiar_errado(origem: Path, destino: Path) -> None:
        shutil.copy2(origem, destino)
        destino.write_bytes(b'corrompido')

    monkeypatch.setattr('concursos.migracao._copiar', copiar_errado)

    assert main([]) != 0

    assert hashes(legado) == antes
    assert 'backup' in capsys.readouterr().err


def test_segunda_execucao_nao_migra_de_novo(legado, home_isolada):
    assert main([]) == 0
    config = config_toml(legado)

    assert main([]) == 0

    assert len(backups(home_isolada)) == 1
    assert config_toml(legado) == config


def test_dry_run_lista_a_migracao_e_nao_grava_nada(legado, home_isolada, capsys):
    antes = hashes(legado)

    assert main(['--dry-run']) == 0

    saida = capsys.readouterr().out
    assert 'migraria' in saida
    assert 'analises/alfa' in saida and 'config.yaml' in saida
    assert hashes(legado) == antes
    assert not (legado / '.concurso').exists()
    assert backups(home_isolada) == []


def test_pasta_legada_copiada_depois_e_migrada_com_aviso(legado, caplog):
    assert main([]) == 0
    criar_concurso(legado / 'provas', 'beta', {**CONCURSO, 'nome': 'beta'}, ARQUIVOS)
    slug = candidato_padrao()

    with caplog.at_level(logging.WARNING):
        assert main([]) == 0

    assert any('beta' in r.getMessage() and 'migrad' in r.getMessage() for r in caplog.records)
    assert (legado / 'provas' / 'beta' / 'candidatos' / slug / 'candidato.yaml').exists()
    assert (legado / 'analises' / slug / 'beta' / 'relatorio.md').exists()


def test_candidato_escolhido_vira_o_dono_dos_dados_migrados(legado):
    assert main(['--candidate', 'Ana Lima']) == 0

    assert (legado / 'analises' / 'ana_lima' / 'alfa' / 'relatorio.md').exists()
    assert (legado / 'provas' / 'alfa' / 'candidatos' / 'ana_lima' / 'candidato.yaml').exists()


def test_reprocessar_depois_da_migracao_da_as_mesmas_saidas(legado):
    antes = hashes(legado / 'analises')

    assert main([]) == 0
    assert main(['--force']) == 0

    depois = hashes(legado / 'analises' / candidato_padrao())
    assert {chave: depois.get(chave) for chave in antes} == antes


def test_saida_ja_existente_no_destino_nao_e_sobrescrita(legado):
    destino = legado / 'analises' / candidato_padrao() / 'alfa'
    destino.mkdir(parents=True)
    (destino / 'relatorio.md').write_text('outro', encoding='utf-8')
    contexto = resolver_contexto(candidato=candidato_padrao())

    with pytest.raises(MigracaoError, match='já existe'):
        executar_migracao(planejar_migracao(contexto), contexto)

    assert (destino / 'relatorio.md').read_text(encoding='utf-8') == 'outro'
    assert (legado / 'analises' / 'alfa').exists()
