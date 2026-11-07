"""O nome mostrado de um concurso, tirado do edital: "SIGLA ANO — Cargo", com o nome oficial e o edital no
subtítulo. A pasta (`nome` do `concurso.yaml`) continua sendo o identificador."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from concursos.analytics.regras_edital import CONFIANCA_SIGLA_PELAS_INICIAIS, FonteRegra
from concursos.concurso_config import ConcursoConfig
from concursos.texto import normalizar

CONFIANCA_PCI = 0.6
CONFIANCA_ARQUIVO = 0.2
FONTES_CONFIRMADAS = frozenset({FonteRegra.CONFIG, FonteRegra.RETIFICACAO, FonteRegra.EDITAL})
"""Abaixo delas, o nome aparece com o selo "a confirmar"."""
NOMES_GENERICOS = frozenset({'edital', 'prova', 'caderno', 'gabarito', 'anexo', 'retificacao'})
_SIGLA_NO_FIM = re.compile(r'\s*(?:\([^()]{2,20}\)|\s[–-]\s\S{2,20})\s*$')
_NUMERO_DO_EDITAL = re.compile(r'N[º°.o]\s*(?P<numero>\d[\d.]*)(?:/(?P<ano>\d{4}))?', re.IGNORECASE)


@dataclass(frozen=True)
class NomeDoConcurso:
    titulo: str
    subtitulo: str
    fonte: FonteRegra
    confianca: float
    a_confirmar: bool
    origem: str
    """De onde veio, em palavras, para "O que o app decidiu sozinho"."""


def _valor(identificacao: Mapping | None, campo: str):
    return ((identificacao or {}).get(campo) or {}).get('valor')


def _fonte(identificacao: Mapping | None, campo: str) -> FonteRegra:
    return FonteRegra(((identificacao or {}).get(campo) or {}).get('fonte') or FonteRegra.DEFAULT)


def _oficial(identificacao: Mapping | None) -> str | None:
    """O nome oficial sem a sigla do fim ("Tribunal de Contas da União (TCU)"), que já está no título."""
    oficial = _valor(identificacao, 'nome_oficial')
    return (_SIGLA_NO_FIM.sub('', oficial) or oficial) if oficial else None


def _cargo(identificacao: Mapping | None) -> str | None:
    cargo, especialidade = _valor(identificacao, 'cargo'), _valor(identificacao, 'especialidade')
    if cargo and especialidade:
        return f'{cargo} – {especialidade}'
    return cargo


def edital_curto(identificacao: Mapping | None) -> str | None:
    """ "EDITAL Nº 1 – TCU/AUFC, DE 24 DE OUTUBRO DE 2025" vira "Edital nº 1/2025"."""
    linha = _valor(identificacao, 'edital')
    if not linha:
        return None
    if match := _NUMERO_DO_EDITAL.search(linha):
        ano = match['ano'] or _valor(identificacao, 'ano')
        return f'Edital nº {match["numero"]}' + (f'/{ano}' if ano else '')
    return None


def titulo_pelo_edital(identificacao: Mapping | None) -> str | None:
    """ "TCU 2025 — Auditor Federal de Controle Externo"; com a sigla tirada só das iniciais, o nome oficial
    no lugar dela. Sem sigla nem nome oficial, None."""
    sigla, oficial = _valor(identificacao, 'sigla'), _oficial(identificacao)
    confianca_sigla = ((identificacao or {}).get('sigla') or {}).get('confianca_extracao') or 0.0
    cabeca = (
        oficial if oficial and (not sigla or confianca_sigla <= CONFIANCA_SIGLA_PELAS_INICIAIS) else sigla
    )
    if not cabeca:
        return None
    ano, cargo = _valor(identificacao, 'ano'), _cargo(identificacao)
    titulo = f'{cabeca} {ano}' if ano else cabeca
    return f'{titulo} — {cargo}' if cargo else titulo


def subtitulo_pelo_edital(identificacao: Mapping | None) -> str:
    return ', '.join(p for p in (_oficial(identificacao), edital_curto(identificacao)) if p)


def _do_arquivo(config: ConcursoConfig) -> tuple[str, str] | None:
    edital = [config.edital.arquivo] if config.edital and config.edital.arquivo else []
    arquivos = [*edital, *(p.caderno for p in config.provas if p.caderno)]
    for arquivo in arquivos:
        base = Path(arquivo).stem
        palavras = re.findall(r'[0-9A-Za-zÀ-ÿ]+', base)
        if palavras and not {normalizar(p).lower() for p in palavras} <= NOMES_GENERICOS:
            return ' '.join(palavras).capitalize(), arquivo
    return None


def nome_do_concurso(config: ConcursoConfig, identificacao: Mapping | None) -> NomeDoConcurso:
    """Nesta ordem: a correção do usuário (`titulo`), a retificação ou o edital, o título do PCI, a IA, o
    nome do arquivo do edital ou da prova e a pasta. `identificacao` é a do edital estruturado."""
    subtitulo = subtitulo_pelo_edital(identificacao)
    if config.titulo:
        return NomeDoConcurso(config.titulo, subtitulo, FonteRegra.CONFIG, 1.0, False, 'corrigido por você')
    titulo = titulo_pelo_edital(identificacao)
    fonte = _fonte(identificacao, 'sigla' if _valor(identificacao, 'sigla') else 'nome_oficial')
    if titulo and fonte in FONTES_CONFIRMADAS:
        origem = 'da retificação do edital' if fonte is FonteRegra.RETIFICACAO else 'do edital'
        confianca = ((identificacao or {}).get('sigla') or {}).get('confianca_extracao') or 0.0
        return NomeDoConcurso(titulo, subtitulo, fonte, confianca, False, origem)
    if config.pci_titulo:
        return NomeDoConcurso(
            config.pci_titulo, subtitulo, FonteRegra.PCI, CONFIANCA_PCI, True, 'do título no PCI Concursos'
        )
    if titulo and fonte is FonteRegra.LLM:
        confianca = ((identificacao or {}).get('sigla') or {}).get('confianca_extracao') or 0.0
        return NomeDoConcurso(titulo, subtitulo, fonte, confianca, True, 'lido pela IA no edital')
    if do_arquivo := _do_arquivo(config):
        nome, arquivo = do_arquivo
        return NomeDoConcurso(
            nome, subtitulo, FonteRegra.DEFAULT, CONFIANCA_ARQUIVO, True, f'do nome do arquivo {arquivo}'
        )
    return NomeDoConcurso(config.nome, subtitulo, FonteRegra.DEFAULT, 0.0, True, 'da pasta do concurso')


def rotulo_do_concurso(slug: str, identificacao: Mapping | None) -> str:
    """ "slug: nome oficial — cargo"; sem nome oficial ou cargo, só o slug."""
    oficial, cargo = _valor(identificacao, 'nome_oficial'), _cargo(identificacao)
    if not oficial or not cargo:
        return slug
    return f'{slug}: {oficial} — {cargo}'


def rotulos_dos_concursos(regras_por_concurso: Mapping[str, Mapping]) -> dict[str, str]:
    return {
        slug: rotulo_do_concurso(slug, (regras or {}).get('identificacao'))
        for slug, regras in regras_por_concurso.items()
    }
