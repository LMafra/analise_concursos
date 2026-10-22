"""Candidatos de um concurso: a subpasta `candidatos/<slug>/` com as respostas e o `candidato.yaml`."""

import logging
import posixpath
import re
import shutil
import unicodedata
from dataclasses import replace
from pathlib import Path

import tomli_w
import yaml

from concursos.concurso_config import ConcursoConfig, ConfiguracaoInvalidaError, FolhaConfig

logger = logging.getLogger(__name__)

PASTA_CANDIDATOS = 'candidatos'
ARQUIVO_CANDIDATO = 'candidato.yaml'
PASTA_PERFIS_GLOBAIS = 'candidatos'
_EXTENSOES_FOLHA = {'.pdf', '.png', '.jpg', '.jpeg'}


def slug(nome: str) -> str:
    sem_acento = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode()
    valor = re.sub(r'[^a-z0-9]+', '_', sem_acento.lower()).strip('_')
    if not valor:
        raise ConfiguracaoInvalidaError(f'nome de candidato inválido: {nome!r} (use letras ou números)')
    return valor


def pasta_do_candidato(pasta_concurso: Path, candidato: str) -> Path:
    return pasta_concurso / PASTA_CANDIDATOS / candidato


def candidatos_do_concurso(pasta_concurso: Path) -> list[str]:
    raiz = pasta_concurso / PASTA_CANDIDATOS
    if not raiz.is_dir():
        return []
    return sorted(p.name for p in raiz.iterdir() if p.is_dir() and not p.name.startswith('.'))


def candidatos_existentes(raiz_provas: Path) -> list[str]:
    if not raiz_provas.is_dir():
        return []
    return sorted(
        {c for pasta in raiz_provas.iterdir() if pasta.is_dir() for c in candidatos_do_concurso(pasta)}
    )


def aplicar_candidato(config: ConcursoConfig, candidato: str) -> ConcursoConfig:
    """O concurso visto por um candidato: respostas e identificador vêm só do perfil dele, com caminhos
    relativos à pasta do concurso."""
    perfil = ler_perfil(config, candidato)
    prefixo = f'{PASTA_CANDIDATOS}/{candidato}/'
    respostas = perfil.get('respostas') or {}
    if respostas.get('arquivo') and respostas.get('folha'):
        raise ConfiguracaoInvalidaError(f"{prefixo}{ARQUIVO_CANDIDATO}: respostas: use 'arquivo' ou 'folha'")

    def da_pasta_do_concurso(caminho: str) -> str:
        return posixpath.normpath(prefixo + caminho)

    folha = None
    if respostas.get('folha'):
        herdada = config.folha
        template = respostas.get('template') or (herdada and herdada.template)
        if not template:
            raise ConfiguracaoInvalidaError(
                f"{prefixo}{ARQUIVO_CANDIDATO}: campo obrigatório 'respostas.template' ausente"
            )
        folha = FolhaConfig(
            da_pasta_do_concurso(respostas['folha']),
            template,
            respostas.get('total_itens') or (herdada and herdada.total_itens),
            respostas.get('itens_por_coluna') or (herdada and herdada.itens_por_coluna),
        )
    resultado = config.resultado_oficial
    if resultado is not None:
        identificador = (perfil.get('resultado_oficial') or {}).get('identificador')
        resultado = replace(resultado, identificador=None if identificador is None else str(identificador))
    return replace(
        config,
        respostas_arquivo=da_pasta_do_concurso(respostas['arquivo']) if respostas.get('arquivo') else None,
        folha=folha,
        resultado_oficial=resultado,
    )


def ler_perfil(config: ConcursoConfig, candidato: str) -> dict:
    """O `candidato.yaml`; sem ele, o perfil inferido dos arquivos da subpasta."""
    pasta = pasta_do_candidato(config.pasta, candidato)
    caminho = pasta / ARQUIVO_CANDIDATO
    if not caminho.exists():
        return inferir_perfil(pasta)
    try:
        return yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro


def inferir_perfil(pasta: Path) -> dict:
    """`respostas.txt` (ou o único .txt) vira arquivo de respostas; o único PDF ou imagem vira folha."""
    if not pasta.is_dir():
        return {}
    arquivos = [p for p in sorted(pasta.iterdir()) if p.is_file() and ':' not in p.name]
    textos = [p for p in arquivos if p.suffix.lower() == '.txt']
    folhas = [p for p in arquivos if p.suffix.lower() in _EXTENSOES_FOLHA]
    if (pasta / 'respostas.txt').exists():
        return {'respostas': {'arquivo': 'respostas.txt'}}
    if len(textos) == 1:
        return {'respostas': {'arquivo': textos[0].name}}
    if len(folhas) == 1:
        return {'respostas': {'folha': folhas[0].name}}
    return {}


def completar_perfis(raiz_provas: Path, candidato: str) -> None:
    """Grava o `candidato.yaml` inferido nas subpastas do candidato que não têm um."""
    for pasta_concurso in sorted(p for p in raiz_provas.iterdir() if p.is_dir()):
        pasta = pasta_do_candidato(pasta_concurso, candidato)
        caminho = pasta / ARQUIVO_CANDIDATO
        if not pasta.is_dir() or caminho.exists():
            continue
        perfil = inferir_perfil(pasta)
        if not perfil:
            logger.warning('%s: sem respostas reconhecíveis; crie o %s', pasta, ARQUIVO_CANDIDATO)
            continue
        caminho.write_text(yaml.safe_dump(perfil, allow_unicode=True, sort_keys=False), encoding='utf-8')
        logger.warning('%s: candidato sem perfil; %s criado a partir dos arquivos', pasta, ARQUIVO_CANDIDATO)


def adicionar_arquivo(pasta_concurso: Path, arquivo: Path, nome: str) -> Path:
    """Copia o arquivo de respostas (texto) ou a folha para a subpasta do candidato e grava o perfil."""
    candidato = slug(nome)
    destino = pasta_do_candidato(pasta_concurso, candidato)
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arquivo, destino / arquivo.name)
    chave = 'folha' if arquivo.suffix.lower() in _EXTENSOES_FOLHA else 'arquivo'
    perfil = {'nome': nome, 'respostas': {chave: arquivo.name}}
    texto = yaml.safe_dump(perfil, allow_unicode=True, sort_keys=False)
    (destino / ARQUIVO_CANDIDATO).write_text(texto, encoding='utf-8')
    return destino


def gravar_perfil_global(home: Path, nome: str) -> Path:
    candidato = slug(nome)
    caminho = home / PASTA_PERFIS_GLOBAIS / f'{candidato}.toml'
    if not caminho.exists():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(tomli_w.dumps({'nome': nome, 'slug': candidato}), encoding='utf-8')
    return caminho
