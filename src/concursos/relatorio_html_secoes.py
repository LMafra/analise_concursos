"""Relatório HTML por candidato: o painel de gestão (`index.html`) e um HTML por relatório markdown, sem
rede. O vocabulário segue `docs/specs/spec-linguagem.md`; o técnico fica no apêndice "Detalhes técnicos"."""

import json
import logging
import os
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from html import escape
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pandas as pd
from markdown_it import MarkdownIt

from concursos.agregacao import percentual_de_merito
from concursos.analytics.consolidado import (
    N_MINIMO_TOPICO,
    carregar_consolidado,
    cortes_por_concurso,
    pasta_consolidado,
    regras_por_concurso,
)
from concursos.analytics.correcao import ARQUIVO_CORRECAO, NotaFinal, notas_pela_regra_gravadas
from concursos.analytics.evolucao import MINIMO_PONTOS_TENDENCIA, comparar_percentual_e_gap
from concursos.analytics.insights import (
    IMAGEM_HEATMAP,
    IMAGEM_LINHA,
    IMAGEM_PAINEL,
    calcular_achados,
    gravar_relatorio_evolucao,
)
from concursos.analytics.nome_concurso import NomeDoConcurso, nome_do_concurso
from concursos.analytics.painel import (
    FAIXA_NO_LIMITE,
    FontesDasAcoes,
    Painel,
    Prova,
    ha_amostra_por_disciplina,
    montar_painel,
    topicos_por_impacto,
)
from concursos.analytics.regras_edital import UnidadeCorte
from concursos.analytics.validacao_edital import ARQUIVO_DISCREPANCIAS
from concursos.analytics.visualizacao import rotulo_com_variante
from concursos.artefatos import ARQUIVO_RESPOSTAS
from concursos.biblioteca import ARQUIVO_RECOMENDACOES
from concursos.concurso_config import ARQUIVO_CONFIG, carregar_concurso, ler_dados
from concursos.consolidado import MINIMO_CONCURSOS, PASTA_CONSOLIDADO
from concursos.correcao import ARQUIVO_QUESTOES, TOPICO_NAO_MAPEADO
from concursos.datas import data_br
from concursos.design_tokens import css_root_do_relatorio
from concursos.edital import ARQUIVO_EDITAL_ESTRUTURADO
from concursos.integracoes.radar_pci import ARQUIVO_RADAR
from concursos.linguagem import SELOS, percentual, plural, traduzir_aviso
from concursos.pratica_tec import ARQUIVO_RESUMO, PASTA_PRATICA
from concursos.relatorio import TITULO_DETALHES_TECNICOS
from concursos.resultado_oficial import formatar
from concursos.simulado_focado import ARQUIVO_SIMULADO_FOCADO
from concursos.texto import abreviar

logger = logging.getLogger(__name__)

ARQUIVO_INDICE = 'index.html'
ARQUIVO_CONCURSOS = 'concursos.html'
ARQUIVO_TEC = 'tec.html'
ARQUIVO_SIMULADOS = 'simulados.html'
ARQUIVO_RELATORIO_HTML = 'relatorio.html'
_SELOS_DA_CORRECAO = {
    'edital': ('regra do edital', 'ok'),
    'config': ('regra do cadastro', 'info'),
    'perfil': ('regra padrão da banca', 'atencao'),
    'default': ('regra padrão', 'alerta'),
}
_NIVEIS_DO_EDITAL = {
    'alta': ('edital: alta', 'ok'),
    'media': ('edital: média', 'info'),
    'baixa': ('edital: baixa', 'atencao'),
    'minima': ('edital: mínima', 'alerta'),
}
_ORIGEM_DO_CAMPO = {'perfil': 'perfil da banca', 'default': 'padrão', 'llm': 'LLM, com trecho do edital'}
_ORIGEM_LEIGA = {
    'perfil': 'pela regra padrão da banca',
    'default': 'por um valor padrão',
    'llm': 'pela inteligência artificial, com o trecho do edital',
}
_SEVERIDADES_NO_RELATORIO = ('error', 'warn')
_FIGURAS = (
    (
        IMAGEM_LINHA,
        'Gráfico: seu desempenho em cada disciplina, acima ou abaixo da sua média, concurso a concurso.',
        'Cada ponto é um concurso. Linha subindo = melhora; linha descendo = piora. Só aparecem disciplinas '
        f'com pelo menos {MINIMO_PONTOS_TENDENCIA} concursos.',
    ),
    (
        IMAGEM_HEATMAP,
        'Gráfico: como você foi em cada tópico, por concurso.',
        'Vermelho = abaixo do esperado; verde = acima. Cada coluna é um concurso.',
    ),
    (
        IMAGEM_PAINEL,
        'Gráfico: sua nota com e sem a regra de correção e o chute.',
        'Mostra como a sua posição entre os concursos muda quando consideramos a regra de correção e o chute.',
    ),
)


