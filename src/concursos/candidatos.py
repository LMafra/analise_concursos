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
from concursos.config.contexto import ler_toml
from concursos.erros import avisar
from concursos.integracoes.pci_mcp import validar_cargos, validar_uf
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


def _folha_do_candidato(config: ConcursoConfig, respostas: dict, da_pasta) -> FolhaConfig | None:
    if not respostas.get('folha'):
        return None
    herdada = config.folha
    return FolhaConfig(
        da_pasta(respostas['folha']),
        respostas.get('template') or (herdada and herdada.template) or None,
        respostas.get('total_itens') or (herdada and herdada.total_itens),
        respostas.get('itens_por_coluna') or (herdada and herdada.itens_por_coluna),
    )


def _resultado_do_candidato(config: ConcursoConfig, perfil: dict):
    resultado = config.resultado_oficial
    if resultado is None:
        return None
    identificador = (perfil.get('resultado_oficial') or {}).get('identificador')
    return replace(resultado, identificador=None if identificador is None else str(identificador))


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

    arquivo = respostas.get('arquivo')
    if (pasta_do_candidato(config.pasta, candidato) / ARQUIVO_REVISADAS).exists():
        arquivo = ARQUIVO_REVISADAS
    return replace(
        config,
        respostas_arquivo=da_pasta_do_concurso(arquivo) if arquivo else None,
        folha=_folha_do_candidato(config, respostas, da_pasta_do_concurso),
        resultado_oficial=_resultado_do_candidato(config, perfil),
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
        avisar(
            logger,
            f'{config.nome}: revisão antiga: a folha de respostas mudou depois que você revisou a leitura, e as '
            'respostas continuam vindo da revisão.',
            f'para ler a folha nova, apague o {ARQUIVO_REVISADAS} e analise de novo.',
            f'a folha {folha.name} mudou depois do --reuse-csv',
        )


_CAMPOS_CANDIDATO = frozenset({'nome', 'respostas', 'resultado_oficial'})
_CAMPOS_RESPOSTAS = frozenset({'arquivo', 'folha'})
_CAMPOS_RESULTADO = frozenset({'identificador'})


def _validar_respostas_perfil(caminho: Path, respostas: object) -> None:
    if not isinstance(respostas, dict):
        raise ConfiguracaoInvalidaError(f'{caminho}: respostas = {respostas!r} é inválido')
    extras = sorted(set(respostas) - _CAMPOS_RESPOSTAS)
    if extras:
        raise ConfiguracaoInvalidaError(
            f'{caminho}: respostas tem campo desconhecido {", ".join(extras)}'
        )
    tem_arquivo = 'arquivo' in respostas
    tem_folha = 'folha' in respostas
    if tem_arquivo == tem_folha:
        raise ConfiguracaoInvalidaError(
            f'{caminho}: respostas precisa de arquivo ou folha, só um dos dois'
        )
    chave = 'arquivo' if tem_arquivo else 'folha'
    if not isinstance(respostas[chave], str) or not respostas[chave]:
        raise ConfiguracaoInvalidaError(f'{caminho}: respostas.{chave} = {respostas[chave]!r} é inválido')


def _validar_resultado_perfil(caminho: Path, resultado: object) -> None:
    if not isinstance(resultado, dict):
        raise ConfiguracaoInvalidaError(f'{caminho}: resultado_oficial = {resultado!r} é inválido')
    extras = sorted(set(resultado) - _CAMPOS_RESULTADO)
    if extras:
        raise ConfiguracaoInvalidaError(
            f'{caminho}: resultado_oficial tem campo desconhecido {", ".join(extras)}'
        )
    if 'identificador' in resultado and not isinstance(resultado['identificador'], str):
        raise ConfiguracaoInvalidaError(
            f'{caminho}: resultado_oficial.identificador = {resultado["identificador"]!r} é inválido'
        )


def _validar_perfil(caminho: Path, dados: dict) -> dict:
    desconhecidos = sorted(set(dados) - _CAMPOS_CANDIDATO)
    if desconhecidos:
        raise ConfiguracaoInvalidaError(
            f'{caminho}: campo desconhecido {", ".join(desconhecidos)}; '
            f'os campos são {", ".join(sorted(_CAMPOS_CANDIDATO))}'
        )
    if 'nome' in dados and not isinstance(dados['nome'], str):
        raise ConfiguracaoInvalidaError(f'{caminho}: nome = {dados["nome"]!r} é inválido')
    if 'respostas' in dados:
        _validar_respostas_perfil(caminho, dados['respostas'])
    if 'resultado_oficial' in dados:
        _validar_resultado_perfil(caminho, dados['resultado_oficial'])
    return dados


def ler_perfil(config: ConcursoConfig, candidato: str) -> dict:
    """O `candidato.yaml`; sem ele, o perfil inferido dos arquivos da subpasta."""
    pasta = pasta_do_candidato(config.pasta, candidato)
    caminho = pasta / ARQUIVO_CANDIDATO
    if not caminho.exists():
        return inferir_perfil(pasta)
    try:
        dados = yaml.safe_load(caminho.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as erro:
        raise ConfiguracaoInvalidaError(f'{caminho}: {erro}') from erro
    if not isinstance(dados, dict):
        raise ConfiguracaoInvalidaError(f'{caminho}: o perfil precisa ser um mapeamento')
    return _validar_perfil(caminho, dados)


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
            avisar(
                logger,
                f'{pasta.parent.parent.name}: não achei as respostas de {pasta.name}.',
                'ponha o arquivo de respostas ou a folha na pasta do candidato, ou cadastre pela janela '
                '(Novo concurso).',
                f'{pasta}: sem respostas reconhecíveis; crie o {ARQUIVO_CANDIDATO}',
            )
            continue
        gravar_perfil(pasta, perfil)
        avisar(
            logger,
            f'{pasta.parent.parent.name}: montei os dados de {pasta.name} a partir dos arquivos da pasta.',
            detalhe=f'{pasta}: candidato sem perfil; {ARQUIVO_CANDIDATO} criado a partir dos arquivos',
        )


def adicionar_arquivo(pasta_concurso: Path, arquivo: Path, nome: str) -> Path:
    """Copia o arquivo de respostas (texto) ou a folha para a subpasta do candidato e grava o perfil."""
    candidato = slug(nome)
    destino = pasta_do_candidato(pasta_concurso, candidato)
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arquivo, destino / arquivo.name)
    chave = 'folha' if arquivo.suffix.lower() in _EXTENSOES_FOLHA else 'arquivo'
    gravar_perfil(destino, {'nome': nome, 'respostas': {chave: arquivo.name}})
    return destino


def gravar_perfil(pasta: Path, perfil: dict) -> None:
    texto = yaml.safe_dump(perfil, allow_unicode=True, sort_keys=False)
    (pasta / ARQUIVO_CANDIDATO).write_text(texto, encoding='utf-8')


def gravar_perfil_global(home: Path, nome: str, atualizar: bool = False) -> Path:
    """Sem `atualizar`, um perfil existente fica como está; com ele, as outras seções (ex.: `[pci]`) ficam."""
    candidato = slug(nome)
    caminho = home / PASTA_PERFIS_GLOBAIS / f'{candidato}.toml'
    if atualizar or not caminho.exists():
        dados = ler_toml(caminho) | {'nome': nome, 'slug': candidato}
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(tomli_w.dumps(dados), encoding='utf-8')
    return caminho


def alvos_pci(home: Path, candidato: str) -> tuple[tuple[str, ...], str]:
    """Os cargos e a UF de `[pci]` no perfil global do candidato; sem perfil ou sem seção, vazios."""
    caminho = home / PASTA_PERFIS_GLOBAIS / f'{candidato}.toml'
    secao = ler_toml(caminho).get('pci', {})
    onde = f'{caminho}: [pci]'
    cargos = validar_cargos(secao['cargos'], onde) if 'cargos' in secao else ()
    uf = validar_uf(secao['uf'], onde) if 'uf' in secao else ''
    return cargos, uf
