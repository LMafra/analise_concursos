"""Peças puras do Perguntar: a IA do usuário no open-notebook, as citações do Ask e a busca nas análises."""

import re
from dataclasses import dataclass
from pathlib import Path

from concursos.livros.indice import PALAVRAS_VAZIAS, palavras, sem_acento
from concursos.llm import ConfiguracaoLlm, FormatoApi

CITACAO = re.compile(r'\s*\[source:([^\]\s]+)\]')
TAMANHO_TRECHO_ANALISE = 280
SEM_CHAVE = 'sem-chave'
VAZIAS = frozenset(sem_acento(p) for p in PALAVRAS_VAZIAS)


def provedor_do_modelo(configuracao: ConfiguracaoLlm) -> str:
    """O provedor do open-notebook: a Anthropic pelo nome; os outros pelo endereço compatível com a OpenAI."""
    return 'anthropic' if configuracao.api is FormatoApi.ANTHROPIC else 'openai_compatible'


def ambiente_da_ia(configuracao: ConfiguracaoLlm, chave: str | None) -> dict[str, str]:
    """As variáveis que levam a IA ao open-notebook na partida dos processos; a chave nunca vai ao banco."""
    if configuracao.api is FormatoApi.ANTHROPIC:
        return {'ANTHROPIC_API_KEY': chave or ''}
    return {
        'OPENAI_COMPATIBLE_BASE_URL_LLM': configuracao.url,
        'OPENAI_COMPATIBLE_API_KEY_LLM': chave or SEM_CHAVE,
    }


def _sem_prefixo(source_id: str) -> str:
    return source_id.removeprefix('source:')


def citacoes(resposta: str) -> list[str]:
    """Os IDs dos sources citados como `[source:id]`, na ordem e sem repetir."""
    return list(dict.fromkeys(_sem_prefixo(c) for c in CITACAO.findall(resposta)))


def sem_citacoes(resposta: str) -> str:
    return CITACAO.sub('', resposta).strip()


def por_source(mapa: dict[str, object]) -> dict[str, object]:
    """O mesmo mapa com a chave sem o prefixo `source:`, como aparece na citação."""
    return {_sem_prefixo(chave): valor for chave, valor in mapa.items()}


@dataclass(frozen=True)
class TrechoDeAnalise:
    arquivo: Path
    secao: str
    trecho: str
    relevancia: int


def _termos(consulta: str) -> list[str]:
    return [p for p in dict.fromkeys(palavras(consulta)) if p not in VAZIAS and len(p) > 1]


def _trecho(paragrafo: str, termo: str) -> str:
    texto = ' '.join(paragrafo.split())
    if len(texto) <= TAMANHO_TRECHO_ANALISE:
        return texto
    posicao = sem_acento(texto.lower()).find(termo)
    inicio = max(0, posicao - TAMANHO_TRECHO_ANALISE // 3)
    pedaco = texto[inicio : inicio + TAMANHO_TRECHO_ANALISE]
    return ('…' if inicio else '') + pedaco + ('…' if inicio + TAMANHO_TRECHO_ANALISE < len(texto) else '')


def buscar_nas_analises(pasta: Path, consulta: str, limite: int = 10) -> list[TrechoDeAnalise]:
    """Os parágrafos dos relatórios em Markdown com mais termos da pergunta, com a seção em que estão."""
    termos = _termos(consulta)
    if not termos or not pasta.is_dir():
        return []
    achados = []
    for arquivo in sorted(pasta.rglob('*.md')):
        secao = ''
        for paragrafo in re.split(r'\n\s*\n', arquivo.read_text(encoding='utf-8', errors='replace')):
            if paragrafo.lstrip().startswith('#'):
                secao = paragrafo.strip().splitlines()[0].lstrip('#').strip()
            normalizado = sem_acento(paragrafo.lower())
            encontrados = [t for t in termos if t in normalizado]
            if encontrados:
                achados.append(
                    TrechoDeAnalise(arquivo, secao, _trecho(paragrafo, encontrados[0]), len(encontrados))
                )
    achados.sort(key=lambda a: -a.relevancia)
    return achados[:limite]