def _css_do_relatorio() -> str:
    return f"""
{css_root_do_relatorio()}
body {{ font-family: var(--font-family-body); margin: 0; color: var(--color-text-main);
  background: var(--color-bg-base); }}
main {{ max-width: 64rem; margin: 0 auto; padding: var(--space-lg); background: var(--color-bg-surface); }}
h1, h2, h3 {{ line-height: 1.25; color: var(--color-text-main); }}
table {{ border-collapse: collapse; margin: var(--space-md) 0; font-size: 0.9rem; }}
caption {{ text-align: left; color: var(--color-text-muted); font-size: 0.85rem;
  padding-bottom: 0.3rem; }}
th, td {{ border: 1px solid var(--color-border); padding: 0.3rem 0.6rem; text-align: left;
  vertical-align: top; }}
th {{ background: var(--color-bg-base); }}
img {{ max-width: 100%; height: auto; }}
figure {{ margin: var(--space-lg) 0; }}
figcaption {{ color: var(--color-text-muted); font-size: 0.85rem; }}
code {{ background: var(--color-bg-base); padding: 0 0.2rem; }}
a {{ color: var(--color-primary); }}
nav ul {{ list-style: none; padding: 0; display: flex; flex-wrap: wrap;
  gap: var(--space-xs) var(--space-md); }}
.resumo {{ font-size: 1.05rem; }}
.diagnostico {{ display: grid; grid-template-columns: 1fr auto; gap: var(--space-md);
  align-items: start; border: 1px solid var(--color-border); border-radius: var(--radius-md);
  padding: var(--space-md); margin: var(--space-md) 0; background: var(--color-bg-surface);
  box-shadow: var(--shadow-sm); }}
.diagnostico-meta {{ display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-sm);
  margin-bottom: var(--space-xs); }}
.diagnostico-titulo {{ margin: 0; font-size: 1.15rem; }}
.diagnostico-frase {{ margin: var(--space-xs) 0 0; color: var(--color-text-muted); }}
.diagnostico-margem {{ text-align: right; min-width: 8rem; }}
.diagnostico-margem-rotulo {{ display: block; color: var(--color-text-muted); font-size: 0.8rem; }}
.diagnostico-margem-valor {{ display: block; font-size: 1.35rem; font-weight: 600; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: var(--space-sm); margin: var(--space-lg) 0; }}
.card {{ border: 1px solid var(--color-border); border-radius: var(--radius-md);
  padding: var(--space-sm); box-shadow: var(--shadow-sm); }}
.card p {{ margin: 0; }}
.card-rotulo {{ color: var(--color-text-muted); font-size: 0.85rem; }}
.card-valor {{ font-size: 1.6rem; font-weight: 600; margin: 0.2rem 0; }}
.card-contexto {{ color: var(--color-text-muted); font-size: 0.85rem; }}
.corte-medidor {{ margin-top: var(--space-sm); }}
.corte-trilha {{ position: relative; height: 0.55rem; border-radius: var(--radius-pill);
  background: var(--color-bg-base); border: 1px solid var(--color-border); overflow: hidden; }}
.corte-faixa {{ position: absolute; top: 0; bottom: 0; width: 0.35rem;
  background: var(--color-text-muted); opacity: 0.7; }}
.corte-preenchimento {{ height: 100%; border-radius: var(--radius-pill); }}
.corte-preenchimento[data-status="acima"] {{ background: var(--color-status-pass); }}
.corte-preenchimento[data-status="limite"] {{ background: var(--color-status-warn); }}
.corte-preenchimento[data-status="abaixo"] {{ background: var(--color-status-alert); }}
.corte-preenchimento[data-status="neutro"] {{ background: var(--color-text-muted); }}
.selo {{ display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.15rem 0.55rem;
  font-size: 0.8rem; font-weight: 500; }}
.ok {{ background: var(--color-status-pass-bg); color: var(--color-status-pass); }}
.info {{ background: var(--color-bg-base); color: var(--color-text-main); }}
.atencao {{ background: var(--color-status-warn-bg); color: var(--color-status-warn); }}
.alerta {{ background: var(--color-status-alert-bg); color: var(--color-status-alert); }}
.selo-acima {{ background: var(--color-status-pass-bg); color: var(--color-status-pass);
  border-radius: var(--radius-pill); }}
.selo-limite {{ background: var(--color-status-warn-bg); color: var(--color-status-warn);
  border-radius: var(--radius-sm); border: 1px dashed var(--color-status-warn); }}
.selo-abaixo {{ background: var(--color-status-alert-bg); color: var(--color-status-alert);
  border-radius: 2px; border: 2px solid var(--color-status-alert); }}
.selo-neutro {{ background: var(--color-bg-base); color: var(--color-text-muted);
  border-radius: var(--radius-sm); }}
.atalhos {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: var(--space-sm); margin: var(--space-lg) 0; }}
.atalho {{ border: 1px solid var(--color-border); border-radius: var(--radius-md);
  padding: var(--space-md); }}
details {{ margin-top: var(--space-lg); border-top: 1px solid var(--color-border); padding-top: 0.5rem; }}
summary {{ cursor: pointer; }}
summary h2, summary h3 {{ display: inline; }}
footer {{ margin-top: var(--space-lg); color: var(--color-text-muted); font-size: 0.8rem; }}
.nota {{ color: var(--color-text-muted); font-size: 0.85rem; }}
.dashboard {{ margin: var(--space-lg) 0 var(--space-xl); }}
.dashboard-grade {{ display: grid; grid-template-columns: 1fr; gap: var(--space-md); }}
@media (min-width: 900px) {{
  .dashboard-grade {{ grid-template-columns: 1fr 1fr 1fr; }}
}}
.sub-dashboard {{ border: 1px solid var(--color-border); border-radius: var(--radius-md);
  padding: var(--space-md); box-shadow: var(--shadow-sm); }}
.sub-dashboard h3 {{ margin: 0 0 var(--space-sm); font-size: 1rem; }}
.sub-dashboard .kpis {{ display: flex; flex-direction: column; gap: var(--space-sm); }}
.sub-dashboard a.kpi {{ display: flex; flex-direction: column; gap: 0.15rem; text-decoration: none;
  color: inherit; padding: var(--space-sm); border-radius: var(--radius-sm);
  border: 1px solid transparent; }}
.sub-dashboard a.kpi:hover, .sub-dashboard a.kpi:focus-visible {{
  border-color: var(--color-border); background: var(--color-bg-base); }}
.sub-dashboard a.kpi strong {{ font-size: 0.8rem; color: var(--color-text-muted); font-weight: 500; }}
.sub-dashboard a.kpi > span {{ font-size: 1.05rem; font-weight: 600; }}
@media print {{
  .dashboard-grade {{ grid-template-columns: 1fr 1fr 1fr; }}
}}

@media (max-width: 36rem) {{
  .diagnostico {{ grid-template-columns: 1fr; }}
  .diagnostico-margem {{ text-align: left; }}
}}
@media print {{
  body {{ background: #FFFFFF; color: #111111; }}
  main {{ max-width: none; box-shadow: none; }}
  nav, .atalhos {{ display: none; }}
  a {{ color: inherit; text-decoration: none; }}
}}
"""


_CSS = _css_do_relatorio()


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
    notas: tuple[NotaFinal, ...] = ()
    nome_mostrado: NomeDoConcurso | None = None

    @property
    def titulo(self) -> str:
        return self.nome_mostrado.titulo if self.nome_mostrado else self.nome


@dataclass(frozen=True)
class Observacao:
    """Uma decisão automática ou um aviso: o texto leigo e, junto, o técnico de onde ele saiu."""

    concurso: str
    texto: str | None
    detalhe: str


@dataclass(frozen=True)
class _SecaoPropria:
    ancora: str
    titulo: str
    html: str


def _gravar_html_por_concurso(pastas: list[Path]) -> None:
    for pasta in pastas:
        markdown = (pasta / 'relatorio.md').read_text(encoding='utf-8')
        corpo = f'<p><a href="../{ARQUIVO_INDICE}">← todos os concursos</a></p>\n{_relatorio_do_concurso(markdown)}'
        (pasta / ARQUIVO_RELATORIO_HTML).write_text(_pagina(pasta.name, corpo), encoding='utf-8')


def _fontes_do_painel(raiz_analises: Path, pastas: list[Path]) -> FontesDasAcoes:
    return FontesDasAcoes(
        simulado_focado=_existe(raiz_analises / ARQUIVO_SIMULADO_FOCADO),
        recomendacoes=_existe(raiz_analises / PASTA_CONSOLIDADO / ARQUIVO_RECOMENDACOES),
        radar=_existe(raiz_analises / ARQUIVO_RADAR),
        pratica=_existe(raiz_analises / PASTA_PRATICA / ARQUIVO_RESUMO),
        leituras_a_conferir=sum(_leituras_a_conferir(pasta) for pasta in pastas),
        topicos_a_conferir=sum(_topicos_sugeridos(pasta)[0] for pasta in pastas),
    )


def _metas_dashboard(raiz_provas: Path):
    from concursos.analytics.dashboard_fontes import metas_do_toml, metas_padrao
    from concursos.config.contexto import ler_toml

    for caminho in (
        raiz_provas.parent / 'config.toml',
        raiz_provas.parent / '.concurso' / 'config.toml',
        raiz_provas.parent / '.gabarito-vivo' / 'config.toml',
    ):
        if caminho.is_file():
            return metas_do_toml(ler_toml(caminho))
    return metas_padrao()


