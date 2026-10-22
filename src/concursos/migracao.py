"""Migração das fases 1 a 3 para o layout multi-candidato, com backup verificado na pasta global."""

import getpass
import json
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from concursos import manifesto
from concursos.candidatos import (
    ARQUIVO_CANDIDATO,
    PASTA_CANDIDATOS,
    gravar_perfil_global,
    pasta_do_candidato,
    slug,
)
from concursos.concurso_config import ConfiguracaoInvalidaError
from concursos.config.contexto import ARQUIVO_TAXONOMIA, Contexto, gravar_no_config_projeto, ler_toml
from concursos.configuracao import carregar_configuracao_global

logger = logging.getLogger(__name__)

VERSAO_MIGRACAO = 4
ARQUIVO_CONFIG_LEGADO = 'config.yaml'
ARQUIVO_HASHES = 'hashes.json'
CANDIDATO_RESERVA = 'eu'
_MARCADORES_DE_SAIDA = (
    'correcao.json',
    manifesto.ARQUIVO_MANIFESTO,
    'relatorio.md',
    'comparativo_concursos.md',
    'desempenho_geral.csv',
)
_CAMPOS_DE_ARQUIVO = ('arquivo', 'folha')
_ACIMA_DO_CANDIDATO = '../../'


class MigracaoError(Exception):
    """A migração não começou ou parou; a mensagem diz o que ficou como estava."""


@dataclass(frozen=True)
class Movimento:
    origem: Path
    destino: Path
    concurso: Path | None


@dataclass(frozen=True)
class Extracao:
    pasta_concurso: Path
    perfil: dict
    concurso_yaml: str


@dataclass(frozen=True)
class Migracao:
    candidato: str
    movimentos: tuple[Movimento, ...] = ()
    extracoes: tuple[Extracao, ...] = ()
    config_legada: Path | None = None
    taxonomia_legada: Path | None = None
    ja_migrado: bool = False

    @property
    def vazia(self) -> bool:
        return not (self.movimentos or self.extracoes or self.config_legada or self.taxonomia_legada)

    def operacoes(self, contexto: Contexto) -> list[str]:
        def curto(caminho: Path) -> str:
            return str(
                caminho.relative_to(contexto.raiz) if caminho.is_relative_to(contexto.raiz) else caminho
            )

        linhas = [f'migraria {curto(m.origem)} para {curto(m.destino)}' for m in self.movimentos]
        linhas += [
            f'migraria as respostas de {curto(e.pasta_concurso / "concurso.yaml")} para '
            f'{curto(pasta_do_candidato(e.pasta_concurso, self.candidato) / ARQUIVO_CANDIDATO)}'
            for e in self.extracoes
        ]
        if self.config_legada:
            linhas.append(f'migraria {curto(self.config_legada)} para {curto(contexto.config_projeto)}')
        if self.taxonomia_legada:
            linhas.append(
                f'migraria {curto(self.taxonomia_legada)} para {curto(contexto.projeto / ARQUIVO_TAXONOMIA)}'
            )
        linhas.append(f'migraria com backup em {contexto.home / "backup-<data>"}')
        return linhas


def candidato_padrao() -> str:
    """O login do sistema, para a primeira migração não precisar de pergunta."""
    try:
        return slug(getpass.getuser())
    except (OSError, KeyError, ConfiguracaoInvalidaError):
        return CANDIDATO_RESERVA


def planejar_migracao(contexto: Contexto) -> Migracao:
    """O que está no formato das fases 1 a 3; nada é gravado."""
    registro = ler_toml(contexto.config_projeto).get('migracao', {})
    candidato = contexto.candidato or registro.get('candidato') or candidato_padrao()
    taxonomia = contexto.raiz / ARQUIVO_TAXONOMIA
    if taxonomia.exists() and (contexto.projeto / ARQUIVO_TAXONOMIA).exists():
        raise MigracaoError(
            f'há duas taxonomias, {taxonomia} e {contexto.projeto / ARQUIVO_TAXONOMIA}; '
            'junte-as na segunda e apague a primeira'
        )
    config = contexto.raiz / ARQUIVO_CONFIG_LEGADO
    if config.exists():
        carregar_configuracao_global(config)
    return Migracao(
        candidato=candidato,
        movimentos=tuple(_movimentos(contexto, candidato)),
        extracoes=tuple(_extracoes(contexto.provas)),
        config_legada=config if config.exists() else None,
        taxonomia_legada=taxonomia if taxonomia.exists() else None,
        ja_migrado=bool(registro),
    )


