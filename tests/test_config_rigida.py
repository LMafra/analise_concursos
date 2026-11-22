"""Schema rígido de [llm] e candidato.yaml."""

from pathlib import Path

import pytest
import tomli_w
import yaml

from concursos.candidatos import ARQUIVO_CANDIDATO, ler_perfil
from concursos.concurso_config import ConfiguracaoInvalidaError, carregar_concurso
from concursos.llm import ler_configuracao


def test_llm_rejeita_campo_desconhecido(tmp_path: Path) -> None:
    config = tmp_path / 'config.toml'
    config.write_text(
        tomli_w.dumps({'llm': {'provedor': 'openai', 'consentimento': True, 'foo': 1}}),
        encoding='utf-8',
    )
    with pytest.raises(ConfiguracaoInvalidaError, match='campo desconhecido'):
        ler_configuracao(config)


def test_llm_rejeita_provedor_desconhecido(tmp_path: Path) -> None:
    config = tmp_path / 'config.toml'
    config.write_text(tomli_w.dumps({'llm': {'provedor': 'xyz', 'consentimento': True}}), encoding='utf-8')
    with pytest.raises(ConfiguracaoInvalidaError, match='provedor'):
        ler_configuracao(config)


def test_llm_nenhum_desliga(tmp_path: Path) -> None:
    config = tmp_path / 'config.toml'
    config.write_text(tomli_w.dumps({'llm': {'provedor': 'nenhum'}}), encoding='utf-8')
    assert ler_configuracao(config) is None


def test_candidato_rejeita_campo_desconhecido(tmp_path: Path) -> None:
    pasta = tmp_path / 'provas' / 'alfa'
    pasta.mkdir(parents=True)
    (pasta / 'concurso.yaml').write_text(
        yaml.safe_dump(
            {
                'nome': 'alfa',
                'banca': 'fgv',
                'formato': 'multipla_escolha',
                'pontuacao': 'simples',
                'provas': {'unica': {'gabarito': 'g.txt', 'itens': [1, 1]}},
            }
        ),
        encoding='utf-8',
    )
    (pasta / 'g.txt').write_text('1 A\n', encoding='utf-8')
    candidato = pasta / 'candidatos' / 'ana'
    candidato.mkdir(parents=True)
    (candidato / ARQUIVO_CANDIDATO).write_text(
        yaml.safe_dump({'respostas': {'arquivo': 'respostas.txt'}, 'extra': 1}),
        encoding='utf-8',
    )
    (candidato / 'respostas.txt').write_text('1 A\n', encoding='utf-8')
    config = carregar_concurso(pasta)
    with pytest.raises(ConfiguracaoInvalidaError, match='campo desconhecido'):
        ler_perfil(config, 'ana')


def test_candidato_exige_arquivo_ou_folha(tmp_path: Path) -> None:
    pasta = tmp_path / 'provas' / 'alfa'
    pasta.mkdir(parents=True)
    (pasta / 'concurso.yaml').write_text(
        yaml.safe_dump(
            {
                'nome': 'alfa',
                'banca': 'fgv',
                'formato': 'multipla_escolha',
                'pontuacao': 'simples',
                'provas': {'unica': {'gabarito': 'g.txt', 'itens': [1, 1]}},
            }
        ),
        encoding='utf-8',
    )
    (pasta / 'g.txt').write_text('1 A\n', encoding='utf-8')
    candidato = pasta / 'candidatos' / 'ana'
    candidato.mkdir(parents=True)
    (candidato / ARQUIVO_CANDIDATO).write_text(
        yaml.safe_dump({'respostas': {'arquivo': 'a.txt', 'folha': 'f.pdf'}}),
        encoding='utf-8',
    )
    config = carregar_concurso(pasta)
    with pytest.raises(ConfiguracaoInvalidaError, match='arquivo ou folha'):
        ler_perfil(config, 'ana')


def test_llm_rejeita_tipos_invalidos(tmp_path: Path) -> None:
    config = tmp_path / 'config.toml'
    config.write_text(
        tomli_w.dumps({'llm': {'provedor': 'openai', 'consentimento': 'sim'}}),
        encoding='utf-8',
    )
    with pytest.raises(ConfiguracaoInvalidaError, match='consentimento'):
        ler_configuracao(config)
    config.write_text(
        tomli_w.dumps({'llm': {'provedor': 'openai', 'consentimento': True, 'modelo': 1}}),
        encoding='utf-8',
    )
    with pytest.raises(ConfiguracaoInvalidaError, match='modelo'):
        ler_configuracao(config)
    config.write_text(tomli_w.dumps({'llm': {'provedor': 1}}), encoding='utf-8')
    with pytest.raises(ConfiguracaoInvalidaError, match='provedor'):
        ler_configuracao(config)


def _pasta_candidato(tmp_path: Path) -> tuple[Path, object]:
    pasta = tmp_path / 'provas' / 'alfa'
    pasta.mkdir(parents=True)
    (pasta / 'concurso.yaml').write_text(
        yaml.safe_dump(
            {
                'nome': 'alfa',
                'banca': 'fgv',
                'formato': 'multipla_escolha',
                'pontuacao': 'simples',
                'provas': {'unica': {'gabarito': 'g.txt', 'itens': [1, 1]}},
            }
        ),
        encoding='utf-8',
    )
    (pasta / 'g.txt').write_text('1 A\n', encoding='utf-8')
    return pasta, carregar_concurso(pasta)


def test_candidato_rejeita_tipos_invalidos_nas_respostas(tmp_path: Path) -> None:
    pasta, config = _pasta_candidato(tmp_path)
    candidato = pasta / 'candidatos' / 'ana'
    candidato.mkdir(parents=True)
    (candidato / ARQUIVO_CANDIDATO).write_text(
        yaml.safe_dump({'respostas': {'folha': 'f.pdf', 'template': 1}}),
        encoding='utf-8',
    )
    with pytest.raises(ConfiguracaoInvalidaError, match='template'):
        ler_perfil(config, 'ana')
    (candidato / ARQUIVO_CANDIDATO).write_text(
        yaml.safe_dump({'respostas': {'folha': 'f.pdf', 'total_itens': '40'}}),
        encoding='utf-8',
    )
    with pytest.raises(ConfiguracaoInvalidaError, match='total_itens'):
        ler_perfil(config, 'ana')