def _registros_simulados(raiz_provas: Path, pastas: list[Path], simulados: dict):
    from concursos.analytics.dashboard_fontes import RegistroSimulado

    regs = []
    for pasta in pastas:
        if not simulados.get(pasta.name):
            continue
        resumo = _resumo(pasta, raiz_provas / pasta.name)
        regs.append(
            RegistroSimulado(
                resumo.titulo,
                'PCI',
                resumo.percentual,
                resumo.data_prova or '',
            )
        )
    return regs


def _corpo_dashboard(
    raiz_analises: Path, raiz_provas: Path, pastas: list[Path], simulados: dict, painel: Painel
) -> str:
    from concursos.analytics.dashboard_fontes import (
        html_dashboard,
        kpis_concursos,
        kpis_simulados,
        kpis_tec,
    )

    metas = _metas_dashboard(raiz_provas)
    return html_dashboard(
        [
            kpis_concursos(painel.provas, destino_base=ARQUIVO_CONCURSOS),
            kpis_tec(raiz_analises, metas, destino_base=ARQUIVO_TEC),
            kpis_simulados(
                _registros_simulados(raiz_provas, pastas, simulados),
                metas,
                destino_base=ARQUIVO_SIMULADOS,
            ),
        ]
    )


def _corpo_concursos(
    raiz_analises: Path,
    raiz_provas: Path,
    pastas: list[Path],
    simulados: dict,
    concursos: list,
    painel: Painel,
    suficiente: bool,
    consolidado: pd.DataFrame,
    secoes: list,
    decisoes: list,
    gap: pd.DataFrame,
    evolucao_tecnica,
) -> str:
    agora = datetime.now()
    return '\n'.join(
        [
            f'<p><a href="{ARQUIVO_INDICE}">← Painel inicial</a></p>',
            f'<h1 id="lista">Concursos — {escape(raiz_analises.name)}</h1>',
            f'<p class="nota">Situação em {agora:%d/%m/%Y}'
            f' · {escape(plural(painel.kpis.concursos, "concurso"))}</p>',
            f'<p class="resumo">{escape(painel.resumo)}</p>',
            f'<div id="ultima-prova">{_diagnostico_ultima_prova(painel)}</div>',
            _cards(painel, suficiente),
            *_o_que_fazer(painel),
            _navegacao(secoes),
            *_como_estou_saindo(painel, concursos),
            *_pontos_fortes(painel, consolidado),
            *_pontos_a_melhorar(painel, suficiente),
            f'<div id="evolucao">{"".join(_estou_evoluindo(painel, suficiente))}</div>',
            _atalhos_das_secoes(secoes),
            _detalhes_tecnicos(
                concursos,
                decisoes,
                [o for pasta in pastas for o in _avisos(pasta)],
                gap,
                evolucao_tecnica,
            ),
            f'<footer>Relatório gerado localmente pelo aplicativo Gabarito Vivo {_versao()} em '
            f'{agora:%d/%m/%Y %H:%M}.</footer>',
        ]
    )


def gerar_relatorio_html(
    raiz_provas: Path, raiz_analises: Path, arquivo_taxonomia: Path, limiar_topico_baixo: float
) -> Path:
    """Grava o `index.html` em `raiz_analises` (a pasta do candidato) e um `relatorio.html` ao lado de cada
    `relatorio.md`. Gera também o relatório de evolução, quando há concursos suficientes."""
    pastas = sorted(
        p.parent for p in raiz_analises.glob('*/relatorio.md') if p.parent.name != PASTA_CONSOLIDADO
    )
    _gravar_html_por_concurso(pastas)
    simulados = {pasta.name: _simulado(raiz_provas / pasta.name) for pasta in pastas}
    concursos = [_resumo(pasta, raiz_provas / pasta.name) for pasta in pastas if not simulados[pasta.name]]
    consolidado = carregar_consolidado(raiz_provas, raiz_analises, arquivo_taxonomia)
    cortes = cortes_por_concurso(regras_por_concurso(raiz_analises))
    gap = comparar_percentual_e_gap(consolidado, cortes) if not consolidado.empty else pd.DataFrame()
    suficiente = not consolidado.empty and consolidado['concurso'].nunique() >= MINIMO_CONCURSOS
    achados = calcular_achados(consolidado, limiar_topico_baixo) if suficiente else None
    evolucao_tecnica = (
        gravar_relatorio_evolucao(
            consolidado, pasta_consolidado(raiz_analises), limiar_topico_baixo, achados=achados
        )
        if achados
        else None
    )
    secoes = _secoes_proprias(raiz_analises)
    decisoes = [o for pasta in pastas for o in _decisoes(pasta, raiz_provas / pasta.name)]
    painel = montar_painel(
        _provas(concursos, gap, cortes),
        consolidado,
        achados.fracos if achados else pd.DataFrame(),
        achados.tendencias if achados else pd.DataFrame(),
        achados.correlacao_geral if achados else None,
        limiar_topico_baixo,
        _fontes_do_painel(raiz_analises, pastas),
    )
    dash = _corpo_dashboard(raiz_analises, raiz_provas, pastas, simulados, painel)
    corpo_concursos = _corpo_concursos(
        raiz_analises,
        raiz_provas,
        pastas,
        simulados,
        concursos,
        painel,
        suficiente,
        consolidado,
        secoes,
        decisoes,
        gap,
        evolucao_tecnica,
    )
    indice = raiz_analises / ARQUIVO_INDICE
    indice.write_text(_pagina(f'Painel — {raiz_analises.name}', dash), encoding='utf-8')
    (raiz_analises / ARQUIVO_CONCURSOS).write_text(
        _pagina(f'Concursos — {raiz_analises.name}', corpo_concursos), encoding='utf-8'
    )
    _gravar_tec_e_simulados(raiz_analises, raiz_provas, pastas, simulados, painel, suficiente)
    logger.info(
        'Relatório HTML gravado em %s (+ %s, %s, %s)',
        indice,
        ARQUIVO_CONCURSOS,
        ARQUIVO_TEC,
        ARQUIVO_SIMULADOS,
    )
    return indice


