"""Candidatos de um concurso: a subpasta `candidatos/<slug>/` com as respostas e o `candidato.yaml`."""

import json
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
from concursos.manifesto import hash_arquivo
from concursos.modelo import Origem, RespostaMarcada
from concursos.respostas import ler_respostas_csv

logger = logging.getLogger(__name__)

PASTA_CANDIDATOS = 'candidatos'
ARQUIVO_CANDIDATO = 'candidato.yaml'
ARQUIVO_REVISADAS = 'respostas_revisadas.csv'
ARQUIVO_FOLHA_REVISADA = 'respostas_revisadas.json'
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
        folha = FolhaConfig(
            da_pasta_do_concurso(respostas['folha']),
            respostas.get('template') or (herdada and herdada.template) or None,
            respostas.get('total_itens') or (herdada and herdada.total_itens),
            respostas.get('itens_por_coluna') or (herdada and herdada.itens_por_coluna),
        )
    resultado = config.resultado_oficial
    if resultado is not None:
        identificador = (perfil.get('resultado_oficial') or {}).get('identificador')
        resultado = replace(resultado, identificador=None if identificador is None else str(identificador))
    arquivo = respostas.get('arquivo')
    if (pasta_do_candidato(config.pasta, candidato) / ARQUIVO_REVISADAS).exists():
        arquivo = ARQUIVO_REVISADAS
    return replace(
        config,
        respostas_arquivo=da_pasta_do_concurso(arquivo) if arquivo else None,
        folha=folha,
        resultado_oficial=resultado,
    )


def ler_respostas_do_csv(config: ConcursoConfig, caminho: Path) -> list[RespostaMarcada]:
    """O CSV manual ou o revisado (`--reuse-csv`), que vence a folha; avisa se a folha mudou depois da revisão."""
    revisado = caminho.name == ARQUIVO_REVISADAS
    if revisado:
        _avisar_revisao_antiga(config, caminho)
    return ler_respostas_csv(
        caminho.read_bytes(),
        config.formato,
        [q for prova in config.provas for q in prova.questoes],
        str(caminho.relative_to(config.pasta)),
        config.n_alternativas,
        Origem.REVISADA if revisado else Origem.MANUAL,
    )


def gravar_revisao(config: ConcursoConfig, candidato: str, csv: Path) -> Path:
    """Copia o CSV de leitura corrigido para a subpasta do candidato, com o hash da folha lida nele.

    O CSV é validado antes da cópia, para uma revisão inválida não substituir a folha."""
    pasta = pasta_do_candidato(config.pasta, candidato)
    ler_respostas_csv(
        csv.read_bytes(),
        config.formato,
        [q for prova in config.provas for q in prova.questoes],
        csv.name,
        config.n_alternativas,
        Origem.REVISADA,
    )
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / ARQUIVO_REVISADAS
    shutil.copyfile(csv, destino)
    folha = config.folha and config.caminho(config.folha.arquivo)
    origem = {'folha': folha.name, 'sha256': hash_arquivo(folha)} if folha and folha.exists() else {}
    (pasta / ARQUIVO_FOLHA_REVISADA).write_text(json.dumps(origem, indent=2), encoding='utf-8')
    return destino


def _avisar_revisao_antiga(config: ConcursoConfig, revisado: Path) -> None:
    registro = revisado.with_name(ARQUIVO_FOLHA_REVISADA)
    if config.folha is None or not registro.exists():
        return
    folha = config.caminho(config.folha.arquivo)
    revisada = json.loads(registro.read_text(encoding='utf-8')).get('sha256')
    if folha.exists() and revisada and hash_arquivo(folha) != revisada:
        logger.warning(
            '%s: revisão antiga: a folha %s mudou depois do --reuse-csv, e as respostas continuam vindo do %s. '
            'Para ler a folha nova, apague o %s e rode de novo',
            config.nome,
            folha.name,
            ARQUIVO_REVISADAS,
            ARQUIVO_REVISADAS,
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
    """`respostas.txt` ou `respostas.csv` (ou o único .txt ou .csv) vira arquivo de respostas; o único PDF ou
    imagem vira folha. O CSV revisado não conta: ele vence o que for inferido."""
    if not pasta.is_dir():
        return {}
    arquivos = [
        p
        for p in sorted(pasta.iterdir())
        if p.is_file() and ':' not in p.name and p.name != ARQUIVO_REVISADAS
    ]
    folhas = [p for p in arquivos if p.suffix.lower() in _EXTENSOES_FOLHA]
    for extensao in ('.txt', '.csv'):
        if (pasta / f'respostas{extensao}').exists():
            return {'respostas': {'arquivo': f'respostas{extensao}'}}
    for extensao in ('.txt', '.csv'):
        if len(candidatos := [p for p in arquivos if p.suffix.lower() == extensao]) == 1:
            return {'respostas': {'arquivo': candidatos[0].name}}
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


def gravar_perfil_global(home: Path, nome: str, atualizar: bool = False) -> Path:
    """Sem `atualizar`, um perfil existente fica como está."""
    candidato = slug(nome)
    caminho = home / PASTA_PERFIS_GLOBAIS / f'{candidato}.toml'
    if atualizar or not caminho.exists():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(tomli_w.dumps({'nome': nome, 'slug': candidato}), encoding='utf-8')
    return caminho
