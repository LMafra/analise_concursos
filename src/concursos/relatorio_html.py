"""Relatório HTML por candidato: um índice dos concursos e um HTML por relatório markdown, sem rede."""

import json
import logging
import os
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from html import escape
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd
from markdown_it import MarkdownIt

from concursos.analytics.consolidado import (
    carregar_consolidado,
    cortes_por_concurso,
    pasta_consolidado,
    regras_por_concurso,
)
from concursos.analytics.evolucao import comparar_percentual_e_gap
from concursos.analytics.insights import gravar_relatorio_evolucao
from concursos.consolidado import MINIMO_CONCURSOS, PASTA_CONSOLIDADO
from concursos.correcao import ARQUIVO_QUESTOES, TOPICO_NAO_MAPEADO
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO

logger = logging.getLogger(__name__)

ARQUIVO_INDICE = 'index.html'
ARQUIVO_RELATORIO_HTML = 'relatorio.html'
_SELOS = {
    'edital': ('regra do edital', 'ok'),
    'config': ('regra do concurso.yaml', 'info'),
    'perfil': ('regra do perfil da banca', 'atencao'),
    'default': ('regra padrão', 'alerta'),
}
_NIVEIS_DO_EDITAL = {
    'alta': ('edital: alta', 'ok'),
    'media': ('edital: média', 'info'),
    'baixa': ('edital: baixa', 'atencao'),
    'minima': ('edital: mínima', 'alerta'),
}
_ORIGEM_DO_CAMPO = {'perfil': 'perfil da banca', 'default': 'padrão', 'llm': 'LLM, com trecho do edital'}
_SEVERIDADES_NO_RELATORIO = ('error', 'warn')
_CSS = """
body { font-family: system-ui, sans-serif; margin: 0; color: #1f2933; background: #f7f8fa; }
main { max-width: 64rem; margin: 0 auto; padding: 1.5rem; background: #fff; }
h1, h2, h3 { line-height: 1.25; }
table { border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
th, td { border: 1px solid #d5dae1; padding: 0.3rem 0.6rem; text-align: left; vertical-align: top; }
th { background: #eef1f5; }
img { max-width: 100%; height: auto; }
code { background: #eef1f5; padding: 0 0.2rem; }
.selo { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 0.8rem; font-size: 0.8rem; }
.ok { background: #d8f3dc; } .info { background: #dbeafe; }
.atencao { background: #fef3c7; } .alerta { background: #fde2e1; }
footer { margin-top: 2rem; color: #616e7c; font-size: 0.8rem; }
"""


@dataclass(frozen=True)
class ConcursoNoIndice:
    nome: str
    total: int
    acertos: int
    percentual: float
    fonte: str | None
    confianca: float | None
    data_prova: str | None
    nivel_edital: str | None


def gerar_relatorio_html(
    raiz_provas: Path, raiz_analises: Path, arquivo_taxonomia: Path, limiar_topico_baixo: float
) -> Path:
    """Grava o `index.html` em `raiz_analises` (a pasta do candidato) e um `relatorio.html` ao lado de cada
    `relatorio.md`. Gera também o relatório de evolução, quando há concursos suficientes."""
    pastas = sorted(
        p.parent for p in raiz_analises.glob('*/relatorio.md') if p.parent.name != PASTA_CONSOLIDADO
    )
    for pasta in pastas:
        markdown = (pasta / 'relatorio.md').read_text(encoding='utf-8')
        corpo = f'<p><a href="../{ARQUIVO_INDICE}">← todos os concursos</a></p>\n{_html(markdown)}'
        (pasta / ARQUIVO_RELATORIO_HTML).write_text(_pagina(pasta.name, corpo), encoding='utf-8')
    concursos = [_resumo(pasta) for pasta in pastas]
    corpo = '\n'.join(
        [
            f'<h1>Relatório de {escape(raiz_analises.name)}</h1>',
            '<h2>Concursos</h2>',
            _tabela_de_concursos(concursos),
            '<h2>O que o app decidiu sozinho</h2>',
            _lista([texto for pasta in pastas for texto in _decisoes(pasta)], 'Nenhuma decisão automática.'),
            '<h2>Avisos</h2>',
            _lista([texto for pasta in pastas for texto in _avisos(pasta)], 'Nenhum aviso.'),
            '<h2>Evolução</h2>',
            _evolucao(raiz_provas, raiz_analises, arquivo_taxonomia, limiar_topico_baixo),
            f'<footer>Gerado por concurso-analise {_versao()} em {datetime.now():%Y-%m-%d %H:%M} a partir de '
            f'{escape(str(raiz_provas))}.</footer>',
        ]
    )
    indice = raiz_analises / ARQUIVO_INDICE
    indice.write_text(_pagina(f'Relatório de {raiz_analises.name}', corpo), encoding='utf-8')
    logger.info('Relatório HTML gravado em %s', indice)
    return indice