def _gravar_tec_e_simulados(
    raiz_analises: Path,
    raiz_provas: Path,
    pastas: list[Path],
    simulados: dict,
    painel: Painel,
    suficiente: bool,
) -> None:
    from concursos.analytics.dashboard_fontes import kpis_tec
    from concursos.pratica.constantes import ARQUIVO_RESPOSTAS, PASTA_PRATICA

    metas = _metas_dashboard(raiz_provas)
    sub = kpis_tec(raiz_analises, metas)
    linhas_tec = [
        f'<p><a href="{ARQUIVO_INDICE}">← Painel inicial</a></p>',
        '<h1 id="gargalo">Prática no TEC</h1>',
        '<p class="nota">Agrupado por matéria → assunto. Caderno é filtro opcional na GUI.</p>',
    ]
    if sub.vazio:
        linhas_tec.append(f'<p>{escape(sub.vazio)}</p>')
    else:
        linhas_tec.append('<ul>')
        for kpi in sub.kpis:
            linhas_tec.append(f'<li><strong>{escape(kpi.rotulo)}</strong>: {escape(kpi.valor)}</li>')
        linhas_tec.append('</ul>')
        csv_path = raiz_analises / PASTA_PRATICA / ARQUIVO_RESPOSTAS
        if csv_path.is_file():
            df = pd.read_csv(csv_path, keep_default_na=False)
            if {'mat', 'ass', 'resultado'}.issubset(df.columns):
                linhas_tec.append(
                    '<table id="banca"><thead><tr><th>Matéria</th><th>Assunto</th><th>Acertos</th>'
                    '<th>Erros</th><th>n</th></tr></thead><tbody>'
                )
                for (mat, ass), g in df.groupby(['mat', 'ass'], dropna=False):
                    a = int((g['resultado'] == 'acerto').sum())
                    e = int((g['resultado'] == 'erro').sum())
                    linhas_tec.append(
                        f'<tr><td>{escape(str(mat))}</td><td>{escape(str(ass))}</td>'
                        f'<td>{a}</td><td>{e}</td><td>{len(g)}</td></tr>'
                    )
                linhas_tec.append('</tbody></table>')
    if suficiente and painel.grupos:
        topicos = topicos_por_impacto(painel.grupos)
        if topicos:
            linhas_tec.append('<h2>Tópicos fracos nas provas (contexto)</h2><ul>')
            for t in topicos[:10]:
                linhas_tec.append(f'<li>{escape(t.disciplina)} — {escape(abreviar(t.topico, 80))}</li>')
            linhas_tec.append('</ul>')
    (raiz_analises / ARQUIVO_TEC).write_text(
        _pagina('Prática no TEC', '\n'.join(linhas_tec)), encoding='utf-8'
    )

    regs = _registros_simulados(raiz_provas, pastas, simulados)
    linhas_sim = [
        f'<p><a href="{ARQUIVO_INDICE}">← Painel inicial</a></p>',
        '<h1 id="ultimo">Simulados</h1>',
        '<p class="nota">PCI e TEC misturados por propósito (treino sob pressão).</p>',
    ]
    from concursos.analytics.dashboard_fontes import EMPTY_SIMULADOS

    if not regs:
        linhas_sim.append(f'<p>{escape(EMPTY_SIMULADOS)}</p>')
    else:
        linhas_sim.append(
            '<table id="evolucao"><thead><tr><th>Nome</th><th>Origem</th>'
            '<th>Acertos</th><th>Data</th></tr></thead><tbody>'
        )
        for r in sorted(regs, key=lambda x: x.data, reverse=True):
            linhas_sim.append(
                f'<tr><td>{escape(r.nome)}</td><td>{escape(r.origem)}</td>'
                f'<td>{percentual(r.percentual)}</td><td>{escape(r.data)}</td></tr>'
            )
        linhas_sim.append('</tbody></table>')
        linhas_sim.append(
            '<p id="gargalo" class="nota">Gargalos por assunto: use a GUI Estudar / Simulado.</p>'
        )
    # tabela de simulados já usada no índice antigo
    tabela = _tabela_de_simulados(
        [
            (_resumo(pasta, raiz_provas / pasta.name), simulados[pasta.name])
            for pasta in pastas
            if simulados.get(pasta.name)
        ]
    )
    if tabela:
        linhas_sim.extend(tabela)
    (raiz_analises / ARQUIVO_SIMULADOS).write_text(
        _pagina('Simulados', '\n'.join(linhas_sim)), encoding='utf-8'
    )


def abrir_no_navegador(caminho: Path | str) -> None:
    """Um arquivo, ou um endereço (str), no navegador padrão; no WSL, no do Windows. Em CI, não abre."""
    if os.environ.get('CI'):
        return
    endereco = caminho if isinstance(caminho, str) else None
    if _no_wsl():
        if shutil.which('wslview'):
            subprocess.run(['wslview', str(caminho)], check=False)
            return
        if endereco and shutil.which('explorer.exe'):
            subprocess.run(['explorer.exe', endereco], check=False)
            return
        if shutil.which('explorer.exe') and shutil.which('wslpath'):
            convertido = subprocess.run(
                ['wslpath', '-w', str(caminho)], capture_output=True, text=True, check=False
            )
            subprocess.run(['explorer.exe', convertido.stdout.strip()], check=False)
            return
    webbrowser.open(endereco or Path(caminho).resolve().as_uri())


def _no_wsl() -> bool:
    if os.environ.get('WSL_DISTRO_NAME'):
        return True
    try:
        return 'microsoft' in Path('/proc/version').read_text(encoding='utf-8').lower()
    except OSError:
        return False


def _relatorio_do_concurso(markdown: str) -> str:
    """Tudo a partir de `## Detalhes técnicos` vai para um `<details>` fechado."""
    marcador = f'\n## {TITULO_DETALHES_TECNICOS}\n'
    principal, separador, tecnico = markdown.partition(marcador)
    if not separador:
        return _html(markdown)
    return (
        f'{_html(principal)}\n<details>\n<summary><h2>{TITULO_DETALHES_TECNICOS}</h2></summary>\n'
        f'{_html(tecnico)}\n</details>'
    )


def _resumo(pasta: Path, pasta_provas: Path) -> ConcursoNoIndice:
    desempenho = pd.read_csv(pasta / 'desempenho_por_disciplina.csv', keep_default_na=False)
    somas = desempenho[['total', 'acertos', 'anuladas']].sum().to_frame().T
    correcao = _correcao(pasta)
    notas = ()
    estruturado = _json(pasta / ARQUIVO_EDITAL_ESTRUTURADO)
    nome = None
    if (pasta_provas / ARQUIVO_CONFIG).exists():
        config = carregar_concurso(pasta_provas)
        notas = tuple(notas_pela_regra_gravadas(pasta, config.formato))
        nome = nome_do_concurso(config, estruturado.get('identificacao'))
    return ConcursoNoIndice(
        nome=pasta.name,
        total=int(somas['total'].iloc[0]),
        acertos=int(somas['acertos'].iloc[0]),
        percentual=float(percentual_de_merito(somas).iloc[0]),
        fonte=correcao.get('fonte'),
        confianca=correcao.get('confianca'),
        data_prova=correcao.get('data_prova'),
        nivel_edital=(estruturado.get('confianca_edital') or {}).get('nivel'),
        notas=notas,
        nome_mostrado=nome,
    )


def _mapa_gaps(gap: pd.DataFrame) -> dict:
    return {
        (linha.concurso, _variante(linha.variante)): (linha.menor_gap_percentual, linha.atingido)
        for linha in (gap.itertuples() if not gap.empty else ())
    }


