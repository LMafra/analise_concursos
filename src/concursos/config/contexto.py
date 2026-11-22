import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import tomli_w

from concursos.concurso_config import ConfiguracaoInvalidaError

VARIAVEL_HOME = 'GABARITO_VIVO_HOME'
VARIAVEL_PROVAS = 'GABARITO_VIVO_PROVAS'
VARIAVEL_ANALISES = 'GABARITO_VIVO_ANALISES'
VARIAVEL_CANDIDATO = 'GABARITO_VIVO_CANDIDATO'
PASTA_HOME = '.gabarito-vivo'
PASTA_PROJETO = '.gabarito-vivo'
PASTA_ANTIGA = '.concurso'
PASTA_PROVAS = 'provas'
PASTA_ANALISES = 'analises'
ARQUIVO_CONFIG_PROJETO = 'config.toml'
ARQUIVO_CONFIG_GLOBAL = 'config.toml'
ARQUIVO_TAXONOMIA = 'taxonomia.yaml'
ARQUIVO_DICIONARIO = 'taxonomia_topicos.yaml'
SECAO_DICIONARIO = 'dicionario'


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
    def config_global(self) -> Path:
        return self.home / ARQUIVO_CONFIG_GLOBAL

    @property
    def config_projeto(self) -> Path:
        return self.projeto / ARQUIVO_CONFIG_PROJETO

    @property
    def taxonomia(self) -> Path:
        return self.projeto / ARQUIVO_TAXONOMIA

    @property
    def dicionario(self) -> Path:
        return self.projeto / ARQUIVO_DICIONARIO

    @property
    def dicionario_ligado(self) -> bool:
        """O dicionário de temas existe e não foi desligado (`[dicionario] usar = false`)."""
        if not self.dicionario.exists():
            return False
        return ler_toml(self.config_projeto).get(SECAO_DICIONARIO, {}).get('usar', True) is not False

    @property
    def extras_do_manifesto(self) -> dict[str, Path]:
        """Os arquivos de fora da pasta do concurso que mudam a análise e por isso entram no manifesto; o
        dicionário só quando ligado, para que ligar e desligar refaça a análise."""
        extras = {f'{PASTA_PROJETO}/taxonomia.yaml': self.taxonomia}
        if self.dicionario_ligado:
            extras[f'{PASTA_PROJETO}/{ARQUIVO_DICIONARIO}'] = self.dicionario
        return extras


def migrar_pasta_antiga(caminho_novo: Path) -> Path:
    """Se só existir `.gabarito-vivo` no mesmo pai, renomeia para `.gabarito-vivo`. Não lê as duas."""
    if caminho_novo.exists():
        return caminho_novo
    antiga = caminho_novo.parent / PASTA_ANTIGA
    if antiga.is_dir():
        antiga.rename(caminho_novo)
    return caminho_novo


def resolver_home(ambiente: Mapping[str, str] | None = None) -> Path:
    ambiente = os.environ if ambiente is None else ambiente
    if valor := ambiente.get(VARIAVEL_HOME):
        return Path(valor).expanduser()
    return migrar_pasta_antiga(Path.home() / PASTA_HOME)


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
    if data_dir:
        projeto = migrar_pasta_antiga(_absoluto(data_dir, raiz))
    else:
        projeto = migrar_pasta_antiga(raiz / PASTA_PROJETO)
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
    gravar_secao(contexto.config_projeto, secao, valores)


def gravar_secao(caminho: Path, secao: str, valores: dict) -> None:
    dados = ler_toml(caminho)
    dados[secao] = {**dados.get(secao, {}), **valores}
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(tomli_w.dumps(dados), encoding='utf-8')


def _raiz_do_projeto(atual: Path, home: Path) -> Path:
    """A pasta mais próxima com `.gabarito-vivo/` (ou `.gabarito-vivo/` ainda não migrada)."""
    for pasta in (atual, *atual.parents):
        for nome in (PASTA_PROJETO, PASTA_ANTIGA):
            marcador = pasta / nome
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
