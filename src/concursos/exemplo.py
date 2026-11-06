"""O concurso de exemplo do onboarding: sintético, no formato do `scripts/smoke.py`, de uma candidata fictícia."""

from pathlib import Path

CONCURSO = 'exemplo'
CANDIDATO = 'exemplo'
CONCURSO_YAML = """\
banca: fgv
formato: multipla_escolha
pontuacao: simples
data_prova: 2025-03-09
edital:
  manual: edital_manual.yaml
provas:
  unica:
    gabarito: gabarito.txt
    itens: [1, 10]
"""
GABARITO = 'ABCDEABCDE'
RESPOSTAS = 'ABCDEEDCBA'


def criar_exemplo(raiz: Path) -> Path:
    """Grava `<raiz>/provas/exemplo/` e devolve a pasta do concurso."""
    pasta = raiz / 'provas' / CONCURSO
    respostas = pasta / 'candidatos' / CANDIDATO
    respostas.mkdir(parents=True, exist_ok=True)
    (pasta / 'concurso.yaml').write_text(CONCURSO_YAML, encoding='utf-8')
    (pasta / 'edital_manual.yaml').write_text('conhecimentos: []\n', encoding='utf-8')
    (pasta / 'gabarito.txt').write_text(_linhas(GABARITO), encoding='utf-8')
    (respostas / 'respostas.txt').write_text(_linhas(RESPOSTAS), encoding='utf-8')
    return pasta


def _linhas(letras: str) -> str:
    return ''.join(f'{numero} {letra}\n' for numero, letra in enumerate(letras, start=1))