def _prova_de_nota(concurso: ConcursoNoIndice, nota, gaps: dict, calculavel: bool) -> Prova:
    variante = _variante(nota.variante) if nota else None
    valor, atingido = gaps.get((concurso.nome, variante), (None, None))
    return Prova(
        concurso=concurso.nome,
        titulo=concurso.titulo,
        percentual=nota.percentual if nota else concurso.percentual,
        variante=variante,
        data=concurso.data_prova,
        gap=None if valor is None or pd.isna(valor) else float(valor),
        atingido=None if atingido is None or pd.isna(atingido) else bool(atingido),
        corte_calculavel=calculavel,
    )


def _provas(
    concursos: list[ConcursoNoIndice], gap: pd.DataFrame, cortes: dict[str, list[dict]]
) -> list[Prova]:
    """Uma prova por opção de cargo; o gap vem de `comparar_percentual_e_gap`, pela mesma variante."""
    gaps = _mapa_gaps(gap)
    provas = []
    for concurso in concursos:
        objetivos = [c for c in cortes.get(concurso.nome) or [] if c.get('escopo') != 'discursiva']
        calculavel = not objetivos or any(_calculavel(c) for c in objetivos)
        for nota in concurso.notas or (None,):
            provas.append(_prova_de_nota(concurso, nota, gaps, calculavel))
    return provas


def _calculavel(corte: dict) -> bool:
    try:
        return UnidadeCorte(corte.get('unidade')).calculavel
    except ValueError:
        return True


def _variante(valor) -> str | None:
    return (
        None if valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor == '' else str(valor)
    )


def _navegacao(secoes: list[_SecaoPropria]) -> str:
    destinos = [
        ('o-que-fazer', 'O que fazer agora'),
        ('como-estou-saindo', 'Como estou saindo'),
        ('pontos-fortes', 'Pontos fortes'),
        ('pontos-a-melhorar', 'Pontos a melhorar'),
        ('evolucao', 'Estou evoluindo?'),
        *((s.ancora, s.titulo) for s in secoes),
        ('detalhes-tecnicos', TITULO_DETALHES_TECNICOS),
    ]
    itens = '\n'.join(f'<li><a href="#{ancora}">{escape(titulo)}</a></li>' for ancora, titulo in destinos)
    return f'<nav aria-label="Ir para">\n<p class="nota">Ir para:</p>\n<ul>\n{itens}\n</ul>\n</nav>'


def _ultima_prova(painel: Painel) -> Prova | None:
    if not painel.provas:
        return None
    com_data = [p for p in painel.provas if p.data]
    if com_data:
        return max(com_data, key=lambda p: p.data or '')
    return painel.provas[-1]


def _diagnostico_ultima_prova(painel: Painel) -> str:
    prova = _ultima_prova(painel)
    if prova is None:
        return (
            '<section class="diagnostico" aria-label="Diagnóstico">'
            '<p>Cadastre e analise uma prova para ver o diagnóstico.</p></section>'
        )
    margem = (
        f'<div class="diagnostico-margem">'
        f'<span class="diagnostico-margem-rotulo">Margem para o corte</span>'
        f'<span class="diagnostico-margem-valor">{escape(prova.quanto_falta)}</span></div>'
        if prova.quanto_falta
        else ''
    )
    frase = f'Nota {escape(percentual(prova.percentual))} na última prova analisada.'
    return (
        f'<section class="diagnostico" aria-label="Diagnóstico da última prova" aria-live="polite">'
        f'<div><div class="diagnostico-meta">{_selo(prova)}</div>'
        f'<h2 class="diagnostico-titulo">{escape(prova.rotulo)}</h2>'
        f'<p class="diagnostico-frase">{frase}</p></div>{margem}</section>'
    )


def _cards(painel: Painel, suficiente: bool) -> str:
    del suficiente  # a tendência já comunica amostra insuficiente
    k = painel.kpis
    ultima = _ultima_prova(painel)
    if k.com_corte:
        status_valor = f'{k.acima} de {k.com_corte} acima'
        status_ctx = f'{k.abaixo} abaixo · {k.no_limite} no limite'
    else:
        status_valor = '–'
        status_ctx = 'nenhuma prova com corte no edital'
    tendencia = k.tendencia
    if ultima:
        nota_valor = escape(percentual(ultima.percentual))
        nota_ctx = escape(ultima.rotulo)
        nota_extra = _medidor_de_corte(ultima)
    else:
        nota_valor = '–'
        nota_ctx = 'nenhuma prova analisada'
        nota_extra = ''
    cards = [
        ('Situação no corte', escape(status_valor), escape(status_ctx), ''),
        (
            'Tendência',
            f'<span aria-hidden="true">{tendencia.icone}</span> {escape(tendencia.rotulo)}',
            escape(tendencia.frase),
            '',
        ),
        ('Nota da última prova', nota_valor, nota_ctx, nota_extra),
    ]
    return (
        '<section class="cards" aria-label="Indicadores principais">\n'
        + '\n'.join(
            f'<div class="card"><p class="card-rotulo">{rotulo}</p><p class="card-valor">{valor}</p>'
            f'<p class="card-contexto">{contexto}</p>{extra}</div>'
            for rotulo, valor, contexto, extra in cards
        )
        + '\n</section>'
    )


def _medidor_de_corte(prova: Prova) -> str:
    """Barra da nota com marca do corte; só visual — o texto do card e do banner já dizem o gap."""
    if prova.gap is None or pd.isna(prova.gap):
        return ''
    nota = max(0.0, min(100.0, float(prova.percentual)))
    corte = max(0.0, min(100.0, nota - float(prova.gap)))
    status = prova.status.value
    chave = status if status in {'acima', 'limite', 'abaixo'} else 'neutro'
    faixa = max(FAIXA_NO_LIMITE, 0.5)
    esquerda = max(0.0, corte - faixa)
    largura_faixa = min(100.0, corte + faixa) - esquerda
    aria = (
        f'Nota {percentual(nota)} frente ao corte em {percentual(corte)}; '
        f'{prova.quanto_falta or "sem margem"}.'
    )
    return (
        f'<div class="corte-medidor" role="img" aria-label="{escape(aria)}">'
        f'<div class="corte-trilha" aria-hidden="true">'
        f'<div class="corte-faixa" style="left: {esquerda:.1f}%; width: {largura_faixa:.1f}%"></div>'
        f'<div class="corte-preenchimento" data-status="{chave}" style="width: {nota:.1f}%"></div>'
        f'</div></div>'
    )


def _selo(prova: Prova) -> str:
    selo = SELOS[prova.status.value]
    return (
        f'<span class="selo {selo.classe}" role="status" aria-label="Situação: {escape(selo.rotulo)}">'
        f'<span aria-hidden="true">{selo.icone}</span> {escape(selo.rotulo)}</span>'
    )