def abrir_no_navegador(caminho: Path) -> None:
    """No navegador padrão; no WSL, no do Windows. Em CI, não abre."""
    if os.environ.get('CI'):
        return
    if _no_wsl():
        if shutil.which('wslview'):
            subprocess.run(['wslview', str(caminho)], check=False)
            return
        if shutil.which('explorer.exe') and shutil.which('wslpath'):
            convertido = subprocess.run(
                ['wslpath', '-w', str(caminho)], capture_output=True, text=True, check=False
            )
            subprocess.run(['explorer.exe', convertido.stdout.strip()], check=False)
            return
    webbrowser.open(caminho.resolve().as_uri())


def _no_wsl() -> bool:
    if os.environ.get('WSL_DISTRO_NAME'):
        return True
    try:
        return 'microsoft' in Path('/proc/version').read_text(encoding='utf-8').lower()
    except OSError:
        return False


def _resumo(pasta: Path) -> ConcursoNoIndice:
    desempenho = pd.read_csv(pasta / 'desempenho_por_disciplina.csv', keep_default_na=False)
    total, acertos, anuladas = (int(desempenho[c].sum()) for c in ('total', 'acertos', 'anuladas'))
    validas = total - anuladas
    correcao = _correcao(pasta)
    return ConcursoNoIndice(
        nome=pasta.name,
        total=total,
        acertos=acertos,
        percentual=round(100 * (acertos - anuladas) / validas, 2) if validas > 0 else 0.0,
        fonte=correcao.get('fonte'),
        confianca=correcao.get('confianca'),
        data_prova=correcao.get('data_prova'),
        nivel_edital=(_json(pasta / ARQUIVO_EDITAL_ESTRUTURADO).get('confianca_edital') or {}).get('nivel'),
    )


def _tabela_de_concursos(concursos: list[ConcursoNoIndice]) -> str:
    if not concursos:
        return '<p>Nenhum concurso analisado.</p>'
    linhas = [
        '<table>',
        '<tr><th>Concurso</th><th>Data</th><th>Acertos</th><th>Percentual</th><th>Edital</th>'
        '<th>Correção</th></tr>',
    ]
    for concurso in concursos:
        rotulo, classe = _SELOS.get(concurso.fonte or '', ('sem regra de correção', 'alerta'))
        confianca = f' ({_numero(concurso.confianca, 2)})' if concurso.confianca is not None else ''
        nivel, classe_do_nivel = _NIVEIS_DO_EDITAL.get(concurso.nivel_edital or '', ('sem edital', 'info'))
        linhas.append(
            f'<tr><td><a href="{escape(concurso.nome)}/{ARQUIVO_RELATORIO_HTML}">{escape(concurso.nome)}</a></td>'
            f'<td>{escape(concurso.data_prova or "sem data")}</td>'
            f'<td>{concurso.acertos} de {concurso.total}</td>'
            f'<td>{_numero(concurso.percentual, 1)}%</td>'
            f'<td><span class="selo {classe_do_nivel}">{escape(nivel)}</span></td>'
            f'<td><span class="selo {classe}">{escape(rotulo)}{confianca}</span></td></tr>'
        )
    linhas.append('</table>')
    return '\n'.join(linhas)


def _decisoes(pasta: Path) -> list[str]:
    decisoes = []
    correcao = _correcao(pasta)
    regra = f'{correcao.get("modelo")}, fator {correcao.get("fator_penalidade", 0):g}'
    if correcao.get('fonte') == 'perfil':
        decisoes.append(
            f'regra de correção do perfil da banca ({regra}): o edital e o concurso.yaml não a trazem'
        )
    elif correcao.get('fonte') == 'default':
        decisoes.append(f'regra de correção padrão ({regra}): nenhuma fonte a traz')
    estruturado = _json(pasta / ARQUIVO_EDITAL_ESTRUTURADO)
    for campo, valor in (estruturado.get('prova') or {}).items():
        if valor.get('fonte') in _ORIGEM_DO_CAMPO and valor.get('valor') is not None:
            decisoes.append(f'{campo} da prova: {valor["valor"]} ({_ORIGEM_DO_CAMPO[valor["fonte"]]})')
    objetiva = (estruturado.get('cronograma') or {}).get('objetiva') or {}
    if objetiva.get('fonte') == 'llm' and objetiva.get('valor') is not None:
        decisoes.append(f'data da prova: {objetiva["valor"]} ({_ORIGEM_DO_CAMPO["llm"]})')
    questoes = pasta / ARQUIVO_QUESTOES
    if questoes.exists():
        tabela = pd.read_csv(questoes, keep_default_na=False)
        sugeridos = int(((tabela['topico'] != TOPICO_NAO_MAPEADO) & ~tabela['revisado'].astype(bool)).sum())
        if sugeridos:
            decisoes.append(
                f'{sugeridos} de {len(tabela)} questões com tópico sugerido por similaridade com o edital; '
                f'confira em provas/{pasta.name}/revisao/'
            )
    return [f'{pasta.name}: {texto}' for texto in decisoes]