def executar_migracao(migracao: Migracao, contexto: Contexto) -> Path | None:
    """Backup verificado antes de qualquer mudança; devolve a pasta do backup."""
    if migracao.vazia:
        return None
    backup = _fazer_backup(migracao, contexto)
    atualizados = [
        m
        for m in migracao.movimentos
        if m.concurso is not None and manifesto.atualizado(m.concurso, m.origem)
    ]
    try:
        _aplicar(migracao, contexto)
        gravar_no_config_projeto(
            contexto,
            'migracao',
            {
                'versao': VERSAO_MIGRACAO,
                'candidato': migracao.candidato,
                'backup': str(backup),
                'data': datetime.now().isoformat(timespec='seconds'),
            },
        )
        gravar_no_config_projeto(contexto, 'candidato', {'ultimo': migracao.candidato})
        gravar_perfil_global(contexto.home, migracao.candidato)
        for movimento in atualizados:
            manifesto.gravar(movimento.concurso, movimento.destino, migracao.candidato)
    except OSError as erro:
        raise MigracaoError(f'migração interrompida ({erro}); o backup completo está em {backup}') from erro
    _avisar(migracao, backup)
    return backup


def _movimentos(contexto: Contexto, candidato: str) -> list[Movimento]:
    if not contexto.analises.is_dir():
        return []
    movimentos = []
    for origem in sorted(p for p in contexto.analises.iterdir() if p.is_dir()):
        if not any((origem / marcador).exists() for marcador in _MARCADORES_DE_SAIDA):
            continue
        destino = contexto.analises / candidato / origem.name
        if destino.exists():
            raise MigracaoError(f'{destino} já existe; mova ou apague essa pasta antes de migrar {origem}')
        concurso = contexto.provas / origem.name
        movimentos.append(
            Movimento(origem, destino, concurso if (concurso / 'concurso.yaml').exists() else None)
        )
    return movimentos


def _extracoes(raiz_provas: Path) -> list[Extracao]:
    if not raiz_provas.is_dir():
        return []
    extracoes = []
    for pasta in sorted(p for p in raiz_provas.iterdir() if p.is_dir()):
        caminho = pasta / 'concurso.yaml'
        if not caminho.exists() or (pasta / PASTA_CANDIDATOS).is_dir():
            continue
        texto = caminho.read_text(encoding='utf-8')
        try:
            dados = yaml.safe_load(texto) or {}
        except yaml.YAMLError:
            continue
        perfil, restante = _separar(dados)
        if perfil:
            extracoes.append(Extracao(pasta, perfil, _sem_os_campos_do_candidato(texto, restante)))
    return extracoes


def _separar(dados: dict) -> tuple[dict, dict]:
    """Os campos do candidato (respostas e identificador) e o que fica no `concurso.yaml`."""
    perfil, restante = {}, dict(dados)
    if respostas := restante.pop('respostas', None):
        perfil['respostas'] = {
            chave: _ACIMA_DO_CANDIDATO + valor if chave in _CAMPOS_DE_ARQUIVO else valor
            for chave, valor in respostas.items()
        }
    resultado = restante.get('resultado_oficial')
    if isinstance(resultado, dict) and resultado.get('identificador') is not None:
        perfil['resultado_oficial'] = {'identificador': str(resultado['identificador'])}
        restante['resultado_oficial'] = {k: v for k, v in resultado.items() if k != 'identificador'}
    return perfil, restante


def _sem_os_campos_do_candidato(texto: str, restante: dict) -> str:
    """Tira as linhas dos campos do candidato preservando os comentários; se o YAML resultante não
    confere, regrava o arquivo inteiro."""
    linhas, bloco = [], None
    for linha in texto.splitlines(keepends=True):
        if re.match(r'\S', linha) and not linha.startswith('#'):
            bloco = linha.split(':', 1)[0].strip()
        if bloco == 'respostas' or (
            bloco == 'resultado_oficial' and re.match(r'\s+identificador\s*:', linha)
        ):
            continue
        linhas.append(linha)
    novo = ''.join(linhas)
    try:
        if yaml.safe_load(novo) == restante:
            return novo
    except yaml.YAMLError:
        pass
    return yaml.safe_dump(restante, allow_unicode=True, sort_keys=False)