def _como_estou_saindo(painel: Painel, concursos: list[ConcursoNoIndice]) -> list[str]:
    titulo = '<h2 id="como-estou-saindo">Como estou saindo</h2>'
    if not concursos:
        return [titulo, '<p>Nenhum concurso analisado.</p>']
    por_nome = {c.nome: c for c in concursos}
    linhas = [
        titulo,
        '<table>',
        '<caption>Uma linha por prova; cada opção de cargo conta como uma prova.</caption>',
        '<tr><th scope="col">Concurso</th><th scope="col">Data</th><th scope="col">Nota pela regra</th>'
        '<th scope="col">Situação</th><th scope="col">Quanto falta para o corte</th></tr>',
    ]
    for prova in painel.provas:
        concurso = por_nome[prova.concurso]
        nota = next((n for n in concurso.notas if _variante(n.variante) == prova.variante), None)
        opcao = f'<br><span class="nota">Opção: {escape(prova.variante)}</span>' if prova.variante else ''
        linhas.append(
            f'<tr><td>{_celula_do_nome(concurso)}{opcao}</td>'
            f'<td>{escape(data_br(concurso.data_prova) or "sem data")}</td>'
            f'<td>{_nota_pela_regra(prova, nota)}<br><span class="nota">{concurso.acertos} de '
            f'{concurso.total} acertos</span></td>'
            f'<td>{_selo(prova)}</td>'
            f'<td>{escape(prova.quanto_falta or "–")}</td></tr>'
        )
    linhas += [
        '</table>',
        '<p class="nota">Nota pela regra: a nota calculada como manda o edital (com o desconto por erro e os '
        'pesos; questão anulada conta como acerto), em percentual da nota máxima. "No limite" é estar a até '
        '2 pontos percentuais do corte, para cima ou para baixo.</p>',
    ]
    return linhas


def _nota_pela_regra(prova: Prova, nota: NotaFinal | None) -> str:
    if nota is None:
        return escape(percentual(prova.percentual))
    return escape(
        f'{percentual(nota.percentual)} ({formatar(round(nota.nota, 2))} de {formatar(nota.nota_maxima)} pontos)'
    )


def _celula_do_nome(concurso: ConcursoNoIndice) -> str:
    """O nome do edital como link e, embaixo, o subtítulo; o selo "a confirmar" quando o nome não veio do
    edital nem do usuário."""
    nome = concurso.nome_mostrado
    link = f'<a href="{escape(concurso.nome)}/{ARQUIVO_RELATORIO_HTML}">{escape(concurso.titulo)}</a>'
    if nome is None:
        return link
    selo = ' <span class="selo selo-limite">a confirmar</span>' if nome.a_confirmar else ''
    subtitulo = f'<br><span class="nota">{escape(nome.subtitulo)}</span>' if nome.subtitulo else ''
    return f'{link}{selo}{subtitulo}'


def _simulado(pasta_provas: Path) -> dict:
    simulado = ler_dados(pasta_provas).get('simulado')
    return simulado if isinstance(simulado, dict) else {}


def _tabela_de_simulados(simulados: list[tuple[ConcursoNoIndice, dict]]) -> list[str]:
    """Fora da tabela de concursos e, por padrão, do consolidado: a prova original é de outra época e banca."""
    if not simulados:
        return []
    linhas = [
        '<h3>Simulados que você fez</h3>',
        '<table>',
        '<caption>Provas anteriores resolvidas como simulado.</caption>',
        '<tr><th scope="col">Simulado</th><th scope="col">Resolvido em</th><th scope="col">Prova original</th>'
        '<th scope="col">Acertos</th><th scope="col">Nota pela regra</th></tr>',
    ]
    for concurso, simulado in simulados:
        original = ' '.join(
            str(parte) for parte in (simulado.get('orgao'), simulado.get('ano_original')) if parte
        )
        banca = f' ({simulado["organizadora"]})' if simulado.get('organizadora') else ''
        link = simulado.get('link')
        original_html = escape(f'{original or "?"}{banca}')
        if link:
            original_html = f'<a href="{escape(link)}">{original_html}</a>'
        linhas.append(
            f'<tr><td><a href="{escape(concurso.nome)}/{ARQUIVO_RELATORIO_HTML}">{escape(concurso.nome)}</a></td>'
            f'<td>{escape(data_br(concurso.data_prova) or "sem data")}</td>'
            f'<td>{original_html}</td>'
            f'<td>{concurso.acertos} de {concurso.total}</td>'
            f'<td>{_percentual_pela_regra(concurso)}</td></tr>'
        )
    linhas += [
        '</table>',
        '<p class="nota">Corrigidos pela regra da banca da prova original, com os tópicos do edital do '
        'concurso que você quer. Ficam fora dos números acima e da evolução.</p>',
    ]
    return linhas


def _percentual_pela_regra(concurso: ConcursoNoIndice) -> str:
    if not concurso.notas:
        return escape(percentual(concurso.percentual))
    return '<br>'.join(
        escape(
            f'{nota.variante + ": " if nota.variante else ""}{percentual(nota.percentual)} '
            f'({formatar(round(nota.nota, 2))} de {formatar(nota.nota_maxima)} pontos)'
        )
        for nota in concurso.notas
    )


def _pontos_fortes(painel: Painel, consolidado: pd.DataFrame) -> list[str]:
    titulo = '<h2 id="pontos-fortes">Meus pontos fortes</h2>'
    if painel.fortes:
        return [titulo, _lista_html([escape(forte.frase) for forte in painel.fortes])]
    if not ha_amostra_por_disciplina(consolidado):
        return [
            titulo,
            '<p>Ainda não há questões suficientes com a disciplina identificada para apontar pontos fortes '
            f'(são precisas pelo menos {N_MINIMO_TOPICO} por disciplina). Cadastre o edital de cada concurso, '
            'que traz as disciplinas, ou faça mais um concurso.</p>',
        ]
    return [
        titulo,
        f'<p>Nenhuma disciplina chegou ao mínimo de {escape(percentual(100 * painel.limiar, 0))} que você '
        'definiu, descontado o chute.</p>',
    ]


def _pontos_a_melhorar(painel: Painel, suficiente: bool) -> list[str]:
    linhas = ['<h2 id="pontos-a-melhorar">Meus pontos a melhorar</h2>']
    if not suficiente:
        return [
            *linhas,
            f'<p>Para apontar tópicos fracos, são precisos pelo menos {MINIMO_CONCURSOS} concursos analisados.</p>',
        ]
    if not painel.grupos:
        return [*linhas, '<p>Nenhum tópico ficou abaixo do esperado em mais de um concurso.</p>']
    prioridade = topicos_por_impacto(painel.grupos)
    linhas.append(f'<p>Os {len(prioridade)} tópicos com maior ganho de pontos se você melhorar agora:</p>')
    linhas.append(
        _lista_html(
            [
                f'<strong>{escape(t.topico)}</strong> ({escape(t.disciplina)}): '
                f'{escape(t.frase(painel.limiar))}'
                for t in prioridade
            ]
        )
    )
    linhas.append('<details><summary><h3>Por disciplina</h3></summary>')
    for grupo in painel.grupos:
        linhas += [
            f'<h4>{escape(grupo.titulo)}</h4>',
            _lista_html(
                [
                    f'<strong>{escape(t.topico)}</strong>: {escape(t.frase(painel.limiar))}'
                    for t in grupo.topicos
                ]
            ),
            f'<p>{escape(grupo.sugestao)}</p>',
        ]
    linhas.append('</details>')
    return linhas