def _avisos(pasta: Path) -> list[str]:
    avisos = [
        texto.removeprefix(f'{pasta.name}: ')
        for texto in _json(pasta / ARQUIVO_EDITAL_ESTRUTURADO).get('avisos') or []
    ]
    if not _correcao(pasta).get('data_prova'):
        avisos.append('sem data da prova; fica fora das análises de tendência')
    discrepancias = pasta / 'discrepancias_edital.csv'
    if discrepancias.exists():
        tabela = pd.read_csv(discrepancias, keep_default_na=False)
        for linha in tabela[tabela['severidade'].isin(_SEVERIDADES_NO_RELATORIO)].itertuples():
            avisos.append(
                f'{linha.item}: edital {linha.esperado_edital}, prova {linha.observado_prova} ({linha.severidade})'
            )
    respostas = pasta / 'respostas_extraidas.csv'
    if respostas.exists():
        revisar = int(pd.read_csv(respostas)['revisar'].astype(bool).sum())
        if revisar:
            avisos.append(
                f'{revisar} leituras da folha para revisar: corrija o respostas_extraidas.csv e rode '
                f'`concurso-analise analyze {pasta.name} --reuse-csv`'
            )
    return [f'{pasta.name}: {texto}' for texto in avisos]


def _evolucao(raiz_provas: Path, raiz_analises: Path, arquivo_taxonomia: Path, limiar: float) -> str:
    consolidado = carregar_consolidado(raiz_provas, raiz_analises, arquivo_taxonomia)
    if consolidado['concurso'].nunique() < MINIMO_CONCURSOS:
        return f'<p>A evolução precisa de pelo menos {MINIMO_CONCURSOS} concursos analisados.</p>'
    pasta = pasta_consolidado(raiz_analises)
    relatorio = gravar_relatorio_evolucao(consolidado, pasta, limiar)
    gap = comparar_percentual_e_gap(consolidado, cortes_por_concurso(regras_por_concurso(raiz_analises)))
    return '\n'.join(
        [
            _html(relatorio.read_text(encoding='utf-8'), base=f'{PASTA_CONSOLIDADO}/', nivel=1),
            '<h2>Gap para o corte</h2>',
            _tabela_de_gap(gap),
        ]
    )


def _tabela_de_gap(gap: pd.DataFrame) -> str:
    gap = gap.dropna(subset=['menor_gap_percentual'])
    if gap.empty:
        return '<p>Nenhum concurso com corte no edital.</p>'
    linhas = [
        '<table>',
        '<tr><th>Concurso</th><th>Percentual ponderado</th><th>Menor gap (p.p.)</th>'
        '<th>Corte mais distante</th><th>Atingido</th></tr>',
    ]
    for linha in gap.itertuples():
        nome = linha.concurso if pd.isna(linha.variante) else f'{linha.concurso} ({linha.variante})'
        linhas.append(
            f'<tr><td>{escape(str(nome))}</td><td>{_numero(linha.percentual_ponderado, 1)}%</td>'
            f'<td>{_numero(linha.menor_gap_percentual, 1)}</td><td>{escape(str(linha.corte_mais_distante))}</td>'
            f'<td>{"sim" if linha.atingido else "não"}</td></tr>'
        )
    linhas.append('</table>')
    return '\n'.join(linhas)


def _html(markdown: str, base: str = '', nivel: int = 0) -> str:
    """Markdown em HTML, sem HTML bruto do texto (que vem de PDFs); imagens relativas ganham `base` e os
    títulos descem `nivel` níveis."""
    conversor = MarkdownIt('commonmark', {'html': False}).enable('table')
    tokens = conversor.parse(markdown)
    for token in tokens:
        if token.type in ('heading_open', 'heading_close') and nivel:
            token.tag = f'h{min(6, int(token.tag[1]) + nivel)}'
        for filho in token.children or []:
            src = filho.attrGet('src') if filho.type == 'image' else None
            if src and base and not src.startswith(('/', '#')) and ':' not in src:
                filho.attrSet('src', base + src)
    return conversor.renderer.render(tokens, conversor.options, {})


def _pagina(titulo: str, corpo: str) -> str:
    return (
        '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{escape(titulo)}</title>\n<style>{_CSS}</style>\n</head>\n'
        f'<body>\n<main>\n{corpo}\n</main>\n</body>\n</html>\n'
    )


def _lista(itens: list[str], vazio: str) -> str:
    if not itens:
        return f'<p>{escape(vazio)}</p>'
    return '<ul>\n' + '\n'.join(f'<li>{escape(item)}</li>' for item in itens) + '\n</ul>'


def _correcao(pasta: Path) -> dict:
    configuracoes = _json(pasta / 'correcao.json')
    return configuracoes[0] if isinstance(configuracoes, list) and configuracoes else {}


def _json(caminho: Path) -> dict | list:
    return json.loads(caminho.read_text(encoding='utf-8')) if caminho.exists() else {}


def _numero(valor: float, casas: int) -> str:
    return f'{valor:.{casas}f}'.replace('.', ',')


def _versao() -> str:
    try:
        return version('concurso-analise')
    except PackageNotFoundError:
        return 'desconhecida'
