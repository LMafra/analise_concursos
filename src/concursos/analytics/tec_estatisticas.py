"""Estatísticas da prática TEC: matérias/assuntos com mais erros e evolução simples."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from concursos.pratica_tec import ARQUIVO_RESPOSTAS, ARQUIVO_TENTATIVAS, PASTA_PRATICA, RESULTADO_ERRO


@dataclass(frozen=True)
class ResumoTec:
    por_materia: list[tuple[str, int]]
    por_assunto: list[tuple[str, int]]
    tentativas_acerto: int
    tentativas_erro: int
    frases: list[str]


def _ler(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        return []
    with caminho.open(encoding='utf-8', newline='') as arquivo:
        return list(csv.DictReader(arquivo))


def resumir_pratica(pasta_candidato: Path) -> ResumoTec:
    pasta = pasta_candidato / PASTA_PRATICA
    respostas = _ler(pasta / ARQUIVO_RESPOSTAS)
    erros = [r for r in respostas if r.get('resultado') == RESULTADO_ERRO]
    por_mat = Counter((r.get('mat') or 'Sem matéria') for r in erros)
    por_ass = Counter((r.get('ass') or 'Sem assunto') for r in erros)
    tentativas = _ler(pasta / ARQUIVO_TENTATIVAS)
    acertos = sum(1 for t in tentativas if t.get('resultado') == 'acerto')
    falhas = sum(1 for t in tentativas if t.get('resultado') == 'erro')
    frases: list[str] = []
    if por_mat:
        mat, n = por_mat.most_common(1)[0]
        frases.append(f'Matéria com mais erros: {mat} ({n}).')
    if por_ass:
        ass, n = por_ass.most_common(1)[0]
        frases.append(f'Assunto recorrente: {ass} ({n} erro(s)).')
    if tentativas:
        frases.append(f'Nas repetições: {acertos} acerto(s) e {falhas} erro(s).')
    pci = pasta / 'tec_pci_provas.csv'
    if pci.is_file():
        provas = _ler(pci)
        if provas:
            temas = sorted({p.get('ass') or '' for p in provas if p.get('ass')})
            frases.append(f'Temas com prova no PCI: {", ".join(temas[:5])}.')
    return ResumoTec(
        por_materia=por_mat.most_common(),
        por_assunto=por_ass.most_common(),
        tentativas_acerto=acertos,
        tentativas_erro=falhas,
        frases=frases,
    )


def markdown_resumo(pasta_candidato: Path) -> str:
    resumo = resumir_pratica(pasta_candidato)
    if not resumo.frases:
        return '# Prática TEC\n\nSem dados ainda.\n'
    linhas = ['# Prática TEC', '']
    for frase in resumo.frases:
        linhas.append(f'- {frase}')
    linhas.append('')
    return '\n'.join(linhas)