def _estou_evoluindo(painel: Painel, suficiente: bool) -> list[str]:
    linhas = ['<h2 id="evolucao">Estou evoluindo?</h2>']
    if not suficiente:
        return [*linhas, f'<p>{escape(painel.kpis.tendencia.frase)}</p>']
    tendencia = painel.kpis.tendencia
    if painel.situacoes:
        linhas.append(f'<p><strong>{escape(painel.frase_de_evolucao)}</strong></p>')
    linhas.append(f'<p>{escape(tendencia.frase)}</p>')
    if painel.situacoes:
        linhas.append(
            _lista_html([f'{escape(s.disciplina)}: {escape(s.situacao)}' for s in painel.situacoes])
        )
    principal, *demais = _FIGURAS
    imagem, alt, legenda = principal
    linhas.append(
        f'<figure><img src="{PASTA_CONSOLIDADO}/{imagem}" alt="{escape(alt)}">'
        f'<figcaption>{escape(legenda)}</figcaption></figure>'
    )
    if demais:
        linhas.append('<details><summary>Outros gráficos</summary>')
        for imagem, alt, legenda in demais:
            linhas.append(
                f'<figure><img src="{PASTA_CONSOLIDADO}/{imagem}" alt="{escape(alt)}">'
                f'<figcaption>{escape(legenda)}</figcaption></figure>'
            )
        linhas.append('</details>')
    return linhas


def _atalhos_das_secoes(secoes: list[_SecaoPropria]) -> str:
    if not secoes:
        return ''
    cards = '\n'.join(
        f'<div class="atalho"><p><strong>{escape(s.titulo)}</strong></p>'
        f'<p class="nota"><a href="#{s.ancora}">Abrir detalhes</a></p></div>'
        for s in secoes
    )
    detalhes = '\n'.join(
        f'<details id="{s.ancora}"><summary><h2>{escape(s.titulo)}</h2></summary>\n{s.html}\n</details>'
        for s in secoes
    )
    return (
        f'<section aria-label="Atalhos"><h2>Próximos passos no app</h2>\n'
        f'<div class="atalhos">\n{cards}\n</div>\n{detalhes}\n</section>'
    )


def _o_que_fazer(painel: Painel) -> list[str]:
    linhas = ['<h2 id="o-que-fazer">O que fazer agora</h2>']
    if not painel.acoes:
        return [
            *linhas,
            '<p>Nenhuma ação sugerida por enquanto: analise mais concursos para o app apontar prioridades.</p>',
        ]
    itens = [
        escape(acao.texto) + (f' <a href="{acao.link}">Ver a seção</a>' if acao.link else '')
        for acao in painel.acoes
    ]
    return [*linhas, '<ol>\n' + '\n'.join(f'<li>{item}</li>' for item in itens) + '\n</ol>']


def _secoes_proprias(raiz_analises: Path) -> list[_SecaoPropria]:
    """Só existem com a integração ligada: radar (PCI), simulado focado, recomendações e prática no TEC."""
    candidatas = (
        ('prazos', 'Prazos dos editais', raiz_analises / ARQUIVO_RADAR),
        ('simulado-focado', 'Simulado focado', raiz_analises / ARQUIVO_SIMULADO_FOCADO),
        ('onde-estudar', 'Onde estudar', raiz_analises / PASTA_CONSOLIDADO / ARQUIVO_RECOMENDACOES),
        ('pratica', 'Prática no TEC', raiz_analises / PASTA_PRATICA / ARQUIVO_RESUMO),
    )
    return [
        _SecaoPropria(ancora, titulo, _html(arquivo.read_text(encoding='utf-8'), nivel=1))
        for ancora, titulo, arquivo in candidatas
        if arquivo.exists()
    ]


def _detalhes_tecnicos(
    concursos: list[ConcursoNoIndice],
    decisoes: list[Observacao],
    avisos: list[Observacao],
    gap: pd.DataFrame,
    evolucao_tecnica: Path | None,
) -> str:
    partes = [
        '<details id="detalhes-tecnicos">',
        f'<summary><h2>{TITULO_DETALHES_TECNICOS}</h2></summary>',
        '<p class="nota">Para quem quer conferir as contas: as regras usadas, as decisões automáticas e os '
        'números de cada análise.</p>',
        '<h3>Como o app chegou nesses números</h3>',
        _observacoes(decisoes, 'Nenhuma decisão automática.'),
        '<h3>Observações sobre os dados</h3>',
        _observacoes(avisos, 'Nenhuma observação.'),
        '<h3>Regras de correção e nível do edital</h3>',
        _tabela_de_regras(concursos),
        '<h3>Quanto falta para o corte (tabela técnica)</h3>',
        _tabela_de_gap(gap),
    ]
    if evolucao_tecnica is not None:
        partes.append(
            _html(evolucao_tecnica.read_text(encoding='utf-8'), base=f'{PASTA_CONSOLIDADO}/', nivel=2)
        )
    partes.append(
        '<p class="nota">Simulados ficam fora do consolidado e das tendências, a não ser com '
        '<code>incluir_simulados = true</code> em <code>[analise]</code>.</p>'
    )
    partes.append('</details>')
    return '\n'.join(partes)


def _observacoes(observacoes: list[Observacao], vazio: str) -> str:
    if not observacoes:
        return f'<p>{escape(vazio)}</p>'
    itens = []
    for item in observacoes:
        if item.texto is None:
            itens.append(f'{escape(item.concurso)}: Observação técnica: {escape(item.detalhe)}')
        else:
            itens.append(
                f'{escape(item.concurso)}: {escape(item.texto)}<br><span class="nota">Detalhe técnico: '
                f'{escape(item.detalhe)}</span>'
            )
    return _lista_html(itens)


def _tabela_de_regras(concursos: list[ConcursoNoIndice]) -> str:
    if not concursos:
        return '<p>Nenhum concurso analisado.</p>'
    linhas = [
        '<table>',
        '<caption>De onde veio a regra de correção e quanto do edital o app conseguiu ler.</caption>',
        '<tr><th scope="col">Concurso</th><th scope="col">Edital</th><th scope="col">Correção</th></tr>',
    ]
    for concurso in concursos:
        rotulo, classe = _SELOS_DA_CORRECAO.get(concurso.fonte or '', ('sem regra de correção', 'alerta'))
        confianca = f' ({_numero(concurso.confianca, 2)})' if concurso.confianca is not None else ''
        nivel, classe_do_nivel = _NIVEIS_DO_EDITAL.get(concurso.nivel_edital or '', ('sem edital', 'info'))
        linhas.append(
            f'<tr><td>{escape(concurso.nome)}</td>'
            f'<td><span class="selo {classe_do_nivel}">{escape(nivel)}</span></td>'
            f'<td><span class="selo {classe}">{escape(rotulo)}{confianca}</span></td></tr>'
        )
    linhas.append('</table>')
    return '\n'.join(linhas)


def _topicos_sugeridos(pasta: Path) -> tuple[int, int]:
    """Questões com tópico escolhido pelo app e ainda não revisado, e o total de questões."""
    questoes = pasta / ARQUIVO_QUESTOES
    if not questoes.exists():
        return 0, 0
    tabela = pd.read_csv(questoes, keep_default_na=False)
    sugeridos = int(((tabela['topico'] != TOPICO_NAO_MAPEADO) & ~tabela['revisado'].astype(bool)).sum())
    return sugeridos, len(tabela)


