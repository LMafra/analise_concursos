import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import tomli_w

from concursos.concurso_config import ConfiguracaoInvalidaError

VARIAVEL_HOME = 'CONCURSO_HOME'
VARIAVEL_PROVAS = 'CONCURSO_PROVAS'
VARIAVEL_ANALISES = 'CONCURSO_ANALISES'
VARIAVEL_CANDIDATO = 'CONCURSO_CANDIDATO'
PASTA_HOME = '.concurso'
PASTA_PROJETO = '.concurso'
PASTA_PROVAS = 'provas'
PASTA_ANALISES = 'analises'
ARQUIVO_CONFIG_PROJETO = 'config.toml'
ARQUIVO_TAXONOMIA = 'taxonomia.yaml'
ARQUIVO_CONFIG_LEGADO = 'config.yaml'


@dataclass(frozen=True)
class Contexto:
    """Todos os caminhos de uma execução; nenhum outro módulo decide onde ler ou gravar."""

    raiz: Path
    home: Path
    projeto: Path
    provas: Path
    analises: Path
    candidato: str | None = None

    @property
    def analises_do_candidato(self) -> Path:
        """`analises/<candidato>/`; sem candidato, a pasta de análises do layout das fases 1 a 3."""
        return self.analises / self.candidato if self.candidato else self.analises

    @property
    def logs(self) -> Path:
        return self.home / 'logs'

    @property
    def config_projeto(self) -> Path:
        return self.projeto / ARQUIVO_CONFIG_PROJETO

    @property
    def config_legado(self) -> Path:
        """O `config.yaml` da raiz, das fases 1 a 3; a migração o converte para o `config.toml`."""
        return self.raiz / ARQUIVO_CONFIG_LEGADO

    @property
    def taxonomia(self) -> Path:
        do_projeto = self.projeto / ARQUIVO_TAXONOMIA
        legada = self.raiz / ARQUIVO_TAXONOMIA
        return legada if not do_projeto.exists() and legada.exists() else do_projeto


def resolver_home(ambiente: Mapping[str, str] | None = None) -> Path:
    ambiente = os.environ if ambiente is None else ambiente
    if valor := ambiente.get(VARIAVEL_HOME):
        return Path(valor).expanduser()
    return Path.home() / PASTA_HOME


def resolver_contexto(
    *,
    cwd: Path | None = None,
    data_dir: Path | None = None,
    provas: Path | None = None,
    analises: Path | None = None,
    candidato: str | None = None,
    ambiente: Mapping[str, str] | None = None,
) -> Contexto:
    """Precedência de cada pasta e do candidato: flag, variável de ambiente, `config.toml` do projeto,
    padrão."""
    ambiente = os.environ if ambiente is None else ambiente
    home = resolver_home(ambiente)
    atual = (cwd or Path.cwd()).resolve()
    raiz = _raiz_do_projeto(atual, home) if data_dir is None else atual
    projeto = _absoluto(data_dir, raiz) if data_dir else raiz / PASTA_PROJETO
    config = ler_toml(projeto / ARQUIVO_CONFIG_PROJETO)
    pastas = config.get('pastas', {})
    ultimo = config.get('candidato', {}).get('ultimo')
    return Contexto(
        candidato=candidato or ambiente.get(VARIAVEL_CANDIDATO) or ultimo or None,
        raiz=raiz,
        home=home,
        projeto=projeto,
        provas=_pasta(provas, ambiente.get(VARIAVEL_PROVAS), pastas.get('provas'), PASTA_PROVAS, raiz),
        analises=_pasta(
            analises, ambiente.get(VARIAVEL_ANALISES), pastas.get('analises'), PASTA_ANALISES, raiz
        ),
    )


def ler_toml(caminho: Path) -> dict:
    if not caminho.exists():
        return {}
    try:
        return tomllib.loads(caminho.read_text(encoding='utf-8'))
    except tomllib.TOMLDecodeError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro


def gravar_no_config_projeto(contexto: Contexto, secao: str, valores: dict) -> None:
    """Atualiza uma seção do `config.toml` do projeto, preservando as demais."""
    dados = ler_toml(contexto.config_projeto)
    dados[secao] = {**dados.get(secao, {}), **valores}
    contexto.config_projeto.parent.mkdir(parents=True, exist_ok=True)
    contexto.config_projeto.write_text(tomli_w.dumps(dados), encoding='utf-8')


def _raiz_do_projeto(atual: Path, home: Path) -> Path:
    """A pasta mais próxima com `.concurso/`, para rodar de uma subpasta (ex.: notebooks/)."""
    for pasta in (atual, *atual.parents):
        marcador = pasta / PASTA_PROJETO
        if marcador.is_dir() and marcador.resolve() != home.resolve():
            return pasta
    return atual


def _pasta(flag: Path | None, variavel: str | None, configurada: str | None, padrao: str, raiz: Path) -> Path:
    for valor in (flag, variavel, configurada):
        if valor:
            return _absoluto(Path(valor), raiz)
    return raiz / padrao


def _absoluto(caminho: Path, raiz: Path) -> Path:
    caminho = caminho.expanduser()
    return caminho if caminho.is_absolute() else raiz / caminho