def _fazer_backup(migracao: Migracao, contexto: Contexto) -> Path:
    pasta = _pasta_nova(contexto.home / f'backup-{datetime.now():%Y%m%d-%H%M%S}')
    arquivos: dict[str, Path] = {}
    for nome, caminho in (
        ('raiz', migracao.config_legada),
        ('raiz', migracao.taxonomia_legada),
        ('projeto', contexto.config_projeto if contexto.config_projeto.exists() else None),
    ):
        if caminho is not None:
            arquivos[f'{nome}/{caminho.name}'] = caminho
    for extracao in migracao.extracoes:
        arquivos[f'provas/{extracao.pasta_concurso.name}/concurso.yaml'] = (
            extracao.pasta_concurso / 'concurso.yaml'
        )
    for movimento in migracao.movimentos:
        for caminho in sorted(p for p in movimento.origem.rglob('*') if p.is_file()):
            arquivos[f'analises/{caminho.relative_to(contexto.analises).as_posix()}'] = caminho
    try:
        hashes = {chave: manifesto.hash_arquivo(caminho) for chave, caminho in arquivos.items()}
        for chave, caminho in arquivos.items():
            destino = pasta / chave
            destino.parent.mkdir(parents=True, exist_ok=True)
            _copiar(caminho, destino)
        divergentes = [
            chave for chave, valor in hashes.items() if manifesto.hash_arquivo(pasta / chave) != valor
        ]
        (pasta / ARQUIVO_HASHES).write_text(
            json.dumps(hashes, indent=2, ensure_ascii=False), encoding='utf-8'
        )
    except OSError as erro:
        raise MigracaoError(f'não deu para gravar o backup em {pasta} ({erro}); nada foi alterado') from erro
    if divergentes:
        raise MigracaoError(
            f'o backup em {pasta} não confere com o original ({", ".join(divergentes[:3])}); nada foi alterado'
        )
    return pasta


def _copiar(origem: Path, destino: Path) -> None:
    shutil.copy2(origem, destino)


def _pasta_nova(base: Path) -> Path:
    pasta, n = base, 1
    while pasta.exists():
        n += 1
        pasta = base.with_name(f'{base.name}-{n}')
    pasta.mkdir(parents=True)
    return pasta


def _aplicar(migracao: Migracao, contexto: Contexto) -> None:
    for extracao in migracao.extracoes:
        perfil = pasta_do_candidato(extracao.pasta_concurso, migracao.candidato)
        perfil.mkdir(parents=True, exist_ok=True)
        texto = yaml.safe_dump(extracao.perfil, allow_unicode=True, sort_keys=False)
        (perfil / ARQUIVO_CANDIDATO).write_text(texto, encoding='utf-8')
        (extracao.pasta_concurso / 'concurso.yaml').write_text(extracao.concurso_yaml, encoding='utf-8')
    for movimento in migracao.movimentos:
        movimento.destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(movimento.origem, movimento.destino)
    if migracao.config_legada:
        lidos = yaml.safe_load(migracao.config_legada.read_text(encoding='utf-8')) or {}
        atuais = ler_toml(contexto.config_projeto).get('analise', {})
        valores = {campo: valor for campo, valor in lidos.items() if valor is not None}
        gravar_no_config_projeto(contexto, 'analise', {**valores, **atuais})
        migracao.config_legada.unlink()
    if migracao.taxonomia_legada:
        contexto.projeto.mkdir(parents=True, exist_ok=True)
        shutil.move(migracao.taxonomia_legada, contexto.projeto / ARQUIVO_TAXONOMIA)


def _avisar(migracao: Migracao, backup: Path) -> None:
    if not migracao.ja_migrado:
        logger.info(
            'dados das fases 1 a 3 migrados para o candidato %s; backup em %s', migracao.candidato, backup
        )
        return
    nomes = [m.origem.name for m in migracao.movimentos] + [e.pasta_concurso.name for e in migracao.extracoes]
    for nome in sorted(set(nomes)):
        logger.warning(
            '%s: pasta no formato antigo encontrada depois da migração; migrada para o candidato %s',
            nome,
            migracao.candidato,
        )
    for legado in (migracao.config_legada, migracao.taxonomia_legada):
        if legado:
            logger.warning('%s encontrado depois da migração; migrado para a pasta .concurso/', legado.name)