def _leituras_a_conferir(pasta: Path) -> int:
    respostas = pasta / ARQUIVO_RESPOSTAS
    if not respostas.exists():
        return 0
    return int(pd.read_csv(respostas)['revisar'].astype(bool).sum())


def _decisoes_nome(pasta: Path, pasta_provas: Path) -> list[tuple[str, str]]:
    if not (pasta_provas / ARQUIVO_CONFIG).exists():
        return []
    identificacao = _json(pasta / ARQUIVO_EDITAL_ESTRUTURADO).get('identificacao')
    nome = nome_do_concurso(carregar_concurso(pasta_provas), identificacao)
    if not nome.a_confirmar:
        return []
    return [
        (
            f'o nome “{nome.titulo}” não veio do edital; confirme na tela Concursos.',
            f'nome do concurso: {nome.titulo} ({nome.origem}); a confirmar em Concursos',
        )
    ]


def _decisoes_correcao(pasta: Path) -> list[tuple[str, str]]:
    correcao = _correcao(pasta)
    regra = f'{correcao.get("modelo")}, fator {correcao.get("fator_penalidade", 0):g}'
    if correcao.get('fonte') == 'perfil':
        return [
            (
                'o edital não traz a regra de correção; usei a regra padrão da banca.',
                f'regra de correção do perfil da banca ({regra}): o edital e o concurso.yaml não a trazem',
            )
        ]
    if correcao.get('fonte') == 'default':
        return [
            (
                'nenhuma fonte traz a regra de correção; usei a regra padrão: cada acerto vale um ponto.',
                f'regra de correção padrão ({regra}): nenhuma fonte a traz',
            )
        ]
    return []


def _decisoes_estruturado(pasta: Path) -> list[tuple[str, str]]:
    decisoes: list[tuple[str, str]] = []
    estruturado = _json(pasta / ARQUIVO_EDITAL_ESTRUTURADO)
    for campo, valor in (estruturado.get('prova') or {}).items():
        if valor.get('fonte') in _ORIGEM_DO_CAMPO and valor.get('valor') is not None:
            decisoes.append(
                (
                    f'{campo.replace("_", " ")} da prova: {valor["valor"]}, {_ORIGEM_LEIGA[valor["fonte"]]}.',
                    f'{campo} da prova: {valor["valor"]} ({_ORIGEM_DO_CAMPO[valor["fonte"]]})',
                )
            )
    objetiva = (estruturado.get('cronograma') or {}).get('objetiva') or {}
    if objetiva.get('fonte') == 'llm' and objetiva.get('valor') is not None:
        decisoes.append(
            (
                f'data da prova: {data_br(objetiva["valor"]) or objetiva["valor"]}, {_ORIGEM_LEIGA["llm"]}.',
                f'data da prova: {objetiva["valor"]} ({_ORIGEM_DO_CAMPO["llm"]})',
            )
        )
    return decisoes


def _decisoes(pasta: Path, pasta_provas: Path) -> list[Observacao]:
    decisoes = [
        *_decisoes_nome(pasta, pasta_provas),
        *_decisoes_correcao(pasta),
        *_decisoes_estruturado(pasta),
    ]
    sugeridos, total = _topicos_sugeridos(pasta)
    if sugeridos:
        decisoes.append(
            (
                f'o app escolheu o tópico de {sugeridos} de {total} questões; confira na tela Conferir.',
                f'{sugeridos} de {total} questões com tópico sugerido por similaridade com o edital; '
                f'confira em provas/{pasta.name}/revisao/',
            )
        )
    return [Observacao(pasta.name, texto, detalhe) for texto, detalhe in decisoes]


def _avisos(pasta: Path) -> list[Observacao]:
    avisos = []
    for original in _json(pasta / ARQUIVO_EDITAL_ESTRUTURADO).get('avisos') or []:
        texto = original.removeprefix(f'{pasta.name}: ')
        avisos.append((traduzir_aviso(texto), texto))
    if not _correcao(pasta).get('data_prova'):
        avisos.append(
            (
                'não encontrei a data da prova no edital nem no cadastro; este concurso fica fora da evolução.',
                'sem data da prova; fica fora das análises de tendência',
            )
        )
    discrepancias = pasta / ARQUIVO_DISCREPANCIAS
    if discrepancias.exists():
        tabela = pd.read_csv(discrepancias, keep_default_na=False)
        for linha in tabela[tabela['severidade'].isin(_SEVERIDADES_NO_RELATORIO)].itertuples():
            avisos.append(
                (
                    f'o edital e a prova não batem em {linha.item}: o edital diz {linha.esperado_edital}, '
                    f'a prova tem {linha.observado_prova}.',
                    f'{linha.item}: edital {linha.esperado_edital}, prova {linha.observado_prova} '
                    f'({linha.severidade})',
                )
            )
    if revisar := _leituras_a_conferir(pasta):
        avisos.append(
            (
                f'{plural(revisar, "resposta")} da folha com leitura incerta; confira na tela Analisar.',
                f'{revisar} leituras da folha para revisar: corrija o respostas_extraidas.csv e rode '
                f'`gabarito-vivo analyze {pasta.name} --reuse-csv`',
            )
        )
    return [Observacao(pasta.name, texto, detalhe) for texto, detalhe in avisos]


def _tabela_de_gap(gap: pd.DataFrame) -> str:
    gap = gap.dropna(subset=['menor_gap_percentual']) if not gap.empty else gap
    if gap.empty:
        return '<p>Nenhum concurso com corte no edital.</p>'
    linhas = [
        '<table>',
        '<caption>Gap = nota − corte, pelo corte mais distante; negativo é o que falta.</caption>',
        '<tr><th scope="col">Concurso</th><th scope="col">Percentual ponderado</th>'
        '<th scope="col">Menor gap (p.p.)</th><th scope="col">Corte mais distante</th>'
        '<th scope="col">Atingido</th></tr>',
    ]
    for linha in gap.itertuples():
        nome = rotulo_com_variante(linha.concurso, linha.variante)
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


def _lista_html(itens: list[str]) -> str:
    """Itens já escapados."""
    return '<ul>\n' + '\n'.join(f'<li>{item}</li>' for item in itens) + '\n</ul>'


def _existe(caminho: Path) -> Path | None:
    return caminho if caminho.exists() else None


def _correcao(pasta: Path) -> dict:
    configuracoes = _json(pasta / ARQUIVO_CORRECAO)
    return configuracoes[0] if isinstance(configuracoes, list) and configuracoes else {}


def _json(caminho: Path) -> dict | list:
    return json.loads(caminho.read_text(encoding='utf-8')) if caminho.exists() else {}


def _numero(valor: float, casas: int) -> str:
    return f'{valor:.{casas}f}'.replace('.', ',')


def _versao() -> str:
    try:
        from concursos.produto import versao_do_pacote

        return versao_do_pacote()
    except PackageNotFoundError:
        return 'desconhecida'
