#!/usr/bin/env python3
"""Gate de arquitetura: CC, ciclos AST, eferência do pipeline, MI e cobertura.

Lê limiares e dívida em docs/arquitetura/limiares.toml. A lista de dívida só pode
encolher (CC medido ≤ cc_maximo da entrada; entrada sem issue/prazo falha).
"""

from __future__ import annotations

import ast
import json
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

from radon.complexity import cc_visit
from radon.metrics import mi_visit

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / 'src' / 'concursos'
LIMIARES = RAIZ / 'docs' / 'arquitetura' / 'limiares.toml'
COVERAGE_JSON = RAIZ / 'coverage.json'

CICLOS_PROIBIDOS = [
    ('concursos.topicos', 'concursos.analytics.dicionario_topicos'),
    ('concursos.pratica_tec', 'concursos.analytics.tec_estatisticas'),
]


def _carregar_limiares() -> dict:
    return tomllib.loads(LIMIARES.read_text(encoding='utf-8'))


def _mod_from_path(path: Path) -> str:
    rel = path.relative_to(RAIZ / 'src').with_suffix('')
    parts = list(rel.parts)
    if parts[-1] == '__init__':
        parts = parts[:-1]
    return '.'.join(parts)


def _imports_ast() -> dict[str, set[str]]:
    grafo: dict[str, set[str]] = defaultdict(set)
    for path in SRC.rglob('*.py'):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except SyntaxError as erro:
            raise SystemExit(f'AST inválida em {path}: {erro}') from erro
        me = _mod_from_path(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('concursos'):
                grafo[me].add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith('concursos'):
                        grafo[me].add(alias.name)
    return grafo


def _importa(grafo: dict[str, set[str]], origem: str, destino: str) -> bool:
    return any(m == destino or m.startswith(destino + '.') for m in grafo.get(origem, ()))


def _blocos_cc(path: Path) -> list[tuple[str, int, int]]:
    """(nome, lineno, complexity) incluindo closures."""
    codigo = path.read_text(encoding='utf-8')
    resultados: list[tuple[str, int, int]] = []

    def visitar(blocos) -> None:
        for bloco in blocos:
            resultados.append((bloco.name, bloco.lineno, bloco.complexity))
            visitar(getattr(bloco, 'closures', []) or [])

    visitar(cc_visit(codigo))
    return resultados


def _relativo_src(path: Path) -> str:
    return path.relative_to(RAIZ / 'src').as_posix()


def verificar_cc(limiares: dict) -> list[str]:
    falhas: list[str] = []
    divida = {
        (item['arquivo'], item['funcao']): item for item in limiares.get('divida', {}).get('cc', [])
    }
    cc_max = int(limiares['cc_maximo'])
    vistos: set[tuple[str, str]] = set()

    for path in sorted(SRC.rglob('*.py')):
        rel = _relativo_src(path)
        for nome, lineno, complexidade in _blocos_cc(path):
            if complexidade <= cc_max:
                continue
            chave = (rel, nome)
            entrada = divida.get(chave)
            if entrada is None:
                falhas.append(
                    f'CC {complexidade} > {cc_max} sem dívida: {rel}:{lineno} {nome}'
                )
                continue
            if not entrada.get('issue') or not entrada.get('prazo'):
                falhas.append(f'dívida CC sem issue/prazo: {rel} {nome}')
            permitido = int(entrada['cc_maximo'])
            if complexidade > permitido:
                falhas.append(
                    f'CC {complexidade} > dívida {permitido}: {rel}:{lineno} {nome}'
                )
            if complexidade >= 31:
                falhas.append(f'classe E/F proibida: {rel}:{lineno} {nome} CC {complexidade}')
            vistos.add(chave)

    for chave, entrada in divida.items():
        if chave not in vistos:
            # dívida órfã: função já abaixo do limiar global — avisar, não falhar
            print(f'aviso: dívida CC órfã (já ≤{cc_max}): {chave[0]} {chave[1]}')
    return falhas


def verificar_ciclos() -> list[str]:
    grafo = _imports_ast()
    falhas = []
    for a, b in CICLOS_PROIBIDOS:
        if _importa(grafo, a, b) and _importa(grafo, b, a):
            falhas.append(f'ciclo AST: {a} ↔ {b}')
    # pipeline fora de aplicacao/tests
    for path in SRC.rglob('*.py'):
        mod = _mod_from_path(path)
        if mod.startswith('concursos.aplicacao') or mod.startswith('concursos.pipeline'):
            continue
        if 'tests' in path.parts:
            continue
        for dest in grafo.get(mod, ()):
            if dest == 'concursos.pipeline' or dest.startswith('concursos.pipeline.'):
                # legado/relatorio não podem importar pipeline
                if mod.startswith('concursos.cli.legado') or mod == 'concursos.relatorio_html':
                    falhas.append(f'import de pipeline proibido: {mod} → {dest}')
                elif not mod.startswith('concursos.pipeline'):
                    # só aplicacao e o próprio pipeline
                    if not mod.startswith('concursos.aplicacao'):
                        falhas.append(f'import de pipeline fora de aplicacao/: {mod} → {dest}')
    return falhas


def verificar_eferencia_pipeline(limiares: dict) -> list[str]:
    init = SRC / 'pipeline' / '__init__.py'
    if not init.exists():
        return ['pipeline/__init__.py ausente']
    tree = ast.parse(init.read_text(encoding='utf-8'))
    externos: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('concursos'):
            if not node.module.startswith('concursos.pipeline'):
                externos.add(node.module)
    maximo = int(limiares['pipeline_eferencia_max'])
    if len(externos) > maximo:
        return [
            f'pipeline eferência {len(externos)} > {maximo}: {", ".join(sorted(externos))}'
        ]
    print(f'pipeline eferência direta: {len(externos)} (máx {maximo})')
    return []


def verificar_mi(limiares: dict) -> list[str]:
    falhas: list[str] = []
    aviso = float(limiares['mi_minimo_aviso'])
    falha = float(limiares['mi_minimo_falha'])
    for item in limiares.get('divida', {}).get('mi', []):
        path = RAIZ / 'src' / item['arquivo']
        if not path.exists():
            falhas.append(f'MI: arquivo ausente {item["arquivo"]}')
            continue
        codigo = path.read_text(encoding='utf-8')
        mi = float(mi_visit(codigo, multi=True))
        piso_divida = float(item.get('mi_minimo', 0))
        if mi < falha and mi < piso_divida:
            falhas.append(f'MI {mi:.2f} < falha {falha} e < dívida {piso_divida}: {item["arquivo"]}')
        elif mi < falha and piso_divida <= mi:
            # ainda na dívida explícita (permite MI baixo até extrair)
            print(f'aviso: MI {mi:.2f} < {aviso} (dívida): {item["arquivo"]}')
        elif mi < aviso:
            print(f'aviso: MI {mi:.2f} < {aviso}: {item["arquivo"]}')
        else:
            print(f'MI ok {mi:.2f}: {item["arquivo"]}')
    return falhas


def verificar_cobertura(limiares: dict) -> list[str]:
    falhas: list[str] = []
    caminho = COVERAGE_JSON
    if not caminho.exists():
        # aceita artefato da Fase 0
        alt = RAIZ / 'docs' / 'arquitetura' / 'metricas-7016502' / 'coverage.json'
        caminho = alt if alt.exists() else caminho
    if not caminho.exists():
        print('aviso: coverage.json ausente; pule cobertura neste run')
        return []
    dados = json.loads(caminho.read_text(encoding='utf-8'))
    total = dados['totals']
    pct = 100.0 * total['covered_lines'] / total['num_statements']
    minimo = float(limiares['cobertura_minima'])
    if pct < minimo:
        falhas.append(f'cobertura {pct:.4f}% < {minimo}%')
    else:
        print(f'cobertura {pct:.4f}% (mín {minimo}%)')
    limiar_mod = 60.0
    max_baixos = int(limiares['modulos_abaixo_de_60_max'])
    baixos = []
    for arquivo, info in dados['files'].items():
        s = info['summary']
        if s['num_statements'] == 0:
            continue
        p = 100.0 * s['covered_lines'] / s['num_statements']
        if p < limiar_mod:
            baixos.append((p, arquivo))
    if len(baixos) > max_baixos:
        falhas.append(f'{len(baixos)} módulos <60% (máx {max_baixos}): {baixos}')
    else:
        print(f'módulos <60%: {len(baixos)} (máx {max_baixos})')
    return falhas


def main() -> int:
    limiares = _carregar_limiares()
    falhas: list[str] = []
    falhas += verificar_cc(limiares)
    falhas += verificar_ciclos()
    falhas += verificar_eferencia_pipeline(limiares)
    falhas += verificar_mi(limiares)
    falhas += verificar_cobertura(limiares)

    print('\n--- resumo saúde ---')
    print(f'falhas: {len(falhas)}')
    for f in falhas:
        print(f'  ERRO: {f}')
    return 1 if falhas else 0


if __name__ == '__main__':
    sys.exit(main())
